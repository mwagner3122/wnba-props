"""Approvals and roster helpers for phase 3 clean."""
from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

from src.clean_prep import SOURCE_ODDS, _utc_now_iso
from src.name_normalize import normalize_name

def apply_approvals(
    conn: sqlite3.Connection,
    approvals: list[tuple[str, str]],
    *,
    mapped_by: str,
) -> int:
    """Persist user approvals into name_map. Returns count upserted."""
    if not approvals:
        return 0
    now = _utc_now_iso()
    n = 0
    for raw_name, player_id in approvals:
        raw_name = raw_name.strip()
        player_id = player_id.strip()
        if not raw_name or not player_id:
            continue
        conn.execute(
            """
            INSERT INTO name_map(raw_name, source, player_id, confidence, mapped_by, created_at_utc)
            VALUES (?, ?, ?, 'approved', ?, ?)
            ON CONFLICT(raw_name, source) DO UPDATE SET
                player_id = excluded.player_id,
                confidence = excluded.confidence,
                mapped_by = excluded.mapped_by,
                created_at_utc = excluded.created_at_utc
            """,
            (raw_name, SOURCE_ODDS, player_id, mapped_by, now),
        )
        n += 1
    conn.commit()
    print(f"Step: applied {n} name_map approval(s) via {mapped_by}", flush=True)
    return n


def parse_approve_args(items: list[str] | None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"--approve expects raw_name=player_id, got {item!r}")
        raw, pid = item.split("=", 1)
        out.append((raw.strip(), pid.strip()))
    return out


def load_approvals_file(path: Path | None) -> list[tuple[str, str]]:
    if path is None:
        return []
    if not path.is_file():
        raise FileNotFoundError(f"approvals file not found: {path}")
    out: list[tuple[str, str]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        if "raw_name" in sample and ("player_id" in sample or "playerid" in sample.lower()):
            reader = csv.DictReader(fh)
            for row in reader:
                raw = (row.get("raw_name") or row.get("name") or "").strip()
                pid = (row.get("player_id") or row.get("playerid") or "").strip()
                if raw and pid:
                    out.append((raw, pid))
        else:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    raw, pid = line.split("=", 1)
                elif "," in line:
                    raw, pid = line.split(",", 1)
                else:
                    continue
                out.append((raw.strip(), pid.strip()))
    return out


def _roster_for_event(
    conn: sqlite3.Connection,
    *,
    game_date_et: str,
    home_team_id: str | None,
    away_team_id: str | None,
) -> list[tuple[str, str]]:
    team_ids = [t for t in (home_team_id, away_team_id) if t]
    if not team_ids:
        return []
    placeholders = ",".join("?" * len(team_ids))
    rows = conn.execute(
        f"""
        SELECT DISTINCT player_id, player_name
        FROM player_games
        WHERE game_date = ? AND team_id IN ({placeholders})
          AND player_name IS NOT NULL
        """,
        (game_date_et, *team_ids),
    ).fetchall()
    if rows:
        return [(str(r["player_id"]), str(r["player_name"])) for r in rows]
    # Game not yet in stats: fall back to most-recent team assignment this season window
    rows = conn.execute(
        f"""
        SELECT pg.player_id, pg.player_name
        FROM player_games pg
        JOIN (
            SELECT player_id, MAX(game_date) AS max_d
            FROM player_games
            WHERE team_id IN ({placeholders})
            GROUP BY player_id
        ) latest ON latest.player_id = pg.player_id AND latest.max_d = pg.game_date
        WHERE pg.team_id IN ({placeholders})
          AND pg.player_name IS NOT NULL
        GROUP BY pg.player_id
        """,
        (*team_ids, *team_ids),
    ).fetchall()
    return [(str(r["player_id"]), str(r["player_name"])) for r in rows]

def _team_display(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(r["team_id"]): str(r["display_name"] or r["abbreviation"] or r["team_id"])
        for r in conn.execute("SELECT team_id, display_name, abbreviation FROM teams")
    }
