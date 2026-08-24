"""As-of core primitives (phase 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# Fixed role priors for positional defense cold-start (not fit on full data).
_POS_PTS_PRIOR = {"G": 16.0, "F": 15.0, "C": 14.0}


def shrink(
    observed: np.ndarray | float,
    n: np.ndarray | float,
    prior: np.ndarray | float,
    k: np.ndarray | float,
) -> np.ndarray:
    """estimate = (n*observed + k*prior) / (n+k)."""
    observed = np.asarray(observed, dtype=float)
    n = np.asarray(n, dtype=float)
    prior = np.asarray(prior, dtype=float)
    k = np.asarray(k, dtype=float)
    denom = n + k
    out = np.array(prior, dtype=float, copy=True)
    if out.ndim == 0:
        out = np.full(np.shape(denom), float(out))
    usable = denom > 0
    obs = np.where(np.isfinite(observed), observed, prior)
    out = np.where(usable, (n * obs + k * prior) / np.where(usable, denom, 1.0), prior)
    return out


def prior_weight(n: np.ndarray | float, k: np.ndarray | float) -> np.ndarray:
    n = np.asarray(n, dtype=float)
    k = np.asarray(k, dtype=float)
    denom = n + k
    return np.where(denom > 0, k / denom, 1.0)


def _per40(stat: pd.Series, minutes: pd.Series) -> pd.Series:
    m = minutes.astype(float)
    s = stat.astype(float)
    out = pd.Series(np.nan, index=stat.index, dtype=float)
    ok = m > 0
    out.loc[ok] = s.loc[ok] * 40.0 / m.loc[ok]
    return out


def _tz_offset_hours(tz_name: str, game_date: str) -> float:
    try:
        dt = datetime.strptime(str(game_date)[:10], "%Y-%m-%d").replace(
            hour=19, tzinfo=ZoneInfo(tz_name)
        )
        off = dt.utcoffset()
        return float(off.total_seconds() / 3600.0) if off is not None else 0.0
    except Exception:
        return 0.0


def load_frames(conn) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pg = pd.read_sql_query(
        """
        SELECT game_id, game_date, player_id, player_name, team_id, opponent_id,
               home_away, minutes, fga, fgm, fg3a, fg3m, fta, ftm, points,
               oreb, dreb, reb, ast, stl, blk, tov, pf, started, dnp_reason
        FROM player_games
        """,
        conn,
    )
    games = pd.read_sql_query(
        """
        SELECT game_id, game_date, season, season_type, home_team_id, away_team_id,
               home_score, away_score, overtime_periods, possessions_est, pace,
               home_off_rating, away_off_rating
        FROM games
        """,
        conn,
    )
    players = pd.read_sql_query(
        "SELECT player_id, player_name, position FROM players", conn
    )
    teams = pd.read_sql_query(
        "SELECT team_id, abbreviation, location, name, display_name FROM teams",
        conn,
    )
    return pg, games, players, teams


def _assign_game_ord(games: pd.DataFrame) -> pd.DataFrame:
    g = games.copy()
    g["game_date"] = g["game_date"].astype(str)
    g = g.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True)
    g["game_ord"] = np.arange(len(g), dtype=np.int64)
    return g


def _shift_trail(series: pd.Series, groups: pd.Series, window: int) -> pd.Series:
    """Trailing mean of prior values within groups (no center)."""
    return series.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).rolling(window, min_periods=1).mean()
    )


def _shift_ewm(series: pd.Series, groups: pd.Series, half: float) -> pd.Series:
    return series.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).ewm(halflife=half, min_periods=1).mean()
    )


def _shift_expanding(series: pd.Series, groups: pd.Series) -> pd.Series:
    return series.groupby(groups, sort=False).transform(
        lambda s: s.shift(1).expanding(min_periods=1).mean()
    )
