"""Phase 8: American odds, hold, de-vig (mult+power), Kelly, edge floor."""

from __future__ import annotations

import unittest

from src.pricing_kelly import (
    apply_edge_floor,
    edge,
    expected_value,
    kelly_fractional,
    kelly_full,
)
from src.pricing_odds import (
    american_to_decimal,
    american_to_implied,
    devig_multiplicative,
    devig_power,
    hold,
    two_way_market_report,
)


class TestPricingOdds(unittest.TestCase):
    def test_american_implied_negative(self):
        # -115 -> 115/215
        self.assertAlmostEqual(american_to_implied(-115), 115 / 215, places=12)

    def test_american_implied_positive(self):
        self.assertAlmostEqual(american_to_implied(100), 0.5, places=12)
        self.assertAlmostEqual(american_to_implied(190), 100 / 290, places=12)

    def test_hold_minus_115_both_sides(self):
        q = american_to_implied(-115)
        self.assertAlmostEqual(hold(q, q), 2 * (115 / 215) - 1, places=10)
        # Spec: ~7% hold
        self.assertAlmostEqual(hold(q, q), 0.06976744186, places=8)

    def test_multiplicative_balanced(self):
        q = american_to_implied(-115)
        p_o, p_u = devig_multiplicative(q, q)
        self.assertAlmostEqual(p_o, 0.5, places=12)
        self.assertAlmostEqual(p_u, 0.5, places=12)

    def test_power_balanced_matches_multiplicative(self):
        q = american_to_implied(-115)
        m_o, m_u = devig_multiplicative(q, q)
        p_o, p_u = devig_power(q, q)
        self.assertAlmostEqual(p_o, m_o, places=6)
        self.assertAlmostEqual(p_u, m_u, places=6)

    def test_power_lopsided_diverges(self):
        # -250 / +190
        qo = american_to_implied(-250)
        qu = american_to_implied(190)
        m_o, _ = devig_multiplicative(qo, qu)
        p_o, p_u = devig_power(qo, qu)
        self.assertAlmostEqual(p_o + p_u, 1.0, places=10)
        # Power should not equal multiplicative on a lopsided market.
        self.assertGreater(abs(p_o - m_o), 1e-4)

    def test_two_way_report_has_both_methods(self):
        rep = two_way_market_report(-115, -115)
        self.assertIn("hold", rep)
        self.assertIn("fair_over_multiplicative", rep)
        self.assertIn("fair_over_power", rep)
        self.assertAlmostEqual(rep["fair_over_multiplicative"], 0.5, places=8)


class TestPricingKelly(unittest.TestCase):
    def test_edge_and_ev(self):
        self.assertAlmostEqual(edge(0.55, 0.50), 0.05, places=12)
        # Even money +100, p=0.55 -> EV = 0.55*1 - 0.45 = 0.10
        self.assertAlmostEqual(expected_value(0.55, 100), 0.10, places=12)

    def test_kelly_even_money(self):
        # p=0.55, b=1 -> f* = 0.10
        self.assertAlmostEqual(kelly_full(0.55, 100), 0.10, places=12)
        self.assertAlmostEqual(kelly_fractional(0.55, 100, 0.25), 0.025, places=12)

    def test_kelly_zero_when_no_edge(self):
        self.assertEqual(kelly_full(0.45, 100), 0.0)

    def test_edge_floor(self):
        self.assertEqual(apply_edge_floor(0.004, 0.02, min_edge=0.03), 0.0)
        self.assertEqual(apply_edge_floor(0.04, 0.02, min_edge=0.03), 0.02)

    def test_decimal(self):
        self.assertAlmostEqual(american_to_decimal(-110), 1 + 100 / 110, places=12)
        self.assertAlmostEqual(american_to_decimal(150), 2.5, places=12)


if __name__ == "__main__":
    unittest.main()
