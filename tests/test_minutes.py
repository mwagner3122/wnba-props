"""Phase 5: team minutes sum constraint and OT gating."""

from __future__ import annotations

import unittest

import numpy as np

from src.minutes_sim import (
    minutes_from_shares,
    sample_dirichlet_minutes,
    sample_independent_normalize_minutes,
    team_minutes_budget,
)


class TestMinutesSumConstraint(unittest.TestCase):
    def test_regulation_budget_is_200(self):
        self.assertEqual(team_minutes_budget(0), 200.0)
        self.assertEqual(team_minutes_budget(0, ot_event=False), 200.0)
        # overtime_periods ignored unless ot_event is true / periods>0 path
        self.assertEqual(team_minutes_budget(2, ot_event=False), 200.0)

    def test_ot_adds_25_only_after_explicit_event(self):
        self.assertEqual(team_minutes_budget(1, ot_event=True), 225.0)
        self.assertEqual(team_minutes_budget(2, ot_event=True), 250.0)
        # periods>0 implies explicit OT event when ot_event left default
        self.assertEqual(team_minutes_budget(1), 225.0)

    def test_simulated_shares_sum_to_200_regulation(self):
        shares = np.array([0.20, 0.18, 0.15, 0.14, 0.12, 0.10, 0.06, 0.05])
        mins = minutes_from_shares(shares, overtime_periods=0, ot_event=False)
        self.assertAlmostEqual(float(mins.sum()), 200.0, places=6)

    def test_simulated_shares_sum_to_225_after_ot_event(self):
        shares = np.array([0.20, 0.18, 0.15, 0.14, 0.12, 0.10, 0.06, 0.05])
        mins = minutes_from_shares(shares, overtime_periods=1, ot_event=True)
        self.assertAlmostEqual(float(mins.sum()), 225.0, places=6)

    def test_dirichlet_draws_always_sum_to_budget(self):
        shares = [0.17, 0.16, 0.15, 0.14, 0.12, 0.10, 0.08, 0.08]
        rng = np.random.default_rng(0)
        reg = sample_dirichlet_minutes(
            shares, concentration=40.0, n_draws=50, overtime_periods=0, rng=rng
        )
        self.assertTrue(np.allclose(reg.sum(axis=1), 200.0))
        ot = sample_dirichlet_minutes(
            shares,
            concentration=40.0,
            n_draws=50,
            overtime_periods=1,
            ot_event=True,
            rng=rng,
        )
        self.assertTrue(np.allclose(ot.sum(axis=1), 225.0))

    def test_independent_normalize_sums_and_ot_gate(self):
        mu = np.array([34.0, 30.0, 28.0, 24.0, 22.0, 18.0, 14.0, 10.0])
        rng = np.random.default_rng(1)
        reg = sample_independent_normalize_minutes(
            mu, residual_scale=3.0, n_draws=30, overtime_periods=0, rng=rng
        )
        self.assertTrue(np.allclose(reg.sum(axis=1), 200.0, atol=1e-6))
        # Without OT event, periods alone with ot_event=False stay at 200
        no_ot = sample_independent_normalize_minutes(
            mu,
            residual_scale=3.0,
            n_draws=10,
            overtime_periods=2,
            ot_event=False,
            rng=rng,
        )
        self.assertTrue(np.allclose(no_ot.sum(axis=1), 200.0, atol=1e-6))
        yes_ot = sample_independent_normalize_minutes(
            mu,
            residual_scale=3.0,
            n_draws=10,
            overtime_periods=1,
            ot_event=True,
            rng=rng,
        )
        self.assertTrue(np.allclose(yes_ot.sum(axis=1), 225.0, atol=1e-6))


if __name__ == "__main__":
    unittest.main()
