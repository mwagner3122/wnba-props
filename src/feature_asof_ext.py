"""As-of league/team/teammate helpers (phase 4)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.feature_asof_core import (
    _shift_expanding,
)

def _build_league_asof(games: pd.DataFrame) -> pd.DataFrame:
    g = games.sort_values(["season", "game_ord"], kind="mergesort").copy()
    g["_pace"] = g["pace"].astype(float)
    g["_off_sum"] = g["home_off_rating"].astype(float) + g["away_off_rating"].astype(float)
    pieces: list[pd.DataFrame] = []
    for season, sub in g.groupby("season", sort=False):
        sub = sub.copy()
        n = np.arange(len(sub), dtype=float)
        pace_cs = sub["_pace"].cumsum().shift(1)
        off_cs = sub["_off_sum"].cumsum().shift(1)
        pieces.append(
            pd.DataFrame(
                {
                    "season": int(season),
                    "game_ord": sub["game_ord"].to_numpy(),
                    "league_pace_asof": pace_cs.to_numpy() / np.where(n > 0, n, np.nan),
                    "league_off_asof": off_cs.to_numpy() / np.where(n > 0, 2 * n, np.nan),
                    "league_def_asof": off_cs.to_numpy() / np.where(n > 0, 2 * n, np.nan),
                }
            )
        )
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(
        columns=[
            "season",
            "game_ord",
            "league_pace_asof",
            "league_off_asof",
            "league_def_asof",
        ]
    )


def _team_asof_frame(games: pd.DataFrame, league: pd.DataFrame) -> pd.DataFrame:
    home = pd.DataFrame(
        {
            "game_id": games["game_id"].astype(str),
            "game_date": games["game_date"],
            "game_ord": games["game_ord"],
            "season": games["season"],
            "team_id": games["home_team_id"].astype(str),
            "pace": games["pace"].astype(float),
            "off_rtg": games["home_off_rating"].astype(float),
            "def_rtg": games["away_off_rating"].astype(float),
        }
    )
    away = pd.DataFrame(
        {
            "game_id": games["game_id"].astype(str),
            "game_date": games["game_date"],
            "game_ord": games["game_ord"],
            "season": games["season"],
            "team_id": games["away_team_id"].astype(str),
            "pace": games["pace"].astype(float),
            "off_rtg": games["away_off_rating"].astype(float),
            "def_rtg": games["home_off_rating"].astype(float),
        }
    )
    tg = pd.concat([home, away], ignore_index=True)
    tg = tg.sort_values(["team_id", "season", "game_ord"], kind="mergesort").reset_index(
        drop=True
    )
    key = tg["team_id"].astype(str) + "|" + tg["season"].astype(str)
    tg["team_games_played"] = tg.groupby(key, sort=False).cumcount()
    for c in ("pace", "off_rtg", "def_rtg"):
        tg[f"{c}_asof"] = _shift_expanding(tg[c], key)
    tg = tg.merge(league, on=["season", "game_ord"], how="left")
    return tg


def _position_form_priors(df: pd.DataFrame) -> pd.DataFrame:
    played = df.loc[
        df["minutes"].fillna(0) > 0,
        ["season", "game_ord", "position", "pts_p40", "reb_p40", "ast_p40", "fg3m_p40"],
    ].copy()
    pieces: list[pd.DataFrame] = []
    for (season, pos), sub in played.groupby(["season", "position"], sort=False):
        agg = (
            sub.groupby("game_ord", sort=True)
            .agg(
                pts=("pts_p40", "sum"),
                reb=("reb_p40", "sum"),
                ast=("ast_p40", "sum"),
                fg3=("fg3m_p40", "sum"),
                n=("pts_p40", "size"),
            )
            .reset_index()
        )
        for col in ("pts", "reb", "ast", "fg3", "n"):
            agg[f"sum_{col}"] = agg[col].cumsum().shift(1)
        nsum = agg["sum_n"]
        pieces.append(
            pd.DataFrame(
                {
                    "season": season,
                    "game_ord": agg["game_ord"],
                    "position": pos,
                    "prior_pts_p40": agg["sum_pts"] / nsum,
                    "prior_reb_p40": agg["sum_reb"] / nsum,
                    "prior_ast_p40": agg["sum_ast"] / nsum,
                    "prior_fg3m_p40": agg["sum_fg3"] / nsum,
                }
            )
        )
    if not pieces:
        return pd.DataFrame(
            columns=[
                "season",
                "game_ord",
                "position",
                "prior_pts_p40",
                "prior_reb_p40",
                "prior_ast_p40",
                "prior_fg3m_p40",
            ]
        )
    return pd.concat(pieces, ignore_index=True)


def _positional_defense_asof(df: pd.DataFrame) -> pd.DataFrame:
    played = df.loc[
        df["minutes"].fillna(0) > 0,
        ["game_ord", "season", "opponent_id", "position", "pts_p40"],
    ].copy()
    played = played.rename(columns={"opponent_id": "def_team_id"})
    pieces: list[pd.DataFrame] = []
    for (season, def_team, pos), sub in played.groupby(
        ["season", "def_team_id", "position"], sort=False
    ):
        agg = (
            sub.groupby("game_ord", sort=True)
            .agg(allowed=("pts_p40", "sum"), n=("pts_p40", "size"))
            .reset_index()
        )
        agg["sum_c"] = agg["allowed"].cumsum().shift(1)
        agg["sum_n"] = agg["n"].cumsum().shift(1)
        pieces.append(
            pd.DataFrame(
                {
                    "season": season,
                    "game_ord": agg["game_ord"],
                    "opponent_id": def_team,
                    "position": pos,
                    "pos_def_asof": agg["sum_c"] / agg["sum_n"],
                    "pos_def_n": agg["sum_n"].fillna(0),
                }
            )
        )
    if not pieces:
        return pd.DataFrame(
            columns=[
                "season",
                "game_ord",
                "opponent_id",
                "position",
                "pos_def_asof",
                "pos_def_n",
            ]
        )
    return pd.concat(pieces, ignore_index=True)


def _teammate_availability(df: pd.DataFrame, team_minutes: float) -> pd.DataFrame:
    df = df.copy()
    df["_usual_min"] = df["minutes_share_l5"].fillna(0.0) * team_minutes
    df["_is_out"] = (
        (df["minutes"].fillna(0) <= 0) | df["dnp_reason"].notna()
    ).astype(int)
    df["_out_usual"] = df["_usual_min"] * df["_is_out"]
    g = df.groupby(["game_id", "team_id"], sort=False)
    total_vac = g["_out_usual"].transform("sum")
    df["minutes_vacated"] = total_vac - df["_out_usual"]

    # Same-position vacated excluding self
    gpos = df.groupby(["game_id", "team_id", "position"], sort=False)
    pos_vac = gpos["_out_usual"].transform("sum")
    df["same_pos_minutes_vacated"] = pos_vac - df["_out_usual"]

    # Primary ball-handler: max usage among teammates with games_played > 0
    df["_usage_key"] = np.where(
        df["games_played"] > 0, df["usage_rate_shrunk"].fillna(-1.0), -1.0
    )
    bh_idx = g["_usage_key"].transform("idxmax")
    bh_player = df.loc[bh_idx.to_numpy(), "player_id"].to_numpy()
    bh_out_flag = df.loc[bh_idx.to_numpy(), "_is_out"].to_numpy(dtype=float)
    is_self_bh = df["player_id"].to_numpy() == bh_player
    df["primary_bh_out"] = np.where(is_self_bh, 0.0, bh_out_flag)
    no_bh = g["_usage_key"].transform("max") < 0
    df.loc[no_bh, "primary_bh_out"] = 0.0
    return df
