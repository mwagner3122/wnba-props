"""Phase 4 feature leakage and expansion-team tests."""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.feature_columns import FEATURE_COLUMNS
from src.feature_compute import compute_feature_frame, load_frames, shrink
from src.stats_parse import load_config

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "wnba.db"
CFG = ROOT / "config.yaml"


@unittest.skipUnless(DB.is_file(), "data/wnba.db missing")
class TestFeaturesLeakage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = load_config(CFG)
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        cls.pg, cls.games, cls.players, cls.teams = load_frames(conn)
        conn.close()
        cls.full = compute_feature_frame(
            cls.pg, cls.games, cls.players, cls.teams, cls.cfg
        )

    def test_shrink_formula(self) -> None:
        got = shrink(4.0, 6.0, 3.0, 8.0)
        self.assertAlmostEqual(float(got), (6 * 4 + 8 * 3) / (6 + 8), places=9)

    def test_asof_leakage_sample_50(self) -> None:
        """Recompute features from as-of snapshot; assert equality vs full build.

        Samples 50 player-games. Rebuilds once per distinct game_ord in the sample
        (still as-of equality for every sampled row).
        """
        cand = self.full[self.full["games_played"] >= 5].copy()
        if len(cand) < 50:
            cand = self.full.copy()

        # Prefer fewer distinct games so rebuilds stay tractable while still
        # covering 50 player-games.
        games_pool = (
            cand.groupby("game_id", sort=False)
            .size()
            .sort_values(ascending=False)
            .head(15)
            .index.tolist()
        )
        sample_parts = []
        for gid in games_pool:
            part = cand[cand["game_id"] == gid]
            sample_parts.append(part.sample(n=min(4, len(part)), random_state=42))
            if sum(len(p) for p in sample_parts) >= 50:
                break
        sample = pd.concat(sample_parts, ignore_index=True).head(50)
        self.assertEqual(len(sample), 50)

        games = self.games.copy()
        games["game_date"] = games["game_date"].astype(str)
        games = games.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(
            drop=True
        )
        games["game_ord"] = np.arange(len(games), dtype=np.int64)
        ord_map = {
            str(k): int(v) for k, v in games.set_index("game_id")["game_ord"].items()
        }

        mismatches: list[tuple] = []
        # One rebuild per distinct game_ord
        by_ord: dict[int, pd.DataFrame] = {}
        for gid in sample["game_id"].astype(str).unique():
            g_ord = ord_map[gid]
            if g_ord in by_ord:
                continue
            games_sub = games[games["game_ord"] <= g_ord].drop(columns=["game_ord"])
            pg_sub = self.pg[
                self.pg["game_id"].astype(str).isin(games_sub["game_id"].astype(str))
            ]
            by_ord[g_ord] = compute_feature_frame(
                pg_sub, games_sub, self.players, self.teams, self.cfg
            )

        for _, row in sample.iterrows():
            gid = str(row["game_id"])
            pid = str(row["player_id"])
            g_ord = ord_map[gid]
            sub = by_ord[g_ord]
            hit = sub[
                (sub["game_id"].astype(str) == gid)
                & (sub["player_id"].astype(str) == pid)
            ]
            self.assertEqual(len(hit), 1, f"missing row {gid}/{pid}")
            b = hit.iloc[0]
            for col in FEATURE_COLUMNS:
                va = row[col]
                vb = b[col]
                if pd.isna(va) and pd.isna(vb):
                    continue
                if pd.isna(va) or pd.isna(vb):
                    mismatches.append((gid, pid, col, va, vb))
                    continue
                if not np.isclose(
                    float(va), float(vb), rtol=1e-7, atol=1e-7, equal_nan=True
                ):
                    mismatches.append((gid, pid, col, float(va), float(vb)))

        self.assertEqual(
            mismatches[:10],
            [],
            f"{len(mismatches)} mismatches e.g. {mismatches[:5]}",
        )

    def test_expansion_teams_no_crash(self) -> None:
        abbr = {
            str(r.team_id): str(r.abbreviation).upper()
            for r in self.teams.itertuples()
        }
        expansion = {"TOR", "POR"}
        exp_ids = {tid for tid, a in abbr.items() if a in expansion}
        exp = self.full[self.full["team_id"].isin(exp_ids)]
        self.assertGreater(len(exp), 0)
        late = exp[exp["team_games_played"] >= 1]
        self.assertFalse(late["team_pace_shrunk"].isna().all())
        self.assertFalse(late["opp_def_rtg_shrunk"].isna().all())
        self.assertIn("minutes_vacated", exp.columns)
        self.assertFalse(exp["minutes_vacated"].isna().all())


if __name__ == "__main__":
    unittest.main()
