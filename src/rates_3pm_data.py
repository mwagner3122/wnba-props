"""Load as-of frames and variance diagnostics for the 3PM rate model."""

from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from src.minutes_features import time_split  # re-use strict season split


def rates_3pm_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Tunables for 3PM hierarchical EB (all magic numbers from config)."""
    r = dict(cfg.get("rates_3pm") or {})
    minutes_cfg = cfg.get("minutes") or {}
    r.setdefault("train_end_season", minutes_cfg.get("train_end_season", 2024))
    r.setdefault("test_start_season", minutes_cfg.get("test_start_season", 2025))
    r.setdefault("p3_kappa_league", 200.0)
    r.setdefault("p3_kappa_role", 40.0)
    r.setdefault("pa_k_league", 80.0)
    r.setdefault("pa_k_role", 20.0)
    r.setdefault("opp_k", 25.0)
    r.setdefault("pa_nb_r_fallback", 4.0)
    r.setdefault("n_sim", 400)
    r.setdefault("random_state", 0)
    r.setdefault("models_dir", "models")
    r.setdefault("metrics_path", "reports/rates_3pm_metrics.json")
    r.setdefault("pit_histogram_path", "reports/rates_3pm_pit.png")
    r.setdefault("shrinkage_summary_path", "reports/rates_3pm_shrinkage.csv")
    r.setdefault("min_minutes_eval", 1.0)
    return r


def load_rates_3pm_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    """Join features + box score 3PA/3PM/minutes for rate modeling."""
    df = pd.read_sql_query(
        """
        SELECT
            f.game_id, f.player_id, f.game_date, f.season, f.team_id, f.opponent_id,
            f.position, f.fg3m_p40_l10, f.three_rate_std, f.games_played,
            f.player_form_prior_weight, f.opp_pace_shrunk, f.team_pace_shrunk,
            pg.minutes AS minutes, pg.fg3a AS fg3a, pg.fg3m AS fg3m, pg.fga AS fga,
            g.overtime_periods
        FROM player_game_features f
        JOIN player_games pg USING (game_id, player_id)
        JOIN games g ON g.game_id = f.game_id
        ORDER BY f.player_id, f.game_date, f.game_id
        """,
        conn,
    )
    for c in ("minutes", "fg3a", "fg3m", "fga"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["played"] = (df["minutes"] > 0).astype(int)
    df["position"] = df["position"].fillna("F").astype(str)
    df["role"] = df["position"].str.upper().str[0].map({"G": "G", "F": "F", "C": "C"}).fillna("F")
    return df


def add_asof_player_history(df: pd.DataFrame) -> pd.DataFrame:
    """Expanding as-of history (shift 1). Leakage-safe: game N never sees game N."""
    out = df.sort_values(["player_id", "game_date", "game_id"]).copy()
    g = out.groupby("player_id", sort=False)
    out["prior_fg3m"] = g["fg3m"].cumsum().shift(1).fillna(0.0)
    out["prior_fg3a"] = g["fg3a"].cumsum().shift(1).fillna(0.0)
    out["prior_minutes"] = g["minutes"].cumsum().shift(1).fillna(0.0)
    out["prior_games_played"] = g["played"].cumsum().shift(1).fillna(0.0)
    gs = out.groupby(["player_id", "season"], sort=False)
    out["std_fg3m"] = gs["fg3m"].cumsum().shift(1).fillna(0.0)
    out["std_fg3a"] = gs["fg3a"].cumsum().shift(1).fillna(0.0)
    out["std_minutes"] = gs["minutes"].cumsum().shift(1).fillna(0.0)
    out["l10_fg3m"] = g["fg3m"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).sum())
    out["l10_fg3a"] = g["fg3a"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).sum())
    out["l10_minutes"] = g["minutes"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).sum())
    for c in ("prior_fg3m", "prior_fg3a", "prior_minutes", "prior_games_played", "std_fg3m", "std_fg3a", "std_minutes", "l10_fg3m", "l10_fg3a", "l10_minutes"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    return out


def variance_to_mean_report(df: pd.DataFrame) -> dict[str, Any]:
    """Observed variance-to-mean ratios justifying Binomial(3PA, p3) + NB attempts."""
    played = df[df["minutes"] > 0].copy()
    report: dict[str, Any] = {"n_played": int(len(played))}

    def _vm(series: pd.Series, name: str) -> None:
        mu = float(series.mean())
        var = float(series.var(ddof=1)) if len(series) > 1 else float("nan")
        ratio = var / mu if mu > 0 else float("nan")
        report[name] = {"mean": mu, "var": var, "var_to_mean": ratio}

    _vm(played["fg3m"], "fg3m")
    _vm(played["fg3a"], "fg3a")
    played = played.copy()
    played["fg3a_p40"] = played["fg3a"] / played["minutes"].clip(lower=1e-6) * 40.0
    played["fg3m_p40"] = played["fg3m"] / played["minutes"].clip(lower=1e-6) * 40.0
    _vm(played["fg3a_p40"], "fg3a_p40")
    _vm(played["fg3m_p40"], "fg3m_p40")
    return report


def print_variance_to_mean(report: dict[str, Any]) -> None:
    print("", flush=True)
    print("=== Observed variance-to-mean (played rows; documents distribution) ===", flush=True)
    print(f"n_played={report['n_played']}", flush=True)
    for key in ("fg3m", "fg3a", "fg3m_p40", "fg3a_p40"):
        d = report[key]
        print(f"  {key:10} mean={d['mean']:.4f}  var={d['var']:.4f}  var/mean={d['var_to_mean']:.4f}", flush=True)
    print(
        "Interpretation: 3PA var/mean >> 1 → attempts overdispersed "
        "(NB for 3PA count, not Poisson). 3PM modeled as Binomial(3PA, p3) "
        "with Beta hierarchical p3 (EB), which induces extra 3PM overdispersion.",
        flush=True,
    )
