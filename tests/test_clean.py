"""Phase 3 clean/join tests (stdlib unittest)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.clean import (
    game_date_et_from_utc,
    run_clean,
)
from src.db import connect, init_schema
from src.name_normalize import normalize_name, propose_fuzzy


class TestNameNormalize(unittest.TestCase):
    def test_apostrophe_and_accents(self) -> None:
        self.assertEqual(normalize_name("A'ja Wilson"), "aja wilson")
        self.assertEqual(normalize_name("A’ja Wilson"), "aja wilson")  # curly
        self.assertEqual(normalize_name("José"), "jose")

    def test_last_first_and_punct(self) -> None:
        self.assertEqual(normalize_name("Plum, Kelsey"), "kelsey plum")
        self.assertEqual(normalize_name("  K.   Plum "), "k plum")

    def test_fuzzy_propose_not_empty_for_typo(self) -> None:
        cands = [("1", "Breanna Stewart"), ("2", "A'ja Wilson")]
        props = propose_fuzzy(normalize_name("Breanna Stewert"), cands, min_score=0.7)
        self.assertTrue(props)
        self.assertEqual(props[0]["player_id"], "1")


class TestTimezone(unittest.TestCase):
    def test_pacific_late_tip_stays_previous_et_calendar_day(self) -> None:
        # 2026-08-25T02:00:00Z == 2026-08-24 22:00 ET
        self.assertEqual(game_date_et_from_utc("2026-08-25T02:00:00Z"), "2026-08-24")

    def test_afternoon_et_same_day(self) -> None:
        self.assertEqual(game_date_et_from_utc("2026-08-23T20:00:00Z"), "2026-08-23")


class TestCleanPipeline(unittest.TestCase):
    def test_clean_keeps_unmatched_and_flags_void(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "wnba.db"
            raw = root / "raw"
            raw.mkdir()
            reports = root / "reports"
            reports.mkdir()
            cfg = root / "config.yaml"
            cfg.write_text(
                f"""
db_path: {db}
odds:
  raw_odds_dir: {raw}
  fixture_path: {root / 'missing_fixture.json'}
""",
                encoding="utf-8",
            )

            conn = connect(db)
            init_schema(conn)
            conn.execute(
                "INSERT INTO teams(team_id, abbreviation, location, name, display_name) "
                "VALUES ('17','LV','Las Vegas','Aces','Las Vegas Aces')"
            )
            conn.execute(
                "INSERT INTO teams(team_id, abbreviation, location, name, display_name) "
                "VALUES ('9','NY','New York','Liberty','New York Liberty')"
            )
            conn.execute(
                "INSERT INTO players(player_id, player_name) VALUES ('p1', \"A'ja Wilson\")"
            )
            conn.execute(
                "INSERT INTO players(player_id, player_name) VALUES ('p2', 'Breanna Stewart')"
            )
            conn.execute(
                "INSERT INTO games(game_id, game_date, season, home_team_id, away_team_id) "
                "VALUES ('g1', '2026-08-20', 2026, '17', '9')"
            )
            # Played
            conn.execute(
                """
                INSERT INTO player_games(
                    game_id, game_date, player_id, player_name, team_id, opponent_id,
                    minutes, points, dnp_reason
                ) VALUES ('g1','2026-08-20','p1',\"A'ja Wilson\",'17','9', 32.0, 28, NULL)
                """
            )
            # Void / DNP
            conn.execute(
                """
                INSERT INTO player_games(
                    game_id, game_date, player_id, player_name, team_id, opponent_id,
                    minutes, points, dnp_reason
                ) VALUES ('g1','2026-08-20','p2','Breanna Stewart','9','17', 0.0, 0, 'INJURY')
                """
            )
            conn.execute(
                "INSERT INTO availability(game_id, player_id, status, minutes_played) "
                "VALUES ('g1','p2','dnp_injury',0)"
            )
            # odds event meta via raw
            raw_payload = {
                "captured_at_utc": "2026-08-20T12:00:00Z",
                "events": [
                    {
                        "id": "evt1",
                        "commence_time": "2026-08-20T23:00:00Z",
                        "home_team": "Las Vegas Aces",
                        "away_team": "New York Liberty",
                    }
                ],
                "event_odds": [],
            }
            (raw / "snap.json").write_text(json.dumps(raw_payload), encoding="utf-8")
            conn.execute(
                """
                INSERT INTO odds_snapshots(
                    captured_at_utc, game_id, book, market, player_name_raw,
                    line, over_price, under_price, is_alternate
                ) VALUES
                ('2026-08-20T12:00:00Z','evt1','dk','player_points',\"A'ja Wilson\",24.5,-110,-110,0),
                ('2026-08-20T12:00:00Z','evt1','dk','player_points','Breanna Stewart',19.5,-115,-105,0),
                ('2026-08-20T12:00:00Z','evt1','dk','player_points','Unknown Person',10.5,-110,-110,0),
                ('2026-08-20T12:00:00Z','evt1','dk','player_points','Aja Wilson',20.0,-110,-110,1)
                """
            )
            conn.commit()
            conn.close()

            # run from temp CWD so reports/unmatched.md lands in tmp/reports...
            # run_clean writes reports/unmatched.md relative to CWD
            import os
            old = os.getcwd()
            os.chdir(root)
            try:
                # symlink/copy module expectations: config path absolute
                rc = run_clean(config_path=cfg)
                self.assertEqual(rc, 0)
                self.assertTrue((root / "reports" / "unmatched.md").is_file())
            finally:
                os.chdir(old)

            conn = connect(db)
            rows = list(conn.execute("SELECT * FROM prop_results ORDER BY snapshot_id"))
            self.assertEqual(len(rows), 4)
            by_name = {r["player_name_raw"]: r for r in rows}
            self.assertEqual(by_name["A'ja Wilson"]["match_status"], "matched")
            self.assertEqual(by_name["A'ja Wilson"]["actual_points"], 28)
            self.assertEqual(by_name["A'ja Wilson"]["is_voided"], 0)
            self.assertEqual(by_name["Breanna Stewart"]["is_voided"], 1)
            self.assertIsNone(by_name["Breanna Stewart"]["actual_points"])
            self.assertEqual(by_name["Unknown Person"]["match_status"], "unmatched")
            self.assertIsNotNone(by_name["Unknown Person"]["reason_code"])
            # whole-number + alternate flags
            self.assertEqual(by_name["Aja Wilson"]["is_whole_number_line"], 1)
            self.assertEqual(by_name["Aja Wilson"]["is_alternate"], 1)
            # fuzzy never auto-mapped Aja Wilson without approval (may exact-normalize to aja wilson!)
            # normalize("Aja Wilson") == normalize("A'ja Wilson") == "aja wilson" -> exact match
            self.assertEqual(by_name["Aja Wilson"]["player_id"], "p1")
            conn.close()

    def test_fuzzy_never_auto_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "wnba.db"
            raw = root / "raw"
            raw.mkdir()
            (root / "reports").mkdir()
            cfg = root / "config.yaml"
            cfg.write_text(
                f"db_path: {db}\nodds:\n  raw_odds_dir: {raw}\n  fixture_path: x\n",
                encoding="utf-8",
            )
            conn = connect(db)
            init_schema(conn)
            conn.execute(
                "INSERT INTO players(player_id, player_name) VALUES ('p1', 'Kelsey Plum')"
            )
            raw_payload = {
                "events": [
                    {
                        "id": "e2",
                        "commence_time": "2026-08-21T00:00:00Z",
                        "home_team": "Las Vegas Aces",
                        "away_team": "New York Liberty",
                    }
                ]
            }
            (raw / "s.json").write_text(json.dumps(raw_payload), encoding="utf-8")
            conn.execute(
                "INSERT INTO teams(team_id, abbreviation, location, name, display_name) "
                "VALUES ('17','LV','Las Vegas','Aces','Las Vegas Aces')"
            )
            conn.execute(
                "INSERT INTO teams(team_id, abbreviation, location, name, display_name) "
                "VALUES ('9','NY','New York','Liberty','New York Liberty')"
            )
            conn.execute(
                """
                INSERT INTO odds_snapshots(
                    captured_at_utc, game_id, book, market, player_name_raw,
                    line, over_price, under_price, is_alternate
                ) VALUES ('2026-08-20T12:00:00Z','e2','dk','player_points','Kelsy Plumm',15.5,-110,-110,0)
                """
            )
            conn.commit()
            conn.close()
            import os
            old = os.getcwd()
            os.chdir(root)
            try:
                self.assertEqual(run_clean(config_path=cfg), 0)
            finally:
                os.chdir(old)
            conn = connect(db)
            row = conn.execute("SELECT * FROM prop_results").fetchone()
            self.assertIsNone(row["player_id"])
            self.assertEqual(row["reason_code"], "needs_fuzzy_approval")
            nm = conn.execute("SELECT COUNT(*) AS c FROM name_map").fetchone()["c"]
            self.assertEqual(nm, 0)
            conn.close()


if __name__ == "__main__":
    unittest.main()
