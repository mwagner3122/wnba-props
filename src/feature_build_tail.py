"""Tail of compute_feature_frame (team/opp/situational/teammate)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.feature_columns import FEATURE_COLUMNS, KEY_COLUMNS
from src.feature_asof import (
    _POS_PTS_PRIOR,
    _build_league_asof,
    _positional_defense_asof,
    _team_asof_frame,
    _teammate_availability,
    _tz_offset_hours,
    prior_weight,
    shrink,
)


def _compute_feature_frame_tail(
    df: pd.DataFrame,
    games: pd.DataFrame,
    team_abbr: dict,
    tz_map: dict,
    long_break: int,
    expansion_ids: set,
    k_team: float,
    k_opp: float,
    k_pos: float,
    k_exp: float,
    team_minutes: float,
    pace_anchor: float,
    ortg_anchor: float,
    drtg_anchor: float,
) -> pd.DataFrame:
    # Team / opponent context
    league = _build_league_asof(games)
    tg = _team_asof_frame(games, league)
    tg["is_expansion"] = tg["team_id"].isin(expansion_ids).astype(float)
    tg["k_team_eff"] = k_team + tg["is_expansion"] * k_exp
    n_t = tg["team_games_played"].to_numpy(dtype=float)
    k_t = tg["k_team_eff"].to_numpy(dtype=float)
    for asof_c, league_c, out_c, anchor in (
        ("pace_asof", "league_pace_asof", "team_pace_shrunk", pace_anchor),
        ("off_rtg_asof", "league_off_asof", "team_off_rtg_shrunk", ortg_anchor),
        ("def_rtg_asof", "league_def_asof", "team_def_rtg_shrunk", drtg_anchor),
    ):
        prior = tg[league_c].to_numpy(dtype=float)
        prior = np.where(np.isfinite(prior), prior, anchor)
        obs = tg[asof_c].to_numpy(dtype=float)
        tg[out_c] = shrink(obs, n_t, prior, k_t)
    tg["team_prior_weight"] = prior_weight(n_t, k_t)

    team_cols = [
        "game_id",
        "team_id",
        "team_pace_shrunk",
        "team_off_rtg_shrunk",
        "team_def_rtg_shrunk",
        "team_games_played",
        "team_prior_weight",
        "pace_asof",
        "def_rtg_asof",
        "league_pace_asof",
        "league_def_asof",
        "is_expansion",
    ]
    df = df.merge(tg[team_cols], on=["game_id", "team_id"], how="left")

    opp = tg[
        [
            "game_id",
            "team_id",
            "pace_asof",
            "def_rtg_asof",
            "team_games_played",
            "league_pace_asof",
            "league_def_asof",
            "is_expansion",
        ]
    ].rename(
        columns={
            "team_id": "opponent_id",
            "pace_asof": "opp_pace_asof",
            "def_rtg_asof": "opp_def_asof",
            "team_games_played": "opp_games_played",
            "league_pace_asof": "opp_league_pace",
            "league_def_asof": "opp_league_def",
            "is_expansion": "opp_is_expansion",
        }
    )
    df = df.merge(opp, on=["game_id", "opponent_id"], how="left")
    n_o = df["opp_games_played"].fillna(0).to_numpy(dtype=float)
    k_o = k_opp + df["opp_is_expansion"].fillna(0).to_numpy(dtype=float) * k_exp
    for asof_c, league_c, out_c, anchor in (
        ("opp_pace_asof", "opp_league_pace", "opp_pace_shrunk", pace_anchor),
        ("opp_def_asof", "opp_league_def", "opp_def_rtg_shrunk", drtg_anchor),
    ):
        prior = df[league_c].to_numpy(dtype=float)
        prior = np.where(np.isfinite(prior), prior, anchor)
        df[out_c] = shrink(df[asof_c].to_numpy(dtype=float), n_o, prior, k_o)
    df["opp_prior_weight"] = prior_weight(n_o, k_o)

    posdef = _positional_defense_asof(df)
    df = df.merge(posdef, on=["season", "game_ord", "opponent_id", "position"], how="left")
    prior_pos = (
        df["position"]
        .map(lambda p: _POS_PTS_PRIOR.get(str(p), 15.0))
        .to_numpy(dtype=float)
    )
    n_pd = df["pos_def_n"].fillna(0).to_numpy(dtype=float)
    k_pd = k_pos + df["opponent_id"].isin(expansion_ids).astype(float).to_numpy() * k_exp
    df["opp_pos_def_shrunk"] = shrink(
        df["pos_def_asof"].to_numpy(dtype=float), n_pd, prior_pos, k_pd
    )

    # Situational
    df = df.sort_values(["player_id", "game_ord"], kind="mergesort")
    prev_date = df.groupby("player_id", sort=False)["game_date"].shift(1)
    curr = pd.to_datetime(df["game_date"])
    prev = pd.to_datetime(prev_date)
    delta = (curr - prev).dt.days
    raw_rest = delta - 1
    df["is_b2b"] = np.where(prev.isna(), 0.0, (delta == 1).astype(float))
    df["rest_long_break"] = np.where(
        prev.isna(), 0.0, (raw_rest > long_break).astype(float)
    )
    df["days_rest"] = raw_rest.clip(lower=0, upper=long_break)
    df.loc[prev.isna(), "days_rest"] = np.nan

    team_game = (
        df[["team_id", "season", "game_id", "game_ord"]]
        .drop_duplicates()
        .sort_values(["team_id", "season", "game_ord"], kind="mergesort")
    )
    team_game["game_number"] = team_game.groupby(["team_id", "season"]).cumcount() + 1
    df = df.merge(
        team_game[["team_id", "season", "game_id", "game_number"]],
        on=["team_id", "season", "game_id"],
        how="left",
    )

    home_map = games.set_index("game_id")["home_team_id"].astype(str).to_dict()
    df["venue_team_id"] = df["game_id"].map(home_map)
    df["venue_abbr"] = df["venue_team_id"].map(
        lambda t: team_abbr.get(str(t), "NY")
    )
    df["venue_tz"] = df["venue_abbr"].map(
        lambda a: tz_map.get(str(a).upper(), "America/New_York")
    )
    df["tz_offset"] = [
        _tz_offset_hours(tz, d)
        for tz, d in zip(df["venue_tz"], df["game_date"], strict=False)
    ]
    prev_tz = df.groupby("player_id", sort=False)["tz_offset"].shift(1)
    df["tz_hours_crossed"] = (df["tz_offset"] - prev_tz).abs()
    df.loc[prev_tz.isna(), "tz_hours_crossed"] = 0.0

    df["started"] = df["started"].fillna(0).astype(float)
    df["is_home"] = (df["home_away"].astype(str).str.lower() == "home").astype(float)

    df = _teammate_availability(df, team_minutes)

    out_cols = KEY_COLUMNS + FEATURE_COLUMNS
    for c in out_cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[out_cols].copy()
