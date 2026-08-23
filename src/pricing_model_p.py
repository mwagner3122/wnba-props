"""Model P(over) for today's slate via Phase-7 joint simulation on projected rosters."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.clean_prep import _team_name_to_id
from src.name_normalize import normalize_name
from src.sim_engine import GameSimResult, simulate_game
from src.sim_roster import load_game_roster
from src.sim_summarize import prob_ge_k


def _latest_game_for_team(conn, team_id: str, season: int) -> str | None:
    row = conn.execute(
        """
        SELECT g.game_id
        FROM games g
        JOIN player_games pg ON pg.game_id = g.game_id
        WHERE g.season = ?
          AND (g.home_team_id = ? OR g.away_team_id = ?)
          AND pg.team_id = ?
          AND pg.minutes > 0
        ORDER BY g.game_date DESC
        LIMIT 1
        """,
        (int(season), str(team_id), str(team_id), str(team_id)),
    ).fetchone()
    return None if row is None else str(row["game_id"])


def _odds_event_teams(conn, odds_game_id: str) -> tuple[str | None, str | None]:
    row = conn.execute(
        "SELECT home_team, away_team FROM odds_events WHERE odds_game_id = ?",
        (str(odds_game_id),),
    ).fetchone()
    if row is None:
        return None, None
    team_map = _team_name_to_id(conn)
    home = team_map.get(normalize_name(str(row["home_team"] or "")))
    away = team_map.get(normalize_name(str(row["away_team"] or "")))
    return home, away


def _apply_opponent_factors(
    roster: pd.DataFrame,
    *,
    opponent_id: str,
    model_3pm: Any,
    model_reb: Any,
    model_ast: Any,
) -> pd.DataFrame:
    out = roster.copy()
    out["opponent_id"] = str(opponent_id)
    fac3, _ = model_3pm.opp_factor(opponent_id)
    facr, _ = model_reb.opp_factor(opponent_id)
    faca, _ = model_ast.opp_factor(opponent_id)
    out["opp_pa_factor"] = float(fac3)
    out["opp_reb_factor"] = float(facr)
    out["opp_ast_factor"] = float(faca)
    return out


def build_projection_roster(
    conn,
    odds_game_id: str,
    *,
    season: int,
    model_3pm: Any,
    model_reb: Any,
    model_ast: Any,
    model_fg2ft: Any,
    minutes_model: Any,
) -> pd.DataFrame | None:
    """
    Stitch each side's most recent completed-game roster, remap opponent factors.

    Explicit honesty: BACKTEST/PROJECTION USES LAST PLAYED ROSTER -- not true
    pregame availability (phase 10).
    """
    home_id, away_id = _odds_event_teams(conn, odds_game_id)
    if not home_id or not away_id:
        return None
    home_gid = _latest_game_for_team(conn, home_id, season)
    away_gid = _latest_game_for_team(conn, away_id, season)
    if not home_gid or not away_gid:
        return None

    def _side(game_id: str, team_id: str, opp_id: str) -> pd.DataFrame:
        full = load_game_roster(
            conn,
            game_id,
            model_3pm=model_3pm,
            model_reb=model_reb,
            model_ast=model_ast,
            model_fg2ft=model_fg2ft,
            minutes_model=minutes_model,
            played_only=True,
        )
        side = full[full["team_id"].astype(str) == str(team_id)].copy()
        if side.empty:
            raise ValueError(f"no roster rows for team {team_id} in game {game_id}")
        side = _apply_opponent_factors(
            side,
            opponent_id=opp_id,
            model_3pm=model_3pm,
            model_reb=model_reb,
            model_ast=model_ast,
        )
        # Renormalize minutes shares within the side after filter.
        raw = side["expected_minutes_share"].fillna(0.0).clip(lower=0.01)
        side["expected_minutes_share"] = raw / raw.sum()
        side["game_id"] = str(odds_game_id)
        return side

    home = _side(home_gid, home_id, away_id)
    away = _side(away_gid, away_id, home_id)
    # Cross-fill pace so both sides see the matchup.
    hp = float(home["team_pace_shrunk"].dropna().mean()) if home["team_pace_shrunk"].notna().any() else 80.0
    ap = float(away["team_pace_shrunk"].dropna().mean()) if away["team_pace_shrunk"].notna().any() else 80.0
    home["opp_pace_shrunk"] = ap
    away["opp_pace_shrunk"] = hp
    home["team_pace_shrunk"] = hp
    away["team_pace_shrunk"] = ap
    return pd.concat([home, away], ignore_index=True)


def p_over_from_draws(draws: np.ndarray, line: float) -> float:
    """P(stat > line). For .5 lines on integer stats this is P(stat >= ceil(line))."""
    return float(np.mean(np.asarray(draws, dtype=float) > float(line)))


def simulate_odds_game(
    roster: pd.DataFrame,
    *,
    model_3pm: Any,
    model_reb: Any,
    model_ast: Any,
    model_fg2ft: Any,
    cfg: dict[str, Any],
    rng: np.random.Generator,
) -> GameSimResult:
    paces = []
    for tid, sub in roster.groupby("team_id"):
        tp = sub["team_pace_shrunk"].dropna()
        op = sub["opp_pace_shrunk"].dropna()
        if not tp.empty and not op.empty:
            paces.append(0.5 * (float(tp.mean()) + float(op.mean())))
    pace_mu = float(np.mean(paces)) if paces else float(cfg.get("league_pace_anchor", 80.0))
    return simulate_game(
        roster,
        model_3pm=model_3pm,
        model_reb=model_reb,
        model_ast=model_ast,
        model_fg2ft=model_fg2ft,
        cfg=cfg,
        rng=rng,
        ot_event=False,
        overtime_periods=0,
        pace_mu=pace_mu,
    )


def model_p_over_table(
    result: GameSimResult,
    markets: pd.DataFrame,
    market_stat_map: dict[str, str],
) -> pd.DataFrame:
    """Attach model_p_over for each market row that maps to a sim stat."""
    id_to_idx = {pid: i for i, pid in enumerate(result.player_ids)}
    rows = []
    for r in markets.itertuples(index=False):
        stat = market_stat_map.get(str(r.market))
        pid = str(r.player_id)
        ogid = getattr(r, "odds_game_id", None)
        if stat is None or stat not in result.draws or pid not in id_to_idx:
            rows.append(
                {
                    "odds_game_id": ogid,
                    "player_id": pid,
                    "market": r.market,
                    "line": float(r.line),
                    "model_p_over": np.nan,
                    "model_p_status": "missing_player_or_stat",
                }
            )
            continue
        i = id_to_idx[pid]
        p = p_over_from_draws(result.draws[stat][i, :], float(r.line))
        # Also record P(stat >= line) for .5-line sanity (equals p_over when line=*.5).
        p_ge = prob_ge_k(result.draws[stat][i, :], float(r.line) + 0.5)
        rows.append(
            {
                "odds_game_id": ogid,
                "player_id": pid,
                "market": r.market,
                "line": float(r.line),
                "model_p_over": p,
                "model_p_ge_line_plus_half": p_ge,
                "model_p_status": "ok",
                "stat": stat,
            }
        )
    return pd.DataFrame(rows)
