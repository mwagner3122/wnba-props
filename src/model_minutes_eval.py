"""Phase 5 minutes evaluation and DNP calibration reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import log_loss, mean_absolute_error

from src.model_minutes_core import (
    QUANTILES,
    MinutesModel,
    apply_team_renorm,
    interval_coverage,
    winkler_score,
)

def save_dnp_calibration(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    plot_path: Path,
    csv_path: Path,
) -> dict[str, Any]:
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    prob = np.clip(y_prob, 1e-6, 1 - 1e-6)
    ll = float(log_loss(y_true, prob))
    frac_pos, mean_pred = calibration_curve(y_true, prob, n_bins=10, strategy="quantile")
    cal_df = pd.DataFrame(
        {"mean_predicted_prob": mean_pred, "fraction_positives": frac_pos}
    )
    cal_df.to_csv(csv_path, index=False)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", label="perfect")
    ax.plot(mean_pred, frac_pos, "o-", label="DNP classifier")
    ax.set_xlabel("Mean predicted P(DNP)")
    ax.set_ylabel("Observed DNP rate")
    ax.set_title(f"DNP calibration (log loss={ll:.4f})")
    ax.legend(loc="upper left")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=120)
    plt.close(fig)
    return {"log_loss": ll, "n": int(len(y_true)), "base_rate": float(np.mean(y_true))}


def evaluate_minutes(
    model: MinutesModel,
    test: pd.DataFrame,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate on holdout.

    CRITICAL: continuous minutes metrics below use historical availability —
    the backtest KNOWS WHO PLAYED. That is not a true pregame projection.
    """
    regulation = float(cfg["regulation_team_minutes"])
    ot_m = float(cfg["ot_team_minutes"])

    print("", flush=True)
    print("=" * 72, flush=True)
    print(
        "BACKTEST KNOWS WHO PLAYED: continuous minutes MAE/coverage below "
        "are conditioned on historical availability (who actually played). "
        "This is NOT a true pregame result; the gap vs unknown lineup is large.",
        flush=True,
    )
    print("=" * 72, flush=True)

    p_dnp = model.predict_dnp_proba(test)
    dnp_stats = save_dnp_calibration(
        test["dnp"].to_numpy(),
        p_dnp,
        plot_path=Path(cfg["dnp_calibration_plot"]),
        csv_path=Path(cfg["dnp_calibration_csv"]),
    )
    print(
        f"DNP classifier log loss={dnp_stats['log_loss']:.4f} "
        f"(base rate={dnp_stats['base_rate']:.3f}, n={dnp_stats['n']})",
        flush=True,
    )
    print(
        f"Saved calibration plot -> {cfg['dnp_calibration_plot']} "
        f"and bins -> {cfg['dnp_calibration_csv']}",
        flush=True,
    )

    played = test[test["played"] == 1].copy()
    played["raw_med"] = model.predict_raw_median(played)
    for q in QUANTILES:
        played[f"raw_q{q}"] = model.predict_quantile_minutes(played, q)

    played = apply_team_renorm(
        played, "raw_med", "pred_med", regulation=regulation, ot_per_period=ot_m
    )
    for q in QUANTILES:
        raw = played[f"raw_q{q}"].clip(lower=0.1, upper=40.0)
        scale = np.where(
            played["raw_med"].clip(lower=0.1) > 0,
            played["pred_med"] / played["raw_med"].clip(lower=0.1),
            1.0,
        )
        played[f"pred_q{q}"] = (raw * scale).clip(0.0, 45.0)

    y = played["y_minutes"].to_numpy()
    pred = played["pred_med"].to_numpy()
    mae_model = float(mean_absolute_error(y, pred))
    t5 = played["trail5_minutes"].to_numpy()
    t5_fill = np.where(np.isfinite(t5), t5, np.nanmedian(t5))
    last = played["last_minutes"].to_numpy()
    last_fill = np.where(np.isfinite(last), last, t5_fill)
    mae_t5 = float(mean_absolute_error(y, t5_fill))
    mae_last = float(mean_absolute_error(y, last_fill))

    cov_quantile = {
        "50": interval_coverage(y, played["pred_q0.25"], played["pred_q0.75"]),
        "80": interval_coverage(y, played["pred_q0.1"], played["pred_q0.9"]),
        "95": interval_coverage(y, played["pred_q0.025"], played["pred_q0.975"]),
    }

    rq_m = model.model_residual_quantiles
    rq_t = model.trail5_residual_quantiles
    bands = {
        "50": (0.50, "q25", "q75"),
        "80": (0.20, "q10", "q90"),
        "95": (0.05, "q025", "q975"),
    }
    cov_model: dict[str, float] = {}
    cov_t5: dict[str, float] = {}
    wink_model: dict[str, float] = {}
    wink_t5: dict[str, float] = {}
    width_model: dict[str, float] = {}
    width_t5: dict[str, float] = {}
    for name, (alpha, lo_k, hi_k) in bands.items():
        m_lo, m_hi = pred + rq_m[lo_k], pred + rq_m[hi_k]
        t_lo, t_hi = t5_fill + rq_t[lo_k], t5_fill + rq_t[hi_k]
        cov_model[name] = interval_coverage(y, m_lo, m_hi)
        cov_t5[name] = interval_coverage(y, t_lo, t_hi)
        wink_model[name] = winkler_score(y, m_lo, m_hi, alpha)
        wink_t5[name] = winkler_score(y, t_lo, t_hi, alpha)
        width_model[name] = float(np.mean(m_hi - m_lo))
        width_t5[name] = float(np.mean(t_hi - t_lo))

    mean_wink_model = float(np.mean(list(wink_model.values())))
    mean_wink_t5 = float(np.mean(list(wink_t5.values())))

    full = test.copy()
    full["raw_med"] = model.predict_raw_median(full)
    full = apply_team_renorm(
        full, "raw_med", "pred_med", regulation=regulation, ot_per_period=ot_m
    )
    mae_known = float(
        mean_absolute_error(full["y_minutes"].to_numpy(), full["pred_med"].to_numpy())
    )
    t5_known = np.where(
        full["played"] == 1,
        np.where(np.isfinite(full["trail5_minutes"]), full["trail5_minutes"], 0.0),
        0.0,
    )
    mae_t5_known = float(mean_absolute_error(full["y_minutes"].to_numpy(), t5_known))

    beat_mae = mae_model < mae_t5
    beat_cov = mean_wink_model < mean_wink_t5
    beat_both = beat_mae and beat_cov

    print("", flush=True)
    print("=== Minutes comparison (PLAYED rows; known availability) ===", flush=True)
    print(
        f"{'model':20} {'MAE':>8} {'cov50':>8} {'cov80':>8} {'cov95':>8} "
        f"{'wink_mean':>10}",
        flush=True,
    )
    print("-" * 72, flush=True)
    print(
        f"{'minutes_model':20} {mae_model:8.3f} {cov_model['50']:8.3f} "
        f"{cov_model['80']:8.3f} {cov_model['95']:8.3f} {mean_wink_model:10.3f}",
        flush=True,
    )
    print(
        f"{'trailing_5_mean':20} {mae_t5:8.3f} {cov_t5['50']:8.3f} "
        f"{cov_t5['80']:8.3f} {cov_t5['95']:8.3f} {mean_wink_t5:10.3f}",
        flush=True,
    )
    print(
        f"{'last_game':20} {mae_last:8.3f} {'n/a':>8} {'n/a':>8} {'n/a':>8} "
        f"{'n/a':>10}",
        flush=True,
    )
    print("", flush=True)
    print(
        "Quantile-regression interval coverage (DoD; model only): "
        f"50%={cov_quantile['50']:.3f} 80%={cov_quantile['80']:.3f} "
        f"95%={cov_quantile['95']:.3f}",
        flush=True,
    )
    print(
        "Residual-band widths 50/80/95: "
        f"model={width_model['50']:.2f}/{width_model['80']:.2f}/{width_model['95']:.2f} "
        f"trail5={width_t5['50']:.2f}/{width_t5['80']:.2f}/{width_t5['95']:.2f}",
        flush=True,
    )
    print(
        f"Known-availability full-roster MAE: model={mae_known:.3f} "
        f"trailing_5={mae_t5_known:.3f}",
        flush=True,
    )
    print(f"Median prediction MAE (played): model={mae_model:.3f}", flush=True)

    if beat_both:
        print("", flush=True)
        print(
            "PASS vs trailing-5: model beats trailing-5 on BOTH MAE and coverage "
            f"(mean Winkler {mean_wink_model:.3f} < {mean_wink_t5:.3f}).",
            flush=True,
        )
        print(
            "Phase 5 complete. Stop for user gate — do NOT start phase 6.",
            flush=True,
        )
        status = "PASS"
    else:
        print("", flush=True)
        print(
            "FAIL vs trailing-5: model does NOT beat trailing-5 on BOTH MAE and "
            f"coverage (beat_mae={beat_mae}, beat_cov={beat_cov}).",
            flush=True,
        )
        print(
            "Phase 5 BLOCKED per AGENTS.md / build/05-minutes-model.md. "
            "Do NOT claim ready for phase 6.",
            flush=True,
        )
        status = "FAIL"

    return {
        "status": status,
        "beat_trailing5_mae": beat_mae,
        "beat_trailing5_coverage": beat_cov,
        "beat_trailing5_both": beat_both,
        "n_test": int(len(test)),
        "n_played": int(len(played)),
        "mae_median_played": mae_model,
        "mae_trailing5_played": mae_t5,
        "mae_last_played": mae_last,
        "mae_known_avail_model": mae_known,
        "mae_known_avail_trailing5": mae_t5_known,
        "coverage_residual_model": cov_model,
        "coverage_residual_trailing5": cov_t5,
        "coverage_quantile_model": cov_quantile,
        "winkler_model": wink_model,
        "winkler_trailing5": wink_t5,
        "mean_winkler_model": mean_wink_model,
        "mean_winkler_trailing5": mean_wink_t5,
        "width_model": width_model,
        "width_trailing5": width_t5,
        "dnp": dnp_stats,
        "share_method": cfg.get("share_method"),
        "train_end_season": cfg.get("train_end_season"),
        "test_start_season": cfg.get("test_start_season"),
        "backtest_knows_who_played": True,
    }
