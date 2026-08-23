"""CRPS / PIT / baseline evaluation for the assists NB rate model."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.rates_ast_model import RatesAstModel


def crps_from_samples(samples, y):
    samples = np.asarray(samples, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    n, m = samples.shape
    term1 = np.mean(np.abs(samples - y[:, None]), axis=1)
    ordered = np.sort(samples, axis=1)
    idx = np.arange(1, m + 1)
    coef = 2 * idx - m - 1
    term2 = (2.0 / (m * m)) * (ordered * coef[None, :]).sum(axis=1)
    return term1 - 0.5 * term2


def pit_from_samples(samples, y, rng):
    samples = np.asarray(samples)
    y = np.asarray(y).astype(int)
    n, m = samples.shape
    lt = (samples < y[:, None]).sum(axis=1)
    eq = (samples == y[:, None]).sum(axis=1)
    u = rng.random(n)
    return (lt + u * eq) / float(m)


def interpret_pit(pits, n_bins=10):
    hist, edges = np.histogram(pits, bins=n_bins, range=(0.0, 1.0), density=True)
    left = float(np.mean(hist[:3]))
    mid = float(np.mean(hist[3:7]))
    right = float(np.mean(hist[7:]))
    slope = (
        float(np.corrcoef(np.arange(n_bins, dtype=float), hist)[0, 1])
        if np.std(hist) > 0
        else 0.0
    )
    max_dev = float(np.max(np.abs(hist - 1.0)))
    if max_dev < 0.25 and abs(slope) < 0.35:
        shape, words = (
            "flat",
            "approximately flat -- calibrated (no strong over/under-confidence or systematic bias)",
        )
    elif left > mid * 1.15 and right > mid * 1.15:
        shape, words = (
            "U-shaped",
            "U-shaped -- too many outcomes in the tails; distributions are too narrow (overconfident)",
        )
    elif mid > left * 1.15 and mid > right * 1.15:
        shape, words = (
            "peaked",
            "peaked in the middle -- distributions are too wide (underconfident)",
        )
    elif abs(slope) >= 0.35:
        shape = "sloped"
        direction = "over-projecting" if slope < 0 else "under-projecting"
        words = (
            f"sloped (corr={slope:.2f}) -- systematic bias; model appears "
            f"{direction} assists on average"
        )
    else:
        shape, words = (
            "mildly irregular",
            f"mildly irregular (max |density-1|={max_dev:.2f}); not a clean U/peak/slope pattern",
        )
    return {
        "shape": shape,
        "interpretation": words,
        "hist_density": hist.tolist(),
        "bin_edges": edges.tolist(),
        "left_mean_density": left,
        "mid_mean_density": mid,
        "right_mean_density": right,
        "slope_corr": slope,
        "max_abs_dev_from_1": max_dev,
    }


def save_pit_histogram(pits, path, *, title, interpretation):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(pits, bins=10, range=(0, 1), density=True, color="#4C72B0", edgecolor="white")
    ax.axhline(1.0, color="k", linestyle="--", linewidth=1, label="perfect flat")
    ax.set_xlabel("PIT value")
    ax.set_ylabel("Density")
    ax.set_title(title)
    ax.legend(loc="upper right")
    fig.text(0.02, 0.02, interpretation, fontsize=8, wrap=True)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _baseline_samples_rate_x_minutes(
    minutes, hist_ast, hist_minutes, *, n_sim, rng, league_ast_p40, nb_r
):
    n = len(minutes)
    ast_p40 = np.where(
        hist_minutes > 0,
        (hist_ast / np.maximum(hist_minutes, 1e-9)) * 40.0,
        league_ast_p40,
    )
    mu = np.clip(ast_p40 * (minutes / 40.0), 0.0, None)
    r = max(float(nb_r), 1e-3)
    scale = np.where(mu > 0, mu / r, 0.0)
    lam = rng.gamma(shape=r, scale=scale[:, None], size=(n, n_sim))
    return rng.poisson(lam)


def evaluate_ast(model: RatesAstModel, test: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    min_m = float(cfg["min_minutes_eval"])
    eval_df = test[test["minutes"] >= min_m].copy()
    print("", flush=True)
    print("=" * 72, flush=True)
    print(
        "AST BACKTEST CONDITIONS ON REALIZED MINUTES (rate model only). "
        "Full minutes uncertainty is phase 7 simulation -- not applied here.",
        flush=True,
    )
    print("=" * 72, flush=True)
    print(
        f"Eval rows: {len(eval_df)} (minutes>={min_m}); "
        f"test seasons>={cfg['test_start_season']}",
        flush=True,
    )
    params = model.predict_params(eval_df)
    rng = np.random.default_rng(int(cfg["random_state"]))
    n_sim = int(cfg["n_sim"])
    y = params["ast"].to_numpy(dtype=float)
    minutes = params["minutes"].to_numpy(dtype=float)
    model_samples = model.sample_ast(
        minutes,
        params["ast_p40"].to_numpy(dtype=float),
        params["opp_ast_factor"].to_numpy(dtype=float),
        n_sim=n_sim,
        rng=rng,
    )
    std_samples = _baseline_samples_rate_x_minutes(
        minutes,
        params["std_ast"].to_numpy(dtype=float),
        params["std_minutes"].to_numpy(dtype=float),
        n_sim=n_sim,
        rng=rng,
        league_ast_p40=model.league_ast_p40,
        nb_r=model.nb_r,
    )
    l10_samples = _baseline_samples_rate_x_minutes(
        minutes,
        params["l10_ast"].to_numpy(dtype=float),
        params["l10_minutes"].to_numpy(dtype=float),
        n_sim=n_sim,
        rng=rng,
        league_ast_p40=model.league_ast_p40,
        nb_r=model.nb_r,
    )
    crps_model = crps_from_samples(model_samples, y)
    crps_std = crps_from_samples(std_samples, y)
    crps_l10 = crps_from_samples(l10_samples, y)
    pits = pit_from_samples(model_samples, y, rng)
    pit_info = interpret_pit(pits)
    pit_path = Path(cfg["pit_histogram_path"])
    save_pit_histogram(
        pits,
        pit_path,
        title=f"Assists PIT histogram (n={len(pits)})",
        interpretation=pit_info["interpretation"],
    )
    mean_crps_model = float(np.mean(crps_model))
    mean_crps_std = float(np.mean(crps_std))
    mean_crps_l10 = float(np.mean(crps_l10))
    mae_model = float(np.mean(np.abs(model_samples.mean(axis=1) - y)))
    mae_std = float(np.mean(np.abs(std_samples.mean(axis=1) - y)))
    mae_l10 = float(np.mean(np.abs(l10_samples.mean(axis=1) - y)))
    print("", flush=True)
    print("=== Assists holdout comparison (CRPS lower is better) ===", flush=True)
    print(f"{'model':24} {'CRPS':>10} {'MAE_mean':>10}", flush=True)
    print("-" * 48, flush=True)
    print(f"{'hier_EB_negbin':24} {mean_crps_model:10.4f} {mae_model:10.4f}", flush=True)
    print(f"{'season_to_date_rate':24} {mean_crps_std:10.4f} {mae_std:10.4f}", flush=True)
    print(f"{'trailing_10_rate':24} {mean_crps_l10:10.4f} {mae_l10:10.4f}", flush=True)
    beat_std = mean_crps_model < mean_crps_std
    beat_l10 = mean_crps_model < mean_crps_l10
    print(
        f"Beats season-to-date CRPS: {beat_std}; beats trailing-10 CRPS: {beat_l10}",
        flush=True,
    )
    print("", flush=True)
    print(f"PIT shape: {pit_info['shape']} -- {pit_info['interpretation']}", flush=True)
    print(f"Saved PIT histogram -> {pit_path}", flush=True)
    print("", flush=True)
    print("=== Opponent ast-allowed factors (TEAM level only) ===", flush=True)
    print(
        "No player-vs-team interactions (sample size would be a handful of games).",
        flush=True,
    )
    opp_rows = sorted(
        (
            (oid, model.opp_ast_factor[oid], model.opp_sample_size[oid])
            for oid in model.opp_ast_factor
        ),
        key=lambda t: -t[2],
    )
    print(f"{'opp_id':12} {'factor':>8} {'n_games':>8}", flush=True)
    for oid, fac, n_g in opp_rows[:15]:
        print(f"{oid:12} {fac:8.3f} {n_g:8d}", flush=True)
    return {
        "n_eval": int(len(eval_df)),
        "crps_model": mean_crps_model,
        "crps_season_to_date": mean_crps_std,
        "crps_trailing_10": mean_crps_l10,
        "mae_model": mae_model,
        "mae_season_to_date": mae_std,
        "mae_trailing_10": mae_l10,
        "beat_season_to_date_crps": beat_std,
        "beat_trailing_10_crps": beat_l10,
        "pit": pit_info,
        "pit_histogram_path": str(pit_path),
        "nb_r": float(model.nb_r),
        "league_ast_p40": float(model.league_ast_p40),
        "role_ast_p40": dict(model.role_ast_p40),
        "ast_k_role": float(model.ast_k_role),
        "opp_k": float(model.opp_k),
        "opp_n_teams": len(model.opp_ast_factor),
        "opp_games_min": int(min(model.opp_sample_size.values())) if model.opp_sample_size else 0,
        "opp_games_max": int(max(model.opp_sample_size.values())) if model.opp_sample_size else 0,
        "opp_games_median": (
            float(np.median(list(model.opp_sample_size.values())))
            if model.opp_sample_size
            else 0.0
        ),
        "conditioned_on_realized_minutes": True,
        "distribution": "NegativeBinomial",
    }
