#!/usr/bin/env python3
"""DoD: fake an old odds archive, show check-staleness FAIL, restore, show PASS."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.automation import check_staleness
from src.db import connect, init_schema
from src.stats_parse import load_config


def main() -> int:
    cfg = load_config(ROOT / "config.yaml")
    db_path = Path(cfg.get("db_path", "data/wnba.db"))
    print("=== Phase 10 DoD: fake-old-snapshot staleness test ===", flush=True)
    print(f"DB: {db_path}", flush=True)

    conn = connect(db_path)
    init_schema(conn)
    rows = conn.execute(
        "SELECT snapshot_id, captured_at_utc FROM odds_snapshots"
    ).fetchall()
    originals = [(int(r["snapshot_id"]), str(r["captured_at_utc"])) for r in rows]
    newest = max((ts for _, ts in originals), default=None)
    print(f"Rows={len(originals)} newest={newest}", flush=True)

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=40)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    if not originals:
        print("No odds rows — inserting a single old sentinel for the test.", flush=True)
        conn.execute(
            """
            INSERT INTO odds_snapshots (
                captured_at_utc, game_id, book, market, player_name_raw,
                line, over_price, under_price
            ) VALUES (?, '__staleness_test__', 'test', 'player_points',
                      'Staleness Test', 1.5, -110, -110)
            """,
            (old_ts,),
        )
        conn.commit()
        mode = "insert"
    else:
        n = conn.execute(
            "UPDATE odds_snapshots SET captured_at_utc = ?",
            (old_ts,),
        ).rowcount
        conn.commit()
        print(f"Temporarily set ALL {n} row(s) captured_at_utc -> {old_ts}", flush=True)
        mode = "update"

    print("\n--- Expect FAIL (fake age >36h) ---", flush=True)
    rc_fail = check_staleness(db_path=db_path, stale_hours=36)
    print(f"exit_code={rc_fail}", flush=True)

    if mode == "insert":
        conn.execute(
            "DELETE FROM odds_snapshots WHERE game_id = '__staleness_test__'"
        )
        conn.commit()
        print("Removed sentinel test rows.", flush=True)
    else:
        conn.executemany(
            "UPDATE odds_snapshots SET captured_at_utc = ? WHERE snapshot_id = ?",
            [(ts, sid) for sid, ts in originals],
        )
        conn.commit()
        restored_newest = conn.execute(
            "SELECT MAX(captured_at_utc) AS m FROM odds_snapshots"
        ).fetchone()["m"]
        print(
            f"Restored {len(originals)} row(s); newest again={restored_newest}",
            flush=True,
        )

    print("\n--- Expect PASS (restored) ---", flush=True)
    rc_pass = check_staleness(db_path=db_path, stale_hours=36)
    print(f"exit_code={rc_pass}", flush=True)
    conn.close()

    ok = rc_fail == 1 and rc_pass == 0
    print("\n=== RESULT:", "PASS" if ok else "FAIL", "===", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
