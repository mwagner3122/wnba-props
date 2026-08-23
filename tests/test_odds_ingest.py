"""Phase 2 odds ingest tests (stdlib unittest — no pytest dep)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.db import connect, init_schema
from src.ingest_odds import (
    ingest_odds,
    parse_event_odds_rows,
    parse_raw_payload,
    project_monthly_usage,
)


FIXTURE = Path("tests/fixtures/odds/event_odds_fixture.json")


class TestOddsParse(unittest.TestCase):
    def test_fixture_parses_player_points_and_alternate(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertTrue(payload.get("_fixture"))
        rows = parse_raw_payload(payload, "player_points")
        # DK: 3 players; FD main: 2; FD alternate: 1 → 6 rows
        self.assertEqual(len(rows), 6)
        books = {r["book"] for r in rows}
        self.assertEqual(books, {"draftkings", "fanduel"})
        markets = {r["market"] for r in rows}
        self.assertEqual(markets, {"player_points", "player_points_alternate"})
        aja_alt = [
            r
            for r in rows
            if r["player_name_raw"] == "A'ja Wilson" and r["is_alternate"] == 1
        ]
        self.assertEqual(len(aja_alt), 1)
        self.assertEqual(aja_alt[0]["line"], 20.5)

    def test_malformed_bookmakers_do_not_crash(self) -> None:
        rows = parse_event_odds_rows(
            {"id": "g1", "bookmakers": "oops"},
            captured_at_utc="2026-08-23T00:00:00Z",
            configured_market="player_points",
        )
        self.assertEqual(rows, [])

    def test_projection_math(self) -> None:
        proj = project_monthly_usage(
            {
                "snapshots_per_day": 4,
                "games_per_slate": 7,
                "markets": ["player_points"],
                "regions": "us",
                "capture_cadence": {"near_tip": True},
            }
        )
        self.assertEqual(proj["credits_per_game"], 1)
        self.assertEqual(proj["credits_per_month"], 4 * 7 * 1 * 30)


class TestOddsDryRunAndNetwork(unittest.TestCase):
    def test_dry_run_inserts_from_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            raw = Path(tmp) / "raw"
            raw.mkdir()
            cfg = Path(tmp) / "config.yaml"
            cfg.write_text(
                f"""
db_path: {db}
odds:
  sport_key: basketball_wnba
  market: player_points
  markets: [player_points]
  regions: us
  odds_format: american
  raw_odds_dir: {raw}
  fixture_path: {FIXTURE.resolve()}
  snapshots_per_day: 4
  games_per_slate: 7
  capture_cadence:
    near_tip: true
""",
                encoding="utf-8",
            )
            rc = ingest_odds(config_path=cfg, dry_run=True)
            self.assertEqual(rc, 0)
            conn = connect(db)
            init_schema(conn)
            n = conn.execute("SELECT COUNT(*) AS n FROM odds_snapshots").fetchone()["n"]
            self.assertEqual(n, 6)
            ts = conn.execute(
                "SELECT DISTINCT captured_at_utc FROM odds_snapshots"
            ).fetchone()["captured_at_utc"]
            self.assertTrue(ts.endswith("Z"))
            conn.close()

    def test_network_failure_mid_run_exits_cleanly(self) -> None:
        """Simulated path: events succeed, first event-odds raises URLError-like error."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            raw = Path(tmp) / "raw"
            raw.mkdir()
            cfg = Path(tmp) / "config.yaml"
            cfg.write_text(
                f"""
db_path: {db}
odds:
  sport_key: basketball_wnba
  market: player_points
  markets: [player_points]
  regions: us
  odds_format: american
  raw_odds_dir: {raw}
  fixture_path: {FIXTURE.resolve()}
  snapshots_per_day: 4
  games_per_slate: 7
""",
                encoding="utf-8",
            )

            events = [{"id": "evt1", "home_team": "A", "away_team": "B"}]

            with (
                mock.patch("src.ingest_odds._api_key", return_value="test-key-not-real"),
                mock.patch("src.ingest_odds.fetch_events", return_value=events),
                mock.patch(
                    "src.ingest_odds.fetch_event_odds",
                    side_effect=RuntimeError("Network error: simulated disconnect"),
                ),
            ):
                rc = ingest_odds(config_path=cfg, dry_run=False)
            self.assertEqual(rc, 1)
            # No partial raw required; clean exit with no crash.
            conn = connect(db)
            init_schema(conn)
            n = conn.execute("SELECT COUNT(*) AS n FROM odds_snapshots").fetchone()["n"]
            self.assertEqual(n, 0)
            conn.close()


if __name__ == "__main__":
    unittest.main()
