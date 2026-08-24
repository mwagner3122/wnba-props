"""Phase 6: Beta-Binomial 3PM helpers and as-of leakage checks."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.rates_3pm_data import add_asof_player_history, variance_to_mean_report
from src.rates_3pm_eval import crps_from_samples, pit_from_samples
from src.rates_3pm_model import Rates3PMModel


class TestRates3PM(unittest.TestCase):
    def test_asof_history_no_leakage(self):
        df = pd.DataFrame(
            {
                "player_id": ["a", "a", "a"],
                "game_id": ["1", "2", "3"],
                "game_date": ["2024-06-01", "2024-06-03", "2024-06-05"],
                "season": [2024, 2024, 2024],
                "team_id": ["T", "T", "T"],
                "opponent_id": ["O", "O", "O"],
                "position": ["G", "G", "G"],
                "role": ["G", "G", "G"],
                "minutes": [20.0, 30.0, 10.0],
                "fg3a": [4, 6, 2],
                "fg3m": [1, 3, 0],
                "fga": [8, 10, 4],
                "played": [1, 1, 1],
                "fg3m_p40_l10": [0.0, 0.0, 0.0],
                "three_rate_std": [0.0, 0.0, 0.0],
                "games_played": [0, 1, 2],
                "player_form_prior_weight": [1.0, 0.5, 0.3],
                "opp_pace_shrunk": [80.0, 80.0, 80.0],
                "team_pace_shrunk": [80.0, 80.0, 80.0],
                "overtime_periods": [0, 0, 0],
            }
        )
        out = add_asof_player_history(df)
        self.assertEqual(out.iloc[0]["prior_fg3m"], 0.0)
        self.assertEqual(out.iloc[0]["prior_fg3a"], 0.0)
        self.assertEqual(out.iloc[1]["prior_fg3m"], 1.0)
        self.assertEqual(out.iloc[1]["prior_fg3a"], 4.0)
        self.assertEqual(out.iloc[1]["prior_minutes"], 20.0)
        self.assertEqual(out.iloc[2]["prior_fg3m"], 4.0)
        self.assertEqual(out.iloc[2]["prior_fg3a"], 10.0)
        self.assertEqual(out.iloc[2]["std_fg3m"], 4.0)

    def test_player_posterior_shrinks_small_sample(self):
        cfg = {
            "p3_kappa_league": 200.0,
            "p3_kappa_role": 40.0,
            "pa_k_league": 80.0,
            "pa_k_role": 20.0,
            "opp_k": 25.0,
            "pa_nb_r_fallback": 4.0,
        }
        model = Rates3PMModel(cfg)
        train = pd.DataFrame(
            {
                "minutes": [30.0] * 50 + [30.0] * 50,
                "fg3a": [5] * 50 + [3] * 50,
                "fg3m": [2] * 50 + [1] * 50,
                "role": ["G"] * 50 + ["F"] * 50,
                "opponent_id": ["X"] * 100,
                "game_id": [str(i) for i in range(100)],
            }
        )
        model.fit(train)
        cold = model.player_posterior("G", 0, 0, 0)
        self.assertGreater(cold["p3_shrink_weight"], 0.95)
        hot = model.player_posterior("G", 100, 300, 2000)
        self.assertLess(hot["p3_shrink_weight"], cold["p3_shrink_weight"])
        self.assertAlmostEqual(hot["ess"], 40.0 + 300.0, places=5)

    def test_crps_perfect_point_mass(self):
        y = np.array([2.0, 3.0])
        samples = np.array([[2, 2, 2, 2], [3, 3, 3, 3]], dtype=float)
        crps = crps_from_samples(samples, y)
        self.assertTrue(np.allclose(crps, 0.0, atol=1e-9))

    def test_pit_uniform_when_calibrated_gaussian_like(self):
        rng = np.random.default_rng(0)
        y = rng.poisson(2.0, size=2000)
        samples = rng.poisson(2.0, size=(2000, 300))
        pits = pit_from_samples(samples, y, rng)
        self.assertGreater(pits.mean(), 0.45)
        self.assertLess(pits.mean(), 0.55)

    def test_variance_report_keys(self):
        df = pd.DataFrame({"minutes": [20.0, 30.0, 0.0], "fg3m": [1, 2, 0], "fg3a": [3, 5, 0]})
        rep = variance_to_mean_report(df)
        self.assertEqual(rep["n_played"], 2)
        self.assertIn("var_to_mean", rep["fg3m"])


if __name__ == "__main__":
    unittest.main()
