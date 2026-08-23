"""Name resolution for phase 3 clean."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from typing import Any

from src.clean_prep import (
    SOURCE_ODDS,
    REASON_AMBIGUOUS_TEAM,
    REASON_FUZZY,
    REASON_NO_NAME,
    _canonical_players,
    _index_by_normalized,
    _utc_now_iso,
)
from src.clean_approvals import _roster_for_event
from src.logging_setup import setup_logging
from src.name_normalize import initial_lastname_key, normalize_name, propose_fuzzy

logger = setup_logging()

def resolve_names(
    conn: sqlite3.Connection,
    *,
    odds_rows: list[sqlite3.Row],
    events: dict[str, sqlite3.Row],
    team_map: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Resolve distinct raw odds names -> player_id / proposals.

    Cascade: name_map -> exact normalize -> team+date -> fuzzy PROPOSE only.
    Never auto-accepts fuzzy.
    """
    players = _canonical_players(conn)
    by_norm = _index_by_normalized(players)
    existing = {
        (r["raw_name"], r["source"]): dict(r)
        for r in conn.execute("SELECT * FROM name_map WHERE source = ?", (SOURCE_ODDS,))
    }

    # Distinct raw names with optional event context (prefer first seen event)
    name_events: dict[str, str | None] = {}
    for row in odds_rows:
        raw = row["player_name_raw"]
        if raw not in name_events:
            name_events[raw] = row["game_id"]

    now = _utc_now_iso()
    results: dict[str, dict[str, Any]] = {}
    auto_exact = 0
    auto_team = 0
    from_map = 0
    fuzzy_pending = 0
    unmatched = 0

    print(
        f"Step: resolve {len(name_events)} distinct odds names "
        f"(name_map seed={len(existing)})",
        flush=True,
    )

    for raw, odds_game_id in name_events.items():
        # 0) prior approval / persisted map
        prior = existing.get((raw, SOURCE_ODDS))
        if prior:
            results[raw] = {
                "player_id": prior["player_id"],
                "method": "name_map",
                "proposals": [],
                "reason_code": None,
            }
            from_map += 1
            continue

        norm = normalize_name(raw)
        exact_hits = by_norm.get(norm, [])
        if len(exact_hits) == 1:
            pid, _ = exact_hits[0]
            conn.execute(
                """
                INSERT INTO name_map(raw_name, source, player_id, confidence, mapped_by, created_at_utc)
                VALUES (?, ?, ?, 'exact', 'auto_exact', ?)
                ON CONFLICT(raw_name, source) DO NOTHING
                """,
                (raw, SOURCE_ODDS, pid, now),
            )
            results[raw] = {
                "player_id": pid,
                "method": "exact",
                "proposals": [],
                "reason_code": None,
            }
            auto_exact += 1
            continue
        if len(exact_hits) > 1:
            # Disambiguate via team+date if possible
            pass
        else:
            exact_hits = []

        # 2) team + date
        event = events.get(str(odds_game_id)) if odds_game_id else None
        team_hits: list[tuple[str, str]] = []
        if event is not None:
            home_id = team_map.get(normalize_name(str(event["home_team"] or "")))
            away_id = team_map.get(normalize_name(str(event["away_team"] or "")))
            roster = _roster_for_event(
                conn,
                game_date_et=str(event["game_date_et"]),
                home_team_id=home_id,
                away_team_id=away_id,
            )
            roster_by_norm = _index_by_normalized(roster)
            if exact_hits:
                roster_ids = {p for p, _ in roster}
                team_hits = [(p, n) for p, n in exact_hits if p in roster_ids]
            if not team_hits:
                team_hits = roster_by_norm.get(norm, [])
            if not team_hits:
                # Abbreviation: first initial + last name within roster
                key = initial_lastname_key(norm)
                if key is not None:
                    for pid, pname in roster:
                        ck = initial_lastname_key(normalize_name(pname))
                        if ck == key:
                            team_hits.append((pid, pname))

        if len(team_hits) == 1:
            pid, _ = team_hits[0]
            conn.execute(
                """
                INSERT INTO name_map(raw_name, source, player_id, confidence, mapped_by, created_at_utc)
                VALUES (?, ?, ?, 'team_date', 'auto_team_date', ?)
                ON CONFLICT(raw_name, source) DO NOTHING
                """,
                (raw, SOURCE_ODDS, pid, now),
            )
            results[raw] = {
                "player_id": pid,
                "method": "team_date",
                "proposals": [],
                "reason_code": None,
            }
            auto_team += 1
            continue
        if len(team_hits) > 1:
            proposals = [
                {"player_id": p, "player_name": n, "score": 1.0} for p, n in team_hits[:5]
            ]
            results[raw] = {
                "player_id": None,
                "method": None,
                "proposals": proposals,
                "reason_code": REASON_AMBIGUOUS_TEAM,
            }
            unmatched += 1
            continue

        # 3) fuzzy PROPOSE only - never auto-accept
        pool: list[tuple[str, str]] = []
        if event is not None:
            home_id = team_map.get(normalize_name(str(event["home_team"] or "")))
            away_id = team_map.get(normalize_name(str(event["away_team"] or "")))
            pool = _roster_for_event(
                conn,
                game_date_et=str(event["game_date_et"]),
                home_team_id=home_id,
                away_team_id=away_id,
            )
        if not pool:
            pool = players
        proposals = propose_fuzzy(norm, pool)
        if proposals:
            results[raw] = {
                "player_id": None,
                "method": None,
                "proposals": proposals,
                "reason_code": REASON_FUZZY,
            }
            fuzzy_pending += 1
            print(
                f"  FUZZY PROPOSAL (not applied): {raw!r} -> "
                + ", ".join(
                    f"{p['player_name']} ({p['player_id']}, {p['score']})"
                    for p in proposals[:3]
                ),
                flush=True,
            )
        else:
            results[raw] = {
                "player_id": None,
                "method": None,
                "proposals": [],
                "reason_code": REASON_NO_NAME,
            }
            unmatched += 1

    conn.commit()
    after_map = conn.execute(
        "SELECT COUNT(*) AS c FROM name_map WHERE source = ?", (SOURCE_ODDS,)
    ).fetchone()["c"]
    print(
        f"  name resolve: from_map={from_map} exact={auto_exact} team_date={auto_team} "
        f"fuzzy_pending={fuzzy_pending} unmatched={unmatched} "
        f"name_map_total={after_map}",
        flush=True,
    )
    return results


def _void_info(
    conn: sqlite3.Connection,
    *,
    stats_game_id: str,
    player_id: str,
    minutes: float | None,
    dnp_reason: str | None,
) -> tuple[int, str | None]:
    """Return (is_voided, void_reason). Did-not-play != under."""
    if dnp_reason:
        return 1, f"dnp_reason:{dnp_reason}"
    if minutes is None or float(minutes) <= 0:
        avail = conn.execute(
            "SELECT status FROM availability WHERE game_id = ? AND player_id = ?",
            (stats_game_id, player_id),
        ).fetchone()
        if avail and str(avail["status"]).startswith("dnp"):
            return 1, f"availability:{avail['status']}"
        if avail and avail["status"] == "inactive":
            return 1, "availability:inactive"
        return 1, "minutes_zero_or_null"
    return 0, None
