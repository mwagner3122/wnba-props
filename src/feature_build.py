"""As-of feature frame builder body (phase 4)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.feature_build_tail import _compute_feature_frame_tail
from src.feature_asof import (
    _assign_game_ord,
    _per40,
    _position_form_priors,
    _shift_ewm,
    _shift_expanding,
    _shift_trail,
    prior_weight,
    shrink,
)


def compute_feature_frame(
    pg: pd.DataFrame,
    games: pd.DataFrame,
    players: pd.DataFrame,
    teams: pd.DataFrame,
    cfg: dict[str, Any],
) -> pd.DataFrame:
    """One feature row per player-game; features use games strictly before tip."""
    fcfg = cfg.get("features") or {}
    windows = [int(w) for w in fcfg.get("form_windows", [3, 5, 10])]
    half = float(fcfg.get("ewm_halflife_games", 5))
    team_minutes = float(
        fcfg.get("team_minutes", cfg.get("regulation_team_minutes", 200))
    )
    long_break = int(fcfg.get("long_break_days", 7))
    sk = fcfg.get("shrinkage") or {}
    k_form = float(sk.get("player_form_k", 8))
    k_usage = float(sk.get("usage_k", 10))
    k_team = float(sk.get("team_k", 12))
    k_opp = float(sk.get("opponent_k", 20))
    k_pos = float(sk.get("opponent_positional_k", 25))
    k_exp = float(sk.get("expansion_extra_k", 20))
    expansion = {
        str(a).upper()
        for a in (fcfg.get("expansion_team_abbreviations") or ["TOR", "POR"])
    }
    tz_map = {
        str(k).upper(): str(v) for k, v in (fcfg.get("team_timezones") or {}).items()
    }
    fta_factor = float(cfg.get("fta_possession_factor", 0.44))

    games = _assign_game_ord(games)
    team_abbr = {
        str(r.team_id): str(r.abbreviation).upper() for r in teams.itertuples()
    }
    expansion_ids = {tid for tid, abbr in team_abbr.items() if abbr in expansion}

    df = pg.copy()
    df["game_id"] = df["game_id"].astype(str)
    df["player_id"] = df["player_id"].astype(str)
    df["team_id"] = df["team_id"].astype(str)
    df["opponent_id"] = df["opponent_id"].astype(str)
    df["game_date"] = df["game_date"].astype(str)
    df = df.merge(
        games[["game_id", "season", "game_ord", "pace", "possessions_est"]],
        on="game_id",
        how="left",
    )
    df = df.merge(players[["player_id", "position"]], on="player_id", how="left")
    df["position"] = df["position"].fillna("G")
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    for c in (
        "points",
        "reb",
        "ast",
        "fg3m",
        "fg3a",
        "fga",
        "fta",
        "tov",
        "started",
        "stl",
        "blk",
    ):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.sort_values(
        ["player_id", "season", "game_ord"], kind="mergesort"
    ).reset_index(drop=True)
    played = df["minutes"].fillna(0) > 0
    df["played_flag"] = played.astype(int)

    df["pts_p40"] = _per40(df["points"], df["minutes"])
    df["reb_p40"] = _per40(df["reb"], df["minutes"])
    df["ast_p40"] = _per40(df["ast"], df["minutes"])
    df["fg3m_p40"] = _per40(df["fg3m"], df["minutes"])
    df["usage_raw"] = np.where(
        played,
        (
            df["fga"].fillna(0)
            + fta_factor * df["fta"].fillna(0)
            + df["tov"].fillna(0)
        )
        / df["possessions_est"].replace(0, np.nan),
        np.nan,
    )
    df["minutes_share"] = np.where(played, df["minutes"] / team_minutes, np.nan)
    df["three_rate"] = np.where(
        played & (df["fga"].fillna(0) > 0), df["fg3a"].fillna(0) / df["fga"], np.nan
    )
    df["two_rate"] = np.where(
        played & (df["fga"].fillna(0) > 0),
        (df["fga"].fillna(0) - df["fg3a"].fillna(0)) / df["fga"],
        np.nan,
    )
    df["ft_rate"] = np.where(
        played & (df["fga"].fillna(0) > 0), df["fta"].fillna(0) / df["fga"], np.nan
    )

    pkey = df["player_id"].astype(str) + "|" + df["season"].astype(str)
    df["games_played"] = (
        df.groupby(pkey, sort=False)["played_flag"].cumsum() - df["played_flag"]
    )

    priors = _position_form_priors(df)
    df = df.merge(priors, on=["season", "game_ord", "position"], how="left")

    for base, default in (
        ("pts_p40", 15.0),
        ("reb_p40", 6.0),
        ("ast_p40", 3.5),
        ("fg3m_p40", 1.2),
    ):
        col = f"prior_{base}"
        df[col] = df[col].fillna(default)

    n_gp = df["games_played"].to_numpy(dtype=float)
    for base in ("pts_p40", "reb_p40", "ast_p40", "fg3m_p40"):
        prior_v = df[f"prior_{base}"].to_numpy(dtype=float)
        for w in windows:
            raw = _shift_trail(df[base], pkey, w)
            n_eff = np.minimum(n_gp, float(w))
            df[f"{base}_l{w}"] = shrink(raw.to_numpy(), n_eff, prior_v, k_form)
        raw_e = _shift_ewm(df[base], pkey, half)
        raw_s = _shift_expanding(df[base], pkey)
        df[f"{base}_ewm"] = shrink(raw_e.to_numpy(), n_gp, prior_v, k_form)
        df[f"{base}_std"] = shrink(raw_s.to_numpy(), n_gp, prior_v, k_form)

    df["player_form_prior_weight"] = prior_weight(n_gp, k_form)
    df["start_rate_l10"] = _shift_trail(df["started"].fillna(0), pkey, 10)
    df["minutes_share_l5"] = _shift_trail(df["minutes_share"], pkey, 5)
    df["three_rate_std"] = _shift_expanding(df["three_rate"], pkey)
    df["two_rate_std"] = _shift_expanding(df["two_rate"], pkey)
    df["ft_rate_std"] = _shift_expanding(df["ft_rate"], pkey)
    usage_asof = _shift_expanding(df["usage_raw"], pkey)
    usage_prior = 0.20
    df["usage_rate_shrunk"] = shrink(
        usage_asof.to_numpy(), n_gp, usage_prior, k_usage
    )

    pace_anchor, ortg_anchor, drtg_anchor = 80.0, 100.0, 100.0
    return _compute_feature_frame_tail(
        df, games, team_abbr, tz_map, long_break, expansion_ids,
        k_team, k_opp, k_pos, k_exp, team_minutes, pace_anchor, ortg_anchor, drtg_anchor,
    )
