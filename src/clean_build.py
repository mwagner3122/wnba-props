"""prop_results builder for phase 3 clean."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from typing import Any

from src.clean_prep import (
    REASON_MATCHED,
    REASON_MISSING_EVENT,
    REASON_NO_NAME,
    REASON_NO_PG,
    _print_step,
)
from src.clean_names import _void_info
from src.logging_setup import setup_logging

logger = setup_logging()

def build_prop_results(
    conn: sqlite3.Connection,
    *,
    name_resolution: dict[str, dict[str, Any]],
    events: dict[str, sqlite3.Row],
) -> dict[str, int]:
    """Rebuild prop_results from odds_snapshots. Returns count summary."""
    before = conn.execute("SELECT COUNT(*) AS c FROM prop_results").fetchone()["c"]
    odds_count = conn.execute("SELECT COUNT(*) AS c FROM odds_snapshots").fetchone()["c"]
    print(
        f"Step: rebuild prop_results (table before={before}, odds_snapshots={odds_count})",
        flush=True,
    )
    conn.execute("DELETE FROM prop_results")

    # Index player_games by (player_id, game_date) - game_date aligns with game_date_et
    pg_index: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in conn.execute(
        """
        SELECT game_id, game_date, player_id, player_name, team_id, opponent_id,
               minutes, points, dnp_reason
        FROM player_games
        WHERE player_id IS NOT NULL AND game_date IS NOT NULL
        """
    ):
        pg_index[(str(row["player_id"]), str(row["game_date"]))].append(row)

    stats = Counter()
    batch: list[tuple[Any, ...]] = []

    for snap in conn.execute("SELECT * FROM odds_snapshots ORDER BY snapshot_id"):
        stats["odds_in"] += 1
        odds_game_id = str(snap["game_id"])
        event = events.get(odds_game_id)
        commence = event["commence_time_utc"] if event else None
        game_date_et = event["game_date_et"] if event else None

        line = snap["line"]
        is_whole = 0
        if line is not None:
            try:
                is_whole = int(float(line).is_integer())
            except (TypeError, ValueError):
                is_whole = 0

        raw = snap["player_name_raw"]
        resolved = name_resolution.get(raw) or {
            "player_id": None,
            "method": None,
            "proposals": [],
            "reason_code": REASON_NO_NAME,
        }
        proposals_json = (
            json.dumps(resolved["proposals"], ensure_ascii=False)
            if resolved.get("proposals")
            else None
        )

        player_id = resolved.get("player_id")
        method = resolved.get("method")
        reason = resolved.get("reason_code")

        match_status = "unmatched"
        stats_game_id = None
        team_id = None
        opponent_id = None
        minutes = None
        actual_points = None
        is_voided = 0
        void_reason = None

        if event is None:
            reason = REASON_MISSING_EVENT
            stats["missing_event"] += 1
        elif player_id is None:
            reason = reason or REASON_NO_NAME
            stats[reason] += 1
        else:
            hits = pg_index.get((str(player_id), str(game_date_et)), [])
            if not hits:
                reason = REASON_NO_PG
                stats["no_player_game"] += 1
            elif len(hits) > 1:
                # Same player two games same ET date (rare) - take first, flag reason
                hit = hits[0]
                stats_game_id = hit["game_id"]
                team_id = hit["team_id"]
                opponent_id = hit["opponent_id"]
                minutes = hit["minutes"]
                is_voided, void_reason = _void_info(
                    conn,
                    stats_game_id=str(stats_game_id),
                    player_id=str(player_id),
                    minutes=minutes,
                    dnp_reason=hit["dnp_reason"],
                )
                if is_voided:
                    actual_points = None
                    match_status = "matched"
                    reason = REASON_MATCHED
                    stats["matched_voided"] += 1
                else:
                    actual_points = hit["points"]
                    match_status = "matched"
                    reason = REASON_MATCHED
                    stats["matched"] += 1
                stats["multi_pg_same_date"] += 1
            else:
                hit = hits[0]
                stats_game_id = hit["game_id"]
                team_id = hit["team_id"]
                opponent_id = hit["opponent_id"]
                minutes = hit["minutes"]
                is_voided, void_reason = _void_info(
                    conn,
                    stats_game_id=str(stats_game_id),
                    player_id=str(player_id),
                    minutes=minutes,
                    dnp_reason=hit["dnp_reason"],
                )
                if is_voided:
                    actual_points = None  # exclude from outcome evaluation data
                    match_status = "matched"
                    reason = REASON_MATCHED
                    stats["matched_voided"] += 1
                else:
                    actual_points = hit["points"]
                    match_status = "matched"
                    reason = REASON_MATCHED
                    stats["matched"] += 1

        batch.append(
            (
                snap["snapshot_id"],
                snap["captured_at_utc"],
                odds_game_id,
                snap["book"],
                snap["market"],
                raw,
                line,
                snap["over_price"],
                snap["under_price"],
                int(snap["is_alternate"] or 0),
                is_whole,
                is_voided,
                void_reason,
                commence,
                game_date_et,
                player_id,
                stats_game_id,
                team_id,
                opponent_id,
                minutes,
                actual_points,
                match_status,
                reason,
                method,
                proposals_json,
            )
        )

    conn.executemany(
        """
        INSERT INTO prop_results(
            snapshot_id, captured_at_utc, odds_game_id, book, market,
            player_name_raw, line, over_price, under_price,
            is_alternate, is_whole_number_line, is_voided, void_reason,
            commence_time_utc, game_date_et, player_id, stats_game_id,
            team_id, opponent_id, minutes, actual_points,
            match_status, reason_code, name_match_method, fuzzy_proposals
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        batch,
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) AS c FROM prop_results").fetchone()["c"]
    _print_step(
        "prop_results",
        odds_count,
        after,
        "1:1 with odds_snapshots (unmatched kept with reason_code)",
    )
    print("  reason breakdown:", dict(stats), flush=True)
    return dict(stats)
