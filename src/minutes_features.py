"""Load as-of feature rows and targets for the phase-5 minutes model."""

from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np
import pandas as pd

# Pregame / as-of features only. Current-game `started` is NOT used (lineup card).
MINUTES_FEATURE_COLUMNS: list[str] = [
    "minutes_share_l5",
    "start_rate_l10",
    "minutes_vacated",
    "same_pos_minutes_vacated",
    "days_rest",
    "is_b2b",
    "is_home",
    "usage_rate_shrunk",
    "primary_bh_out",
    "rest_long_break",
    "favoritism",
    "last_minutes",
    "team_pace_shrunk",
]


def load_minutes_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    """Join features, box score minutes, availability, and games."""
    df = pd.read_sql_query(
        """
        SELECT
            f.game_id,
            f.player_id,
            f.game_date,
            f.season,
            f.team_id,
            f.opponent_id,
            f.position,
            f.minutes_share_l5,
            f.start_rate_l10,
            f.minutes_vacated,
            f.same_pos_minutes_vacated,
            f.days_rest,
            f.is_b2b,
            f.is_home,
            f.usage_rate_shrunk,
            f.primary_bh_out,
            f.rest_long_break,
            f.team_pace_shrunk,
            f.team_off_rtg_shrunk,
            f.opp_def_rtg_shrunk,
            pg.minutes AS y_minutes,
            pg.started AS y_started,
            a.status AS avail_status,
            g.overtime_periods
        FROM player_game_features f
        JOIN player_games pg USING (game_id, player_id)
        JOIN availability a USING (game_id, player_id)
        JOIN games g ON g.game_id = f.game_id
        ORDER BY f.player_id, f.game_date, f.game_id
        """,
        conn,
    )
    df["y_minutes"] = pd.to_numeric(df["y_minutes"], errors="coerce").fillna(0.0)
    df["played"] = (df["y_minutes"] > 0).astype(int)
    df["dnp"] = 1 - df["played"]
    # Trailing last-game minutes (as-of; shift within player).
    df["last_minutes"] = df.groupby("player_id", sort=False)["y_minutes"].shift(1)
    df["trail5_minutes"] = pd.to_numeric(df["minutes_share_l5"], errors="coerce") * 200.0
    # Spread unavailable in odds history; use team_off − opp_def as blowout proxy.
    # Heavy favorites (large positive) → fatter left tail for high-minute players.
    df["favoritism"] = (
        pd.to_numeric(df["team_off_rtg_shrunk"], errors="coerce").fillna(100.0)
        - pd.to_numeric(df["opp_def_rtg_shrunk"], errors="coerce").fillna(100.0)
    )
    for c in MINUTES_FEATURE_COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def time_split(
    df: pd.DataFrame, train_end_season: int, test_start_season: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Strict time-based split by season. No random shuffle."""
    train = df[df["season"] <= int(train_end_season)].copy()
    test = df[df["season"] >= int(test_start_season)].copy()
    if train.empty or test.empty:
        raise ValueError(
            f"Empty time split: train_end={train_end_season} "
            f"test_start={test_start_season} "
            f"(train={len(train)}, test={len(test)})"
        )
    return train, test


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df[MINUTES_FEATURE_COLUMNS].copy()


def minutes_config(cfg: dict[str, Any]) -> dict[str, Any]:
    m = dict(cfg.get("minutes") or {})
    m.setdefault("train_end_season", 2024)
    m.setdefault("test_start_season", 2025)
    m.setdefault(
        "regulation_team_minutes",
        cfg.get("regulation_team_minutes", 200),
    )
    m.setdefault("ot_team_minutes", cfg.get("ot_team_minutes", 25))
    m.setdefault("share_method", "independent_normalize_dirichlet_sim")
    m.setdefault("dirichlet_concentration", 40.0)
    m.setdefault("max_depth", 4)
    m.setdefault("learning_rate", 0.08)
    m.setdefault("max_iter_classifier", 150)
    m.setdefault("max_iter_regressor", 200)
    m.setdefault("random_state", 0)
    m.setdefault("n_sim", 400)
    m.setdefault("models_dir", "models")
    m.setdefault("dnp_calibration_plot", "reports/dnp_calibration.png")
    m.setdefault("dnp_calibration_csv", "reports/dnp_calibration.csv")
    m.setdefault("metrics_path", "reports/minutes_metrics.json")
    return m
