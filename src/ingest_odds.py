"""Phase 2 entry: fetch or dry-run-parse odds into odds_snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.db import connect, init_schema
from src.logging_setup import setup_logging
from src.odds_http import (
    _api_key,
    _iso_utc,
    _odds_cfg,
    _utc_now,
    fetch_event_odds,
    fetch_events,
    find_latest_raw,
    load_raw_payload,
    save_raw_odds,
)
from src.odds_parse import (
    insert_snapshots,
    parse_event_odds_rows,
    parse_raw_payload,
)
from src.odds_report import (
    print_quota_and_projection,
    print_snapshot_summary,
    project_monthly_usage,
)
from src.stats_parse import load_config

logger = setup_logging()

__all__ = [
    "ingest_odds",
    "parse_event_odds_rows",
    "parse_raw_payload",
    "project_monthly_usage",
]

def _live_fetch_bundle(
    ocfg: dict[str, Any],
    api_key: str,
) -> tuple[dict[str, Any], dict[str, str | None]]:
    sport_key = str(ocfg.get("sport_key", "basketball_wnba"))
    market = str(ocfg.get("market", "player_points"))
    markets = ocfg.get("markets") or [market]
    if isinstance(markets, str):
        markets = [markets]
    markets_param = ",".join(str(m) for m in markets)
    regions = str(ocfg.get("regions", "us"))
    odds_format = str(ocfg.get("odds_format", "american"))
    captured_at = _utc_now()
    captured_iso = _iso_utc(captured_at)
    quota: dict[str, str | None] = {
        "x-requests-remaining": None,
        "x-requests-used": None,
        "x-requests-last": None,
    }

    try:
        events = fetch_events(sport_key, api_key, quota)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to list WNBA events: %s", exc)
        raise

    if not events:
        logger.info("No WNBA events returned (no games today / none listed)")

    event_odds_list: list[dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            logger.error("Skipping malformed event entry")
            continue
        eid = ev.get("id")
        if not eid:
            logger.error("Event missing id; skipping")
            continue
        try:
            odds = fetch_event_odds(
                sport_key,
                str(eid),
                api_key,
                regions=regions,
                markets=markets_param,
                odds_format=odds_format,
                quota=quota,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("HTTP/network error fetching odds for event %s: %s", eid, exc)
            # Mid-run network failure: log and re-raise so caller exits cleanly.
            raise
        if odds is None:
            logger.info("No odds payload for event %s", eid)
            continue
        if not odds.get("bookmakers"):
            logger.info("Game %s has no props posted", eid)
        event_odds_list.append(odds)

    payload = {
        "captured_at_utc": captured_iso,
        "sport_key": sport_key,
        "market": market,
        "markets": list(markets),
        "regions": regions,
        "odds_format": odds_format,
        "events": events,
        "event_odds": event_odds_list,
        "_fixture": False,
    }
    return payload, quota


def ingest_odds(
    config_path: str | Path = "config.yaml",
    *,
    dry_run: bool = False,
) -> int:
    """Fetch (or dry-run parse) odds and append rows to odds_snapshots.

    Returns 0 on success (including empty slate), 1 on hard failure that stops the run.
    """
    cfg = load_config(config_path)
    ocfg = _odds_cfg(cfg)
    db_path = cfg.get("db_path", "data/wnba.db")
    raw_dir = Path(ocfg.get("raw_odds_dir", "data/raw/odds"))
    fixture_path = Path(
        ocfg.get("fixture_path", "tests/fixtures/odds/event_odds_fixture.json")
    )
    market = str(ocfg.get("market", "player_points"))

    conn = connect(db_path)
    init_schema(conn)

    quota: dict[str, str | None] | None = None
    payload: dict[str, Any]

    try:
        if dry_run:
            latest = find_latest_raw(raw_dir)
            if latest is None:
                if not fixture_path.is_file():
                    logger.error(
                        "Dry-run: no files in %s and fixture missing at %s",
                        raw_dir,
                        fixture_path,
                    )
                    print_quota_and_projection(None, ocfg, dry_run=True)
                    conn.close()
                    return 1
                logger.info(
                    "Dry-run: no raw odds yet; using committed fixture %s",
                    fixture_path,
                )
                latest = fixture_path
            else:
                logger.info("Dry-run: parsing %s (no network)", latest)
            try:
                payload = load_raw_payload(latest)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to load raw odds file: %s", exc)
                print_quota_and_projection(None, ocfg, dry_run=True)
                conn.close()
                return 1
            # Re-stamp capture time to "when we parsed" only if fixture lacked one;
            # prefer embedded captured_at_utc from the raw file.
            if not payload.get("captured_at_utc"):
                payload["captured_at_utc"] = _iso_utc()
        else:
            api_key = _api_key()
            if not api_key:
                logger.error(
                    "ODDS_API_KEY missing. Set it in .env (gitignored). "
                    "Use --dry-run / --odds-dry-run against a raw file or fixture."
                )
                print_quota_and_projection(None, ocfg, dry_run=True)
                conn.close()
                return 1
            try:
                payload, quota = _live_fetch_bundle(ocfg, api_key)
            except Exception as exc:  # noqa: BLE001
                logger.error("Odds ingest aborted due to network/API failure: %s", exc)
                print_quota_and_projection(quota, ocfg, dry_run=False)
                conn.close()
                return 1
            raw_path = save_raw_odds(raw_dir, _utc_now(), payload)
            logger.info("Wrote raw odds to %s", raw_path)

        captured_at = str(payload.get("captured_at_utc") or _iso_utc())
        try:
            rows = parse_raw_payload(payload, market)
        except Exception as exc:  # noqa: BLE001
            logger.error("Malformed response while parsing odds: %s", exc)
            rows = []

        inserted = insert_snapshots(conn, rows)
        print_snapshot_summary(conn, inserted, captured_at)
        print_quota_and_projection(quota, ocfg, dry_run=dry_run)
        conn.close()
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected odds ingest failure: %s", exc)
        try:
            print_quota_and_projection(quota, ocfg, dry_run=dry_run)
        except Exception:  # noqa: BLE001
            pass
        conn.close()
        return 1
