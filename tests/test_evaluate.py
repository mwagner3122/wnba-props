"""Phase 9 evaluation: walk-forward folds, holdout freeze, metrics sanity."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

import numpy as np

from src.eval_metrics import crps_from_samples, interval_coverage, log_loss_binary, brier_score
from src.eval_walkforward import (
    build_weekly_folds,
    freeze_holdout,
    assert_not_holdout,
    holdout_warning_message,
)


class TestHoldoutAndFolds(unittest.TestCase):
    def test_holdout_is_final_21_days(self):
        h = freeze_holdout("2026-08-22", holdout_days=21)
        self.assertEqual(h.end, "2026-08-22")
        self.assertEqual(h.start, "2026-08-02")
        self.assertIn("FROZEN HOLDOUT", holdout_warning_message(h))

    def test_folds_never_enter_holdout(self):
        dates = [(date(2025, 5, 16) + timedelta(days=i)).isoformat() for i in range(0, 400, 2)]
        h = freeze_holdout("2026-08-22", holdout_days=21)
        folds = build_weekly_folds(dates, holdout=h, min_train_days=60, week_days=7)
        self.assertGreater(len(folds), 5)
        for f in folds:
            self.assertLess(f.test_end, h.start)
            self.assertLessEqual(f.train_end, f.test_start)

    def test_assert_not_holdout_raises(self):
        h = freeze_holdout("2026-08-22", holdout_days=21)
        with self.assertRaises(RuntimeError):
            assert_not_holdout(["2026-08-10"], h)


class TestMetrics(unittest.TestCase):
    def test_crps_perfect_point(self):
        rng = np.random.default_rng(0)
        y = np.array([5.0, 10.0])
        samples = np.tile(y[:, None], (1, 50))
        c = crps_from_samples(samples, y)
        self.assertTrue(np.all(c < 0.05))

    def test_coverage_and_binary(self):
        rng = np.random.default_rng(1)
        y = rng.normal(0, 1, size=400)
        # Predictive centered at 0 with sd=1; outcomes also N(0,1) => ~nominal coverage
        samples = rng.normal(0, 1, size=(400, 500))
        cov = interval_coverage(samples, y)
        self.assertGreater(cov["coverage_50"], 0.35)
        self.assertLess(cov["coverage_50"], 0.65)
        p = np.array([0.9, 0.1, 0.8])
        yt = np.array([1.0, 0.0, 1.0])
        self.assertLess(log_loss_binary(p, yt), 0.5)
        self.assertLess(brier_score(p, yt), 0.2)


if __name__ == "__main__":
    unittest.main()
