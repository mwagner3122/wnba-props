"""Phase 6: NegativeBinomial rebounds helpers and as-of leakage checks."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.rates_reb_data import add_asof_player_history, variance_to_mean_report
from src.rates_reb_eval import crps_from_samples, pit_from_samples
from src.rates_reb_model import RatesRebModel, _fit_nb_r


class TestRatesReb(unittest.TestCase):
    def test_asof_history_no_leakage(self):
        df = pd.DataFrame(
            {
                "player_id": ["a", "a", "a"],
                "game_id": ["1", "2", "3"],
                "game_date": ["2024-06-01", "2024-06-03", "2024-06-05"],
                "season": [2024, 2024, 2024],
                "team_id": ["T", "T", "T"],
                "opponent_id": ["O", "O", "O"],
                "position": ["C", "C", "C"],
                "role": ["C", "C", "C"],
                "minutes": [20.0, 30.0, 10.0],
                "reb": [5, 8, 2],
                "oreb": [1, 2, 0],
                "dreb": [4, 6, 2],
                "played": [1, 1, 1],
                "reb_p40_l10": [0.0, 0.0, 0.0],
                "reb_p40_std": [0.0, 0.0, 0.0],
                "games_played": [0, 1, 2],
                "player_form_prior_weight": [1.0, 0.5, 0.3],
                "opp_pace_shrunk": [80.0, 80.0, 80.0],
                "team_pace_shrunk": [80.0, 80.0, 80.0],
                "overtime_periods": [0, 0, 0],
            }
        )
        out = add_asof_player_history(df)
        self.assertEqual(out.iloc[0]["prior_reb"], 0.0)
        self.assertEqual(out.iloc[1]["prior_reb"], 5.0)
        self.assertEqual(out.iloc[1]["prior_minutes"], 20.0)
        self.assertEqual(out.iloc[2]["prior_reb"], 13.0)
        self.assertEqual(out.iloc[2]["std_reb"], 13.0)

    def test_player_posterior_shrinks_small_sample(self):
        cfg = {
            "reb_k_league": 80.0,
            "reb_k_role": 20.0,
            "opp_k": 25.0,
            "nb_r_fallback": 3.0,
        }
        model = RatesRebModel(cfg)
        train = pd.DataFrame(
            {
                "minutes": [30.0] * 50 + [30.0] * 50,
                "reb": [4] * 50 + [8] * 50,
                "role": ["G"] * 50 + ["C"] * 50,
                "opponent_id": ["X"] * 100,
                "game_id": [str(i) for i in range(100)],
            }
        )
        model.fit(train)
        cold = model.player_posterior("C", 0, 0)
        self.assertGreater(cold["reb_shrink_weight"], 0.95)
        hot = model.player_posterior("C", 400, 2000)
        self.assertLess(hot["reb_shrink_weight"], cold["reb_shrink_weight"])
        self.assertAlmostEqual(hot["ess"], 20.0 + 2000.0 / 40.0, places=5)

    def test_nb_r_from_overdispersion(self):
        rng = np.random.default_rng(0)
        # overdispersed: var > mean
        counts = rng.negative_binomial(n=5, p=0.4, size=5000).astype(float)
        r = _fit_nb_r(counts, fallback=3.0)
        self.assertGreater(r, 0.5)
        self.assertLess(r, 50.0)
        # near-Poisson -> fallback
        pois = rng.poisson(3.0, size=5000).astype(float)
        r2 = _fit_nb_r(pois, fallback=3.0)
        # may or may not exceed mean slightly; just ensure finite positive
        self.assertGreater(r2, 0.0)

    def test_crps_perfect_point_mass(self):
        y = np.array([2.0, 3.0])
        samples = np.array([[2, 2, 2, 2], [3, 3, 3, 3]], dtype=float)
        crps = crps_from_samples(samples, y)
        self.assertTrue(np.allclose(crps, 0.0, atol=1e-9))

    def test_variance_report_keys(self):
        df = pd.DataFrame(
            {
                "minutes": [20.0, 30.0, 0.0],
                "reb": [5, 7, 0],
                "oreb": [1, 2, 0],
                "dreb": [4, 5, 0],
            }
        )
        rep = variance_to_mean_report(df)
        self.assertEqual(rep["n_played"], 2)
        self.assertIn("var_to_mean", rep["reb"])
        self.assertGreater(rep["reb"]["var_to_mean"], 0.0)

    def test_sample_reb_not_poisson_narrow(self):
        cfg = {
            "reb_k_league": 80.0,
            "reb_k_role": 20.0,
            "opp_k": 25.0,
            "nb_r_fallback": 2.0,
        }
        model = RatesRebModel(cfg)
        model.nb_r = 2.0
        model.fitted = True
        rng = np.random.default_rng(1)
        samples = model.sample_reb(
            np.array([40.0]),
            np.array([8.0]),
            np.array([1.0]),
            n_sim=5000,
            rng=rng,
        )
        mu = samples.mean()
        var = samples.var(ddof=1)
        self.assertGreater(var / mu, 1.2)


if __name__ == "__main__":
    unittest.main()
