"""Distributional and binary scoring metrics for phase-9 evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def crps_from_samples(samples: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Empirical CRPS from Monte Carlo samples (lower is better)."""
    samples = np.asarray(samples, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    n, m = samples.shape
    term1 = np.mean(np.abs(samples - y[:, None]), axis=1)
    ordered = np.sort(samples, axis=1)
    idx = np.arange(1, m + 1)
    coef = 2 * idx - m - 1
    term2 = (2.0 / (m * m)) * (ordered * coef[None, :]).sum(axis=1)
    return term1 - 0.5 * term2


def pit_from_samples(samples: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Randomized PIT for discrete predictive samples."""
    samples = np.asarray(samples)
    y = np.asarray(y).astype(int)
    n, m = samples.shape
    lt = (samples < y[:, None]).sum(axis=1)
    eq = (samples == y[:, None]).sum(axis=1)
    u = rng.random(n)
    return (lt + u * eq) / float(m)


def interpret_pit(pits: np.ndarray, n_bins: int = 10, *, stat_name: str = "stat") -> dict[str, Any]:
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
            f"{direction} {stat_name} on average"
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


def save_pit_histogram(pits: np.ndarray, path: Path, *, title: str, interpretation: str) -> None:
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


def interval_coverage(samples: np.ndarray, y: np.ndarray, levels=(0.5, 0.8, 0.95)) -> dict[str, float]:
    """Empirical coverage of central predictive intervals."""
    samples = np.asarray(samples, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    out: dict[str, float] = {}
    for lev in levels:
        alpha = (1.0 - float(lev)) / 2.0
        lo = np.quantile(samples, alpha, axis=1)
        hi = np.quantile(samples, 1.0 - alpha, axis=1)
        out[f"coverage_{int(round(lev * 100))}"] = float(np.mean((y >= lo) & (y <= hi)))
    return out


def log_loss_binary(p: np.ndarray, y: np.ndarray, eps: float = 1e-6) -> float:
    p = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def brier_score(p: np.ndarray, y: np.ndarray) -> float:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.mean((p - y) ** 2))


def save_reliability_diagram(
    p: np.ndarray,
    y: np.ndarray,
    path: Path,
    *,
    title: str,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Bucket predicted P(over) and plot predicted vs observed frequency."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    centers = []
    obs = []
    counts = []
    for i in range(n_bins):
        mask = (p >= edges[i]) & (p < edges[i + 1] if i < n_bins - 1 else p <= edges[i + 1])
        if not np.any(mask):
            continue
        centers.append(float(np.mean(p[mask])))
        obs.append(float(np.mean(y[mask])))
        counts.append(int(mask.sum()))
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", label="perfect")
    if centers:
        ax.scatter(centers, obs, s=np.clip(np.array(counts) * 2, 20, 200), c="#4C72B0", zorder=3)
        ax.plot(centers, obs, color="#4C72B0", alpha=0.7)
    ax.set_xlabel("Predicted P(over)")
    ax.set_ylabel("Observed frequency")
    ax.set_title(title)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return {"bin_centers": centers, "observed": obs, "counts": counts, "path": str(path)}
