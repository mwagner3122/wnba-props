"""Load as-of frames and variance diagnostics for the assists rate model."""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from src.minutes_features import time_split  # noqa: F401 — re-exported for callers


def rates_ast_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Tunables for assists hierarchical EB NB (all magic numbers from config)."""
    r = dict(cfg.get("rates_ast") or {})
    minutes_cfg = cfg.get("minutes") or {}
    r.setdefault("train_end_season", minutes_cfg.get("train_end_season", 2024))
    r.setdefault("test_start_season", minutes_cfg.get("test_start_season", 2025))
    r.setdefault("ast_k_league", 80.0)
    r.setdefault("ast_k_role", 20.0)
    r.setdefault("opp_k", 25.0)
    r.setdefault("nb_r_fallback", 3.0)
    r.setdefault("n_sim", 400)
    r.setdefault("random_state", 0)
    r.setdefault("models_dir", "models")
    r.setdefault("metrics_path", "reports/rates_ast_metrics.json")
    r.setdefault("pit_histogram_path", "reports/rates_ast_pit.png")
    r.setdefault("shrinkage_summary_path", "reports/rates_ast_shrinkage.csv")
    r.setdefault("min_minutes_eval", 1.0)
    return r


def load_rates_ast_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    """Join features + box score ast/minutes for rate modeling."""
    df = pd.read_sql_query(
        """
        SELECT
            f.game_id, f.player_id, f.game_date, f.season, f.team_id, f.opponent_id,
            f.position, f.ast_p40_l10, f.ast_p40_std, f.games_played,
            f.player_form_prior_weight, f.opp_pace_shrunk, f.team_pace_shrunk,
            pg.minutes AS minutes, pg.ast AS ast,
            g.overtime_periods
        FROM player_game_features f
        JOIN player_games pg USING (game_id, player_id)
        JOIN games g ON g.game_id = f.game_id
        ORDER BY f.player_id, f.game_date, f.game_id
        """,
        conn,
    )
    for c in ("minutes", "ast"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["played"] = (df["minutes"] > 0).astype(int)
    df["position"] = df["position"].fillna("F").astype(str)
    df["role"] = df["position"].str.upper().str[0].map({"G": "G", "F": "F", "C": "C"}).fillna("F")
    return df


def add_asof_player_history(df: pd.DataFrame) -> pd.DataFrame:
    """Expanding as-of history (shift 1). Leakage-safe: game N never sees game N."""
    out = df.sort_values(["player_id", "game_date", "game_id"]).copy()
    g = out.groupby("player_id", sort=False)
    out["prior_ast"] = g["ast"].cumsum().shift(1).fillna(0.0)
    out["prior_minutes"] = g["minutes"].cumsum().shift(1).fillna(0.0)
    out["prior_games_played"] = g["played"].cumsum().shift(1).fillna(0.0)
    gs = out.groupby(["player_id", "season"], sort=False)
    out["std_ast"] = gs["ast"].cumsum().shift(1).fillna(0.0)
    out["std_minutes"] = gs["minutes"].cumsum().shift(1).fillna(0.0)
    out["l10_ast"] = g["ast"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).sum())
    out["l10_minutes"] = g["minutes"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).sum())
    for c in (
        "prior_ast",
        "prior_minutes",
        "prior_games_played",
        "std_ast",
        "std_minutes",
        "l10_ast",
        "l10_minutes",
    ):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    return out


def variance_to_mean_report(df: pd.DataFrame) -> dict[str, Any]:
    """Observed variance-to-mean ratios justifying NegativeBinomial (not Poisson)."""
    played = df[df["minutes"] > 0].copy()
    report: dict[str, Any] = {"n_played": int(len(played))}

    def _vm(series: pd.Series, name: str) -> None:
        mu = float(series.mean())
        var = float(series.var(ddof=1)) if len(series) > 1 else float("nan")
        ratio = var / mu if mu > 0 else float("nan")
        report[name] = {"mean": mu, "var": var, "var_to_mean": ratio}

    _vm(played["ast"], "ast")
    played = played.copy()
    played["ast_p40"] = played["ast"] / played["minutes"].clip(lower=1e-6) * 40.0
    _vm(played["ast_p40"], "ast_p40")
    return report


def print_variance_to_mean(report: dict[str, Any]) -> None:
    print("", flush=True)
    print("=== Observed variance-to-mean (played rows; justifies NB vs Poisson) ===", flush=True)
    print(f"n_played={report['n_played']}", flush=True)
    for key in ("ast", "ast_p40"):
        d = report[key]
        print(
            f"  {key:10} mean={d['mean']:.4f}  var={d['var']:.4f}  var/mean={d['var_to_mean']:.4f}",
            flush=True,
        )
    ratio = report["ast"]["var_to_mean"]
    if ratio is not None and ratio == ratio and abs(ratio - 1.0) < 0.15:
        print(
            f"WARNING: ast var/mean={ratio:.3f} is near 1 — Poisson might suffice; "
            "reconsider NB. Proceeding with NB per phase-6 spec (expect overdispersion).",
            flush=True,
        )
    else:
        print(
            f"Interpretation: ast var/mean={ratio:.3f} "
            f"{'>>' if (ratio or 0) > 1.2 else '~'} 1 → overdispersed counts. "
            "Use NegativeBinomial (NOT Poisson). Poisson would understate variance "
            "and make low lines look like automatic overs.",
            flush=True,
        )
