"""Phase 10: staleness check and today_out override."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.automation import check_staleness
from src.db import init_schema
from src.today_out import apply_today_out, load_today_out, out_player_ids


def _mem_db_with_snapshot(captured_at: str) -> Path:
    # Use a temp file so connect() paths match production shape.
    import tempfile

    tmp = Path(tempfile.mkdtemp()) / "t.db"
    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    conn.execute(
        """
        INSERT INTO odds_snapshots (
            captured_at_utc, game_id, book, market, player_name_raw,
            line, over_price, under_price
        ) VALUES (?, 'g1', 'book', 'player_points', 'Test Player',
                  20.5, -110, -110)
        """,
        (captured_at,),
    )
    conn.commit()
    conn.close()
    return tmp


def test_staleness_pass_fresh(tmp_path: Path) -> None:
    now = datetime(2026, 8, 23, 21, 0, 0, tzinfo=timezone.utc)
    captured = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = _mem_db_with_snapshot(captured)
    rc = check_staleness(db_path=db, stale_hours=36, now=now)
    assert rc == 0


def test_staleness_fail_old(tmp_path: Path) -> None:
    now = datetime(2026, 8, 23, 21, 0, 0, tzinfo=timezone.utc)
    captured = (now - timedelta(hours=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = _mem_db_with_snapshot(captured)
    rc = check_staleness(db_path=db, stale_hours=36, now=now)
    assert rc == 1


def test_today_out_removes_and_renorm(tmp_path: Path) -> None:
    csv_path = tmp_path / "today_out.csv"
    csv_path.write_text(
        "player_id,player_name,status,note\n"
        "1,,out,test\n"
        ",Other Player,dnp_injury,\n",
        encoding="utf-8",
    )
    tout = load_today_out(csv_path)
    roster = pd.DataFrame(
        {
            "player_id": ["1", "2", "3"],
            "player_name": ["A", "B", "Other Player"],
            "team_id": ["T", "T", "T"],
            "expected_minutes_share": [0.4, 0.4, 0.2],
        }
    )
    ids = out_player_ids(tout, roster)
    assert ids == {"1", "3"}
    out = apply_today_out(roster, tout, verbose=False)
    assert list(out["player_id"]) == ["2"]
    assert abs(float(out["expected_minutes_share"].iloc[0]) - 1.0) < 1e-9
