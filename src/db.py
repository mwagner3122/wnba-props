"""SQLite schema helpers for data/wnba.db."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY,
    abbreviation TEXT,
    location TEXT,
    name TEXT,
    display_name TEXT
);

CREATE TABLE IF NOT EXISTS players (
    player_id TEXT PRIMARY KEY,
    player_name TEXT,
    position TEXT
);

CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    game_date TEXT NOT NULL,
    season INTEGER NOT NULL,
    season_type INTEGER,
    home_team_id TEXT,
    away_team_id TEXT,
    home_score INTEGER,
    away_score INTEGER,
    overtime_periods INTEGER,
    possessions_est REAL,
    pace REAL,
    home_off_rating REAL,
    away_off_rating REAL,
    attendance REAL
);

CREATE TABLE IF NOT EXISTS player_games (
    game_id TEXT NOT NULL,
    game_date TEXT,
    player_id TEXT NOT NULL,
    player_name TEXT,
    team_id TEXT,
    opponent_id TEXT,
    home_away TEXT,
    minutes REAL,
    fga INTEGER,
    fgm INTEGER,
    fg3a INTEGER,
    fg3m INTEGER,
    fta INTEGER,
    ftm INTEGER,
    points INTEGER,
    oreb INTEGER,
    dreb INTEGER,
    reb INTEGER,
    ast INTEGER,
    stl INTEGER,
    blk INTEGER,
    tov INTEGER,
    pf INTEGER,
    plus_minus INTEGER,
    started INTEGER,
    dnp_reason TEXT,
    PRIMARY KEY (game_id, player_id)
);

CREATE TABLE IF NOT EXISTS availability (
    game_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    status TEXT NOT NULL,
    minutes_played REAL NOT NULL,
    PRIMARY KEY (game_id, player_id)
);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at_utc TEXT NOT NULL,
    game_id TEXT NOT NULL,
    book TEXT NOT NULL,
    market TEXT NOT NULL,
    player_name_raw TEXT NOT NULL,
    line REAL,
    over_price REAL,
    under_price REAL,
    is_alternate INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_odds_captured ON odds_snapshots(captured_at_utc);
CREATE INDEX IF NOT EXISTS idx_odds_game ON odds_snapshots(game_id);
CREATE INDEX IF NOT EXISTS idx_odds_player ON odds_snapshots(player_name_raw);

CREATE TABLE IF NOT EXISTS ingest_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_player_games_date ON player_games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);

-- Phase 3: name crosswalk (approvals persist across clean rebuilds)
CREATE TABLE IF NOT EXISTS name_map (
    raw_name TEXT NOT NULL,
    source TEXT NOT NULL,
    player_id TEXT NOT NULL,
    confidence TEXT NOT NULL,
    mapped_by TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    PRIMARY KEY (raw_name, source)
);

-- Phase 3: Odds API event metadata (commence time / teams) from raw JSON
CREATE TABLE IF NOT EXISTS odds_events (
    odds_game_id TEXT PRIMARY KEY,
    commence_time_utc TEXT NOT NULL,
    home_team TEXT,
    away_team TEXT,
    game_date_et TEXT NOT NULL,
    source_file TEXT
);

-- Phase 3: joined clean table (odds row + matched outcome fields + flags)
CREATE TABLE IF NOT EXISTS prop_results (
    prop_result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL UNIQUE,
    captured_at_utc TEXT NOT NULL,
    odds_game_id TEXT NOT NULL,
    book TEXT NOT NULL,
    market TEXT NOT NULL,
    player_name_raw TEXT NOT NULL,
    line REAL,
    over_price REAL,
    under_price REAL,
    is_alternate INTEGER NOT NULL DEFAULT 0,
    is_whole_number_line INTEGER NOT NULL DEFAULT 0,
    is_voided INTEGER NOT NULL DEFAULT 0,
    void_reason TEXT,
    commence_time_utc TEXT,
    game_date_et TEXT,
    player_id TEXT,
    stats_game_id TEXT,
    team_id TEXT,
    opponent_id TEXT,
    minutes REAL,
    actual_points INTEGER,
    match_status TEXT NOT NULL,
    reason_code TEXT,
    name_match_method TEXT,
    fuzzy_proposals TEXT
);

CREATE INDEX IF NOT EXISTS idx_prop_results_date ON prop_results(game_date_et);
CREATE INDEX IF NOT EXISTS idx_prop_results_player ON prop_results(player_id);
CREATE INDEX IF NOT EXISTS idx_prop_results_match ON prop_results(match_status, reason_code);
CREATE INDEX IF NOT EXISTS idx_name_map_player ON name_map(player_id);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r["name"] if isinstance(r, sqlite3.Row) else r[1]) for r in rows}


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Additive migrations for existing DBs created before phase 3."""
    cols = _table_columns(conn, "games")
    if cols and "game_date_et" not in cols:
        conn.execute("ALTER TABLE games ADD COLUMN game_date_et TEXT")
        conn.commit()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    migrate_schema(conn)
    # Index after migrate so existing DBs that lacked the column still work.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_games_date_et ON games(game_date_et)"
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM ingest_meta WHERE key = ?", (key,)).fetchone()
    return None if row is None else row["value"]


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO ingest_meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
