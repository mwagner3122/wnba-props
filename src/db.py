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
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
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
