"""Edge, expected value vs best price, and (fractional) Kelly sizing."""

from __future__ import annotations

from src.pricing_odds import american_to_decimal


def edge(model_p: float, fair_p: float) -> float:
    """edge = model_p_over - fair_p_over."""
    return float(model_p) - float(fair_p)


def expected_value(model_p: float, american_odds: float) -> float:
    """EV per unit stake at the given American price: p*b - (1-p)."""
    b = american_to_decimal(american_odds) - 1.0
    p = float(model_p)
    return p * b - (1.0 - p)


def kelly_full(model_p: float, american_odds: float) -> float:
    """Full Kelly fraction f* = (p*b - (1-p)) / b; floored at 0."""
    b = american_to_decimal(american_odds) - 1.0
    if b <= 0:
        return 0.0
    p = float(model_p)
    f = (p * b - (1.0 - p)) / b
    return float(max(0.0, f))


def kelly_fractional(
    model_p: float,
    american_odds: float,
    fraction: float = 0.25,
) -> float:
    """Fractional Kelly (default quarter-Kelly)."""
    return float(fraction) * kelly_full(model_p, american_odds)


def apply_edge_floor(
    edge_value: float,
    stake: float,
    min_edge: float = 0.03,
) -> float:
    """Zero the stake when |edge| is below the configured floor."""
    if abs(float(edge_value)) < float(min_edge):
        return 0.0
    return float(stake)
