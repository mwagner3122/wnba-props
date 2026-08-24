"""Prep helpers for phase 3 clean (events, approvals, team maps)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from typing import Any
from zoneinfo import ZoneInfo

from src.logging_setup import setup_logging
from src.name_normalize import normalize_name

logger = setup_logging()

ET = ZoneInfo("America/New_York")
SOURCE_ODDS = "odds"

# reason_code vocabulary (never silent drop)
REASON_MATCHED = "matched"
REASON_MISSING_EVENT = "missing_event_meta"
REASON_NO_NAME = "no_name_match"
REASON_FUZZY = "needs_fuzzy_approval"
REASON_NO_PG = "no_player_game"
REASON_AMBIGUOUS_TEAM = "ambiguous_team_date"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(ts: str) -> datetime:
    text = (ts or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def game_date_et_from_utc(commence_time_utc: str) -> str:
    """Derive Eastern calendar date from a UTC timestamp (never string arithmetic)."""
    return _parse_utc(commence_time_utc).astimezone(ET).date().isoformat()


def _print_step(label: str, before: int, after: int, drop_reason: str | None = None) -> None:
    dropped = before - after
    msg = f"  [{label}] before={before} after={after}"
    if dropped > 0:
        msg += f" dropped={dropped}"
        if drop_reason:
            msg += f" ({drop_reason})"
    elif dropped < 0:
        msg += f" added={-dropped}"
    print(msg, flush=True)


def ensure_game_date_et(conn: sqlite3.Connection) -> None:
    """Backfill games.game_date_et from games.game_date (ESPN dates are ET calendar days)."""
    before_null = conn.execute(
        "SELECT COUNT(*) AS c FROM games WHERE game_date_et IS NULL OR game_date_et = ''"
    ).fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()["c"]
    print(f"Step: backfill games.game_date_et (null/empty before={before_null} / {total})", flush=True)
    conn.execute(
        """
        UPDATE games
        SET game_date_et = game_date
        WHERE game_date_et IS NULL OR game_date_et = ''
        """
    )
    conn.commit()
    after_null = conn.execute(
        "SELECT COUNT(*) AS c FROM games WHERE game_date_et IS NULL OR game_date_et = ''"
    ).fetchone()["c"]
    _print_step("games.game_date_et filled", before_null, after_null, "remaining null")


def load_odds_events_from_raw(conn: sqlite3.Connection, raw_odds_dir: Path) -> int:
    """Rebuild odds_events from data/raw/odds/*.json (+ fixture if referenced)."""
    before = conn.execute("SELECT COUNT(*) AS c FROM odds_events").fetchone()["c"]
    print(f"Step: rebuild odds_events from raw JSON (table before={before})", flush=True)
    conn.execute("DELETE FROM odds_events")
    files = sorted(raw_odds_dir.glob("*.json")) if raw_odds_dir.is_dir() else []
    inserted = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Skipping unreadable odds raw %s: %s", path, exc)
            continue
        events: list[dict[str, Any]] = []
        if isinstance(payload.get("events"), list):
            events.extend(e for e in payload["events"] if isinstance(e, dict))
        eo = payload.get("event_odds")
        if isinstance(eo, list):
            events.extend(e for e in eo if isinstance(e, dict))
        elif isinstance(eo, dict) and "id" in eo:
            events.append(eo)
        # Fixture shape: top-level event fields
        if payload.get("_fixture") and payload.get("id"):
            events.append(payload)
        for ev in events:
            oid = str(ev.get("id") or "").strip()
            commence = str(ev.get("commence_time") or "").strip()
            if not oid or not commence:
                continue
            try:
                gdate = game_date_et_from_utc(commence)
            except (TypeError, ValueError) as exc:
                logger.error("Bad commence_time for odds event %s: %s", oid, exc)
                continue
            commence_utc = commence
            if not (commence_utc.endswith("Z") or "+" in commence_utc or commence_utc.endswith("z")):
                if "T" in commence_utc and len(commence_utc) >= 19:
                    commence_utc = commence_utc[:19] + "Z"
            conn.execute(
                """
                INSERT INTO odds_events(
                    odds_game_id, commence_time_utc, home_team, away_team,
                    game_date_et, source_file
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(odds_game_id) DO UPDATE SET
                    commence_time_utc = excluded.commence_time_utc,
                    home_team = excluded.home_team,
                    away_team = excluded.away_team,
                    game_date_et = excluded.game_date_et,
                    source_file = excluded.source_file
                """,
                (
                    oid,
                    commence_utc,
                    ev.get("home_team"),
                    ev.get("away_team"),
                    gdate,
                    path.name,
                ),
            )
            inserted += 1
    conn.commit()
    after = conn.execute("SELECT COUNT(*) AS c FROM odds_events").fetchone()["c"]
    _print_step("odds_events rows", before, after, "rebuilt from raw; duplicates collapsed by id")
    print(f"  raw files scanned={len(files)} upsert_ops={inserted}", flush=True)
    return after


def _team_name_to_id(conn: sqlite3.Connection) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in conn.execute(
        "SELECT team_id, display_name, location, name, abbreviation FROM teams"
    ):
        tid = row["team_id"]
        for key in (
            row["display_name"],
            f"{row['location']} {row['name']}".strip(),
            row["abbreviation"],
            row["name"],
        ):
            if key:
                mapping[normalize_name(str(key))] = tid
    return mapping

def _canonical_players(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """(player_id, player_name) name variants from players U player_games.

    A player may appear under more than one spelling (e.g. name change); keep
    every distinct (player_id, name) pair so exact normalize can hit any variant.
    """
    pairs: set[tuple[str, str]] = set()
    for row in conn.execute(
        "SELECT player_id, player_name FROM players WHERE player_name IS NOT NULL"
    ):
        pairs.add((str(row["player_id"]), str(row["player_name"])))
    for row in conn.execute(
        """
        SELECT DISTINCT player_id, player_name FROM player_games
        WHERE player_name IS NOT NULL
        """
    ):
        pairs.add((str(row["player_id"]), str(row["player_name"])))
    return sorted(pairs)


def _index_by_normalized(
    players: list[tuple[str, str]],
) -> dict[str, list[tuple[str, str]]]:
    idx: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for pid, name in players:
        idx[normalize_name(name)].append((pid, name))
    return idx
