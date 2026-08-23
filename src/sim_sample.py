"""Sampling helpers for phase-7 simulation engine."""

from __future__ import annotations

import numpy as np

from src.minutes_sim import team_minutes_budget


def _normalize_rows(x: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    x = np.clip(np.asarray(x, dtype=float), 0.0, None)
    s = x.sum(axis=1, keepdims=True)
    s = np.where(s <= eps, 1.0, s)
    return x / s


def sample_pace(
    mu: float,
    sd: float,
    n_sim: int,
    rng: np.random.Generator,
    *,
    lo: float = 65.0,
    hi: float = 100.0,
) -> np.ndarray:
    draws = rng.normal(float(mu), max(float(sd), 0.1), size=int(n_sim))
    return np.clip(draws, lo, hi)


def _sample_makes_nb_beta(
    *,
    minutes: np.ndarray,
    rate_p40: np.ndarray,
    alpha: np.ndarray,
    beta: np.ndarray,
    opp: np.ndarray,
    scale: np.ndarray,
    nb_r: float,
    n_sim: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """NB attempts × Beta make% with full (n, n_sim) minutes/scale."""
    n = minutes.shape[0]
    mu = np.clip(
        rate_p40[:, None] * (minutes / 40.0) * opp[:, None] * scale,
        0.0,
        None,
    )
    r = max(float(nb_r), 1e-3)
    scale_g = np.where(mu > 0, mu / r, 0.0)
    lam = rng.gamma(shape=r, scale=scale_g)
    attempts = rng.poisson(lam)
    p = rng.beta(alpha[:, None], beta[:, None], size=(n, n_sim))
    makes = np.zeros((n, n_sim), dtype=np.int64)
    mask = attempts > 0
    makes[mask] = rng.binomial(attempts[mask], p[mask])
    return makes, attempts


def _sample_nb_counts(
    *,
    minutes: np.ndarray,
    rate_p40: np.ndarray,
    opp: np.ndarray,
    scale: np.ndarray,
    nb_r: float,
    n_sim: int,
    rng: np.random.Generator,
) -> np.ndarray:
    mu = np.clip(rate_p40[:, None] * (minutes / 40.0) * opp[:, None] * scale, 0.0, None)
    r = max(float(nb_r), 1e-3)
    scale_g = np.where(mu > 0, mu / r, 0.0)
    lam = rng.gamma(shape=r, scale=scale_g)
    return rng.poisson(lam)


def assert_minutes_budget(result: GameSimResult, cfg: dict[str, Any], atol: float = 1e-6) -> dict[str, Any]:
    """Sanity: each team minutes sum equals regulation (+OT only if ot_event)."""
    expected = team_minutes_budget(
        result.overtime_periods,
        regulation=float(cfg["regulation_team_minutes"]),
        ot_per_period=float(cfg["ot_team_minutes"]),
        ot_event=result.ot_event,
    )
    out = {"expected_budget": expected, "ot_event": result.ot_event, "teams": {}}
    ok = True
    for tid, sums in result.team_minutes_sums.items():
        mx = float(np.max(np.abs(sums - expected)))
        team_ok = bool(mx <= atol + 1e-9)
        ok = ok and team_ok
        out["teams"][tid] = {"max_abs_err": mx, "ok": team_ok, "mean": float(sums.mean())}
    out["ok"] = ok
    return out
