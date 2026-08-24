"""Summarize simulation draws: percentiles, mean/sd, P(stat >= k)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.sim_engine import GameSimResult, STAT_KEYS


def percentile_grid(draws: np.ndarray) -> dict[str, float]:
    """Percentiles at 1-unit intervals from floor(min) to ceil(max), plus mean/sd."""
    x = np.asarray(draws, dtype=float).ravel()
    lo = int(np.floor(np.min(x)))
    hi = int(np.ceil(np.max(x)))
    # Cap grid size for storage (wide count stats).
    if hi - lo > 80:
        qs = list(range(0, 101, 5))
        out = {f"p{q:02d}": float(np.percentile(x, q)) for q in qs}
    else:
        # CDF-style: for each integer k, store empirical quantile of the distribution
        # via percentile ranks at 1-unit value grid is awkward; store p01..p99 + mean/sd.
        qs = list(range(1, 100))
        out = {f"p{q:02d}": float(np.percentile(x, q)) for q in qs}
    out["mean"] = float(np.mean(x))
    out["sd"] = float(np.std(x, ddof=1)) if len(x) > 1 else 0.0
    out["min"] = float(np.min(x))
    out["max"] = float(np.max(x))
    return out


def summarize_game(result: GameSimResult, stats: list[str] | None = None) -> pd.DataFrame:
    stats = list(stats or [s for s in STAT_KEYS if s != "minutes"])
    rows = []
    for i, pid in enumerate(result.player_ids):
        for stat in stats:
            if stat not in result.draws:
                continue
            summ = percentile_grid(result.draws[stat][i, :])
            rows.append(
                {
                    "game_id": result.game_id,
                    "player_id": pid,
                    "player_name": result.player_names[i],
                    "team_id": result.team_ids[i],
                    "stat": stat,
                    "n_sim": result.n_sim,
                    "seed": result.seed,
                    **summ,
                }
            )
    return pd.DataFrame(rows)


def prob_ge_k(draws: np.ndarray, k: float) -> float:
    return float(np.mean(np.asarray(draws, dtype=float) >= float(k)))


def prob_table_for_player(
    result: GameSimResult,
    player_id: str,
    *,
    lines: dict[str, float],
    radius: int = 5,
) -> pd.DataFrame:
    """P(stat >= k) for k around each posted line."""
    try:
        i = result.player_ids.index(str(player_id))
    except ValueError:
        return pd.DataFrame()
    rows = []
    for stat, line in lines.items():
        if stat not in result.draws:
            continue
        center = float(line)
        # Whole-number props: evaluate at .5 lines and integers around center.
        ks = []
        base = int(np.floor(center))
        for d in range(-radius, radius + 1):
            ks.append(base + d + 0.5)
            ks.append(float(base + d))
        ks = sorted(set(ks))
        for k in ks:
            rows.append(
                {
                    "game_id": result.game_id,
                    "player_id": player_id,
                    "player_name": result.player_names[i],
                    "stat": stat,
                    "line": center,
                    "k": float(k),
                    "p_ge_k": prob_ge_k(result.draws[stat][i, :], k),
                    "n_sim": result.n_sim,
                    "seed": result.seed,
                }
            )
    return pd.DataFrame(rows)


def team_score_summary(result: GameSimResult) -> dict[str, Any]:
    out = {}
    for tid, pts in result.team_pts_sums.items():
        out[tid] = {
            "pts_mean": float(pts.mean()),
            "pts_sd": float(pts.std(ddof=1)),
            "pts_p10": float(np.percentile(pts, 10)),
            "pts_p50": float(np.percentile(pts, 50)),
            "pts_p90": float(np.percentile(pts, 90)),
            "reb_mean": float(result.team_reb_sums[tid].mean()),
            "reb_sd": float(result.team_reb_sums[tid].std(ddof=1)),
        }
    # Combined game total (sum of both teams).
    if len(result.team_pts_sums) >= 2:
        total = sum(result.team_pts_sums.values())
        out["_game_total"] = {
            "mean": float(total.mean()),
            "sd": float(total.std(ddof=1)),
            "p10": float(np.percentile(total, 10)),
            "p50": float(np.percentile(total, 50)),
            "p90": float(np.percentile(total, 90)),
        }
    return out
