"""Simulate team minutes shares with regulation / OT constraints."""

from __future__ import annotations

from typing import Sequence

import numpy as np


def team_minutes_budget(
    overtime_periods: int,
    *,
    regulation: float = 200.0,
    ot_per_period: float = 25.0,
    ot_event: bool | None = None,
) -> float:
    """
    Team player-minutes for a game.

    OT minutes are added ONLY after an explicit OT event (overtime_periods > 0
    or ot_event=True). Never add OT by default.
    """
    if ot_event is None:
        ot_event = int(overtime_periods or 0) > 0
    if not ot_event:
        return float(regulation)
    n_ot = max(int(overtime_periods or 0), 1)
    return float(regulation) + float(ot_per_period) * n_ot


def normalize_shares(raw: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    """Non-negative shares that sum to 1."""
    x = np.asarray(raw, dtype=float).copy()
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    x = np.clip(x, 0.0, None)
    s = x.sum()
    if s <= eps:
        return np.full(len(x), 1.0 / max(len(x), 1))
    return x / s


def minutes_from_shares(
    shares: np.ndarray,
    *,
    overtime_periods: int = 0,
    regulation: float = 200.0,
    ot_per_period: float = 25.0,
    ot_event: bool | None = None,
) -> np.ndarray:
    budget = team_minutes_budget(
        overtime_periods,
        regulation=regulation,
        ot_per_period=ot_per_period,
        ot_event=ot_event,
    )
    return normalize_shares(shares) * budget


def sample_dirichlet_minutes(
    expected_shares: Sequence[float],
    *,
    concentration: float = 40.0,
    n_draws: int = 1,
    overtime_periods: int = 0,
    regulation: float = 200.0,
    ot_per_period: float = 25.0,
    ot_event: bool | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Sample minutes for active players via Dirichlet on shares.

    Returns shape (n_draws, n_players). Each draw sums to the team budget.
    """
    rng = rng or np.random.default_rng()
    shares = normalize_shares(np.asarray(expected_shares, dtype=float))
    alpha = np.clip(shares * float(concentration), 1e-3, None)
    draws = rng.dirichlet(alpha, size=int(n_draws))
    budget = team_minutes_budget(
        overtime_periods,
        regulation=regulation,
        ot_per_period=ot_per_period,
        ot_event=ot_event,
    )
    return draws * budget


def sample_independent_normalize_minutes(
    expected_minutes: Sequence[float],
    residual_scale: float,
    *,
    n_draws: int = 1,
    overtime_periods: int = 0,
    regulation: float = 200.0,
    ot_per_period: float = 25.0,
    ot_event: bool | None = None,
    rng: np.random.Generator | None = None,
    favoritism: float = 0.0,
    starter_mask: np.ndarray | None = None,
) -> np.ndarray:
    """
    Independent Gaussian noise around expected minutes, then renormalize to budget.

    Heavy favorites (favoritism > 0) fatten the left tail for high-minute /
    starter-like players by applying negative skew via an extra downside shock.
    """
    rng = rng or np.random.default_rng()
    mu = np.asarray(expected_minutes, dtype=float)
    n = len(mu)
    noise = rng.normal(0.0, max(float(residual_scale), 0.5), size=(int(n_draws), n))
    if favoritism > 3.0 and n:
        # Extra left-tail mass for rotation players on heavy favorites.
        weight = starter_mask if starter_mask is not None else (mu >= np.median(mu))
        weight = np.asarray(weight, dtype=float)
        shock = -np.abs(rng.normal(0.0, 0.35 * favoritism, size=(int(n_draws), n)))
        noise = noise + shock * weight.reshape(1, -1)
    raw = np.clip(mu.reshape(1, -1) + noise, 0.1, 40.0)
    shares = raw / raw.sum(axis=1, keepdims=True)
    budget = team_minutes_budget(
        overtime_periods,
        regulation=regulation,
        ot_per_period=ot_per_period,
        ot_event=ot_event,
    )
    return shares * budget
