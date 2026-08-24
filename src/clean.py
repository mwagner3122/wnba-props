"""Phase 3: clean + join odds_snapshots to player_games; write unmatched report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.clean_prep import (
    _utc_now_iso,
    ensure_game_date_et,
    game_date_et_from_utc,
    load_odds_events_from_raw,
    _team_name_to_id,
)
from src.clean_approvals import (
    apply_approvals,
    load_approvals_file,
    parse_approve_args,
)
from src.clean_names import resolve_names
from src.clean_build import build_prop_results
from src.clean_report import write_unmatched_report
from src.db import connect, init_schema, set_meta
from src.logging_setup import setup_logging
from src.stats_parse import load_config

logger = setup_logging()

def run_clean(
    *,
    config_path: str | Path = "config.yaml",
    approve: list[str] | None = None,
    approvals_file: str | Path | None = None,
    skip_features: bool = False,
) -> int:
    cfg = load_config(str(config_path))
    db_path = Path(cfg.get("db_path", "data/wnba.db"))
    raw_odds_dir = Path(cfg.get("odds", {}).get("raw_odds_dir", "data/raw/odds"))
    # Also try fixture for event meta if raw empty of a needed id
    fixture = Path(cfg.get("odds", {}).get("fixture_path", "tests/fixtures/odds/event_odds_fixture.json"))
    report_path = Path("reports/unmatched.md")

    print("=== python run.py clean (phase 3) ===", flush=True)
    conn = connect(db_path)
    init_schema(conn)

    # Approvals first so they seed name_map before resolve
    try:
        apply_approvals(conn, parse_approve_args(approve), mapped_by="approve_cli")
        apply_approvals(
            conn,
            load_approvals_file(Path(approvals_file) if approvals_file else None),
            mapped_by="approve_file",
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", flush=True)
        return 1

    ensure_game_date_et(conn)

    # Include fixture path directory scan if raw dir missing fixture-only ids
    load_odds_events_from_raw(conn, raw_odds_dir)
    if fixture.is_file():
        # Merge fixture event meta (same shapes as raw capture files).
        try:
            before_fx = conn.execute("SELECT COUNT(*) AS c FROM odds_events").fetchone()["c"]
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            events: list[dict[str, Any]] = []
            if isinstance(payload.get("events"), list):
                events.extend(e for e in payload["events"] if isinstance(e, dict))
            eo = payload.get("event_odds")
            if isinstance(eo, list):
                events.extend(e for e in eo if isinstance(e, dict))
            elif isinstance(eo, dict) and eo.get("id"):
                events.append(eo)
            if payload.get("id") and payload.get("commence_time"):
                events.append(payload)
            for ev in events:
                oid = str(ev.get("id") or "").strip()
                commence = str(ev.get("commence_time") or "").strip()
                if not oid or not commence:
                    continue
                gdate = game_date_et_from_utc(commence)
                conn.execute(
                    """
                    INSERT INTO odds_events(
                        odds_game_id, commence_time_utc, home_team, away_team,
                        game_date_et, source_file
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(odds_game_id) DO NOTHING
                    """,
                    (
                        oid,
                        commence,
                        ev.get("home_team"),
                        ev.get("away_team"),
                        gdate,
                        fixture.name,
                    ),
                )
            conn.commit()
            after_fx = conn.execute("SELECT COUNT(*) AS c FROM odds_events").fetchone()["c"]
            print(
                f"  fixture event meta: {fixture.name} "
                f"odds_events {before_fx} -> {after_fx}",
                flush=True,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.error("Fixture event meta load failed: %s", exc)

    events = {
        str(r["odds_game_id"]): r
        for r in conn.execute("SELECT * FROM odds_events")
    }
    team_map = _team_name_to_id(conn)
    odds_rows = list(conn.execute("SELECT * FROM odds_snapshots ORDER BY snapshot_id"))
    print(f"Step: load odds_snapshots count={len(odds_rows)}", flush=True)

    name_resolution = resolve_names(
        conn, odds_rows=odds_rows, events=events, team_map=team_map
    )
    build_stats = build_prop_results(
        conn, name_resolution=name_resolution, events=events
    )
    summary = write_unmatched_report(
        conn, report_path, name_resolution=name_resolution
    )
    named = conn.execute(
        "SELECT COUNT(*) AS c FROM prop_results WHERE player_id IS NOT NULL"
    ).fetchone()["c"]
    summary["named"] = named

    set_meta(conn, "last_clean_utc", _utc_now_iso())
    conn.commit()
    conn.close()

    rate = summary["overall_rate"]
    named_rate = (named / summary["total"]) if summary["total"] else 0.0
    print("", flush=True)
    print(
        f"MATCH RATE (odds<->player_game): {summary['matched']}/{summary['total']} = {rate:.1%} "
        f"(outcome-eligible non-void: {summary['matched_nonvoid']}; "
        f"voided flagged: {summary['voided']})",
        flush=True,
    )
    print(
        f"NAME-MAP RATE: {named}/{summary['total']} = {named_rate:.1%} "
        f"(player_id set; join may still be no_player_game for unplayed dates)",
        flush=True,
    )
    print(f"Wrote {report_path}", flush=True)
    print(f"Build stats: {build_stats}", flush=True)

    if skip_features:
        print("Skipping features rebuild (--skip-features)", flush=True)
        return 0

    from src.features import build_features

    return build_features(config_path=config_path)


def build_argparser(sub: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    p = sub or argparse.ArgumentParser(description="Phase 3 clean/join")
    p.add_argument(
        "--approve",
        action="append",
        default=[],
        help="Persist name approval raw_name=player_id (repeatable)",
    )
    p.add_argument(
        "--approvals-file",
        default=None,
        help="CSV or lines of raw_name=player_id approvals",
    )
    return p
