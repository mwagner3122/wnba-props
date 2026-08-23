"""Quota projection and snapshot summary printing (phase 2)."""

from __future__ import annotations

import sqlite3
from typing import Any

def project_monthly_usage(ocfg: dict[str, Any]) -> dict[str, Any]:
    snapshots_per_day = float(ocfg.get("snapshots_per_day", 4))
    games_per_slate = float(ocfg.get("games_per_slate", 7))
    markets = ocfg.get("markets") or [ocfg.get("market", "player_points")]
    if isinstance(markets, str):
        markets = [markets]
    n_markets = max(1, len(markets))
    regions = str(ocfg.get("regions", "us")).split(",")
    n_regions = max(1, len([r for r in regions if r.strip()]))
    # Event-odds cost ≈ unique markets returned × regions (guide / API docs).
    credits_per_game = n_markets * n_regions
    credits_per_day = snapshots_per_day * games_per_slate * credits_per_game
    credits_per_month = credits_per_day * 30
    cadence = ocfg.get("capture_cadence") or {}
    return {
        "snapshots_per_day": snapshots_per_day,
        "games_per_slate": games_per_slate,
        "markets": list(markets),
        "regions": [r.strip() for r in regions if r.strip()],
        "credits_per_game": credits_per_game,
        "credits_per_day": credits_per_day,
        "credits_per_month": credits_per_month,
        "capture_cadence": cadence,
        "near_tip_is_closing_line": True,
    }


def print_quota_and_projection(
    quota: dict[str, str | None] | None,
    ocfg: dict[str, Any],
    *,
    dry_run: bool,
) -> None:
    proj = project_monthly_usage(ocfg)
    if dry_run or quota is None:
        print("Odds API remaining credits: N/A (dry-run)")
        print("Odds API credits used: N/A (dry-run)")
        print("Odds API last call cost: N/A (dry-run)")
    else:
        print(f"Odds API remaining credits: {quota.get('x-requests-remaining', 'unknown')}")
        print(f"Odds API credits used: {quota.get('x-requests-used', 'unknown')}")
        print(f"Odds API last call cost: {quota.get('x-requests-last', 'unknown')}")
    print(
        "Projected monthly usage at configured cadence: "
        f"{proj['credits_per_month']:.0f} credits "
        f"({proj['snapshots_per_day']:g} snapshots/day × "
        f"{proj['games_per_slate']:g} games/slate × "
        f"{proj['credits_per_game']} credits/game × 30 days)"
    )
    cadence = proj["capture_cadence"]
    if cadence:
        enabled = [k for k, v in cadence.items() if v]
        print(
            "Capture cadence (scheduling is phase 10): "
            + ", ".join(enabled)
            + ". near_tip = closing line."
        )


def print_snapshot_summary(conn: sqlite3.Connection, inserted: int, captured_at: str) -> None:
    total = conn.execute("SELECT COUNT(*) AS n FROM odds_snapshots").fetchone()["n"]
    books = conn.execute(
        "SELECT COUNT(DISTINCT book) AS n FROM odds_snapshots WHERE captured_at_utc = ?",
        (captured_at,),
    ).fetchone()["n"]
    markets = conn.execute(
        "SELECT COUNT(DISTINCT market) AS n FROM odds_snapshots WHERE captured_at_utc = ?",
        (captured_at,),
    ).fetchone()["n"]
    games = conn.execute(
        "SELECT COUNT(DISTINCT game_id) AS n FROM odds_snapshots WHERE captured_at_utc = ?",
        (captured_at,),
    ).fetchone()["n"]
    players = conn.execute(
        "SELECT COUNT(DISTINCT player_name_raw) AS n FROM odds_snapshots WHERE captured_at_utc = ?",
        (captured_at,),
    ).fetchone()["n"]
    print(
        f"Odds snapshot summary: inserted={inserted} captured_at_utc={captured_at} "
        f"games={games} books={books} markets={markets} players={players} "
        f"table_total={total}"
    )
