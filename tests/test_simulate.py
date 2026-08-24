"""Phase 7: minutes budget, OT gate, component points identity."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.minutes_sim import sample_dirichlet_minutes
from src.sim_components import RatesFg2FtModel
from src.sim_config import simulation_config
from src.sim_engine import assert_minutes_budget, simulate_game
from src.sim_summarize import percentile_grid, prob_ge_k
from src.stats_parse import load_config


class _Fake3PM:
    pa_nb_r = 4.0

    def sample_3pm(self, *args, **kwargs):
        raise NotImplementedError


class _FakeNB:
    nb_r = 2.0


def _tiny_roster(n_per_team: int = 8) -> pd.DataFrame:
    rows = []
    for tid in ("T1", "T2"):
        for i in range(n_per_team):
            rows.append(
                {
                    "game_id": "G1",
                    "player_id": f"{tid}-{i}",
                    "player_name": f"P{tid}{i}",
                    "team_id": tid,
                    "role": "G" if i < 3 else ("F" if i < 6 else "C"),
                    "usage_rate_shrunk": 0.22 - 0.015 * i,
                    "team_pace_shrunk": 80.0,
                    "opp_pace_shrunk": 80.0,
                    "expected_minutes_share": 0.0,
                    "pa_p40": 4.0,
                    "p3_alpha": 20.0,
                    "p3_beta": 40.0,
                    "opp_pa_factor": 1.0,
                    "reb_p40": 6.0,
                    "opp_reb_factor": 1.0,
                    "ast_p40": 4.0,
                    "opp_ast_factor": 1.0,
                    "pa2_p40": 8.0,
                    "p2_alpha": 40.0,
                    "p2_beta": 50.0,
                    "fta_p40": 4.0,
                    "ft_alpha": 40.0,
                    "ft_beta": 10.0,
                }
            )
    df = pd.DataFrame(rows)
    for tid, sub in df.groupby("team_id"):
        # Declining shares
        s = np.linspace(0.18, 0.05, len(sub))
        s = s / s.sum()
        df.loc[sub.index, "expected_minutes_share"] = s
    return df


class TestSimulate(unittest.TestCase):
    def test_regulation_minutes_sum_to_200(self):
        shares = [0.17, 0.16, 0.15, 0.14, 0.12, 0.10, 0.08, 0.08]
        rng = np.random.default_rng(0)
        reg = sample_dirichlet_minutes(
            shares, concentration=40.0, n_draws=100, overtime_periods=0, rng=rng
        )
        self.assertTrue(np.allclose(reg.sum(axis=1), 200.0))

    def test_ot_adds_25_only_after_explicit_event(self):
        shares = [0.17, 0.16, 0.15, 0.14, 0.12, 0.10, 0.08, 0.08]
        rng = np.random.default_rng(1)
        ot = sample_dirichlet_minutes(
            shares,
            concentration=40.0,
            n_draws=50,
            overtime_periods=1,
            ot_event=True,
            rng=rng,
        )
        self.assertTrue(np.allclose(ot.sum(axis=1), 225.0))
        no = sample_dirichlet_minutes(
            shares,
            concentration=40.0,
            n_draws=50,
            overtime_periods=2,
            ot_event=False,
            rng=rng,
        )
        self.assertTrue(np.allclose(no.sum(axis=1), 200.0))

    def test_points_identity_and_minutes_budget(self):
        cfg = simulation_config(load_config("config.yaml"))
        cfg["n_sim"] = 200
        cfg["random_seed"] = 3
        roster = _tiny_roster()
        fg2 = RatesFg2FtModel(cfg)
        # Minimal fit via synthetic played rows
        train = pd.DataFrame(
            {
                "minutes": [30.0] * 100,
                "fga": [12] * 100,
                "fgm": [6] * 100,
                "fg3a": [4] * 100,
                "fg3m": [1] * 100,
                "fta": [4] * 100,
                "ftm": [3] * 100,
                "role": ["G"] * 50 + ["F"] * 30 + ["C"] * 20,
                "season": [2024] * 100,
            }
        )
        fg2.fit(train)
        rng = np.random.default_rng(3)
        result = simulate_game(
            roster,
            model_3pm=_Fake3PM(),
            model_reb=_FakeNB(),
            model_ast=_FakeNB(),
            model_fg2ft=fg2,
            cfg=cfg,
            rng=rng,
            ot_event=False,
            overtime_periods=0,
        )
        pts = result.draws["pts"]
        derived = 2 * result.draws["fg2m"] + 3 * result.draws["fg3m"] + result.draws["ftm"]
        self.assertTrue(np.array_equal(pts, derived))
        check = assert_minutes_budget(result, cfg)
        self.assertTrue(check["ok"])
        self.assertEqual(check["expected_budget"], 200.0)

    def test_prob_ge_k_and_summary(self):
        x = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=float)
        self.assertAlmostEqual(prob_ge_k(x, 5), 0.5)
        summ = percentile_grid(x)
        self.assertIn("mean", summ)
        self.assertIn("sd", summ)
        self.assertIn("p50", summ)


if __name__ == "__main__":
    unittest.main()
