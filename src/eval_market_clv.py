"""Binary metrics vs posted line + CLV — skip honestly when odds history is missing."""

from __future__ import annotations

import sqlite3
from typing import Any


def inspect_odds_for_evaluation(conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Determine whether historical posted/closing lines with realized outcomes exist.

    Phase-9 binary metrics and CLV require capture-time prices joined to results.
    Substituting a different price and calling it closing is forbidden.
    """
    n_odds = int(conn.execute("SELECT COUNT(*) FROM odds_snapshots").fetchone()[0])
    n_prop = int(conn.execute("SELECT COUNT(*) FROM prop_results").fetchone()[0])
    n_with_actual = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM prop_results
            WHERE actual_points IS NOT NULL
              AND COALESCE(is_voided, 0) = 0
            """
        ).fetchone()[0]
    )
    n_matched = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM prop_results
            WHERE stats_game_id IS NOT NULL
              AND reason_code = 'matched'
            """
        ).fetchone()[0]
    )
    # Closing: require multiple captures per (game, book, market, player, line)
    # or an explicit near-tip / closing tag. We have neither historically.
    n_capture_times = int(
        conn.execute("SELECT COUNT(DISTINCT captured_at_utc) FROM odds_snapshots").fetchone()[0]
    )
    closing_available = False
    posted_with_outcomes = n_with_actual > 0 and n_matched > 0

    skip_binary_reason = None
    if not posted_with_outcomes:
        skip_binary_reason = (
            "No historical posted lines joined to realized outcomes in prop_results "
            f"(odds_snapshots={n_odds}, prop_results={n_prop}, matched={n_matched}, "
            f"non-void with actual_points={n_with_actual}). "
            "Current odds are future tips only (no_player_game). "
            "Binary log loss / Brier / reliability vs posted line SKIPPED — "
            "not substituted."
        )

    skip_clv_reason = None
    if not closing_available:
        skip_clv_reason = (
            "Closing lines unavailable. Distinct capture timestamps in odds_snapshots="
            f"{n_capture_times}; no near-tip/closing snapshots for completed games. "
            "CLV SKIPPED — not substituting open/midday/other prices as closing."
        )

    skip_baseline4_reason = None
    if not posted_with_outcomes:
        skip_baseline4_reason = (
            "De-vigged market probability baseline requires posted two-way prices on "
            "completed props; none available with realized outcomes. Baseline 4 = N/A."
        )

    return {
        "n_odds_snapshots": n_odds,
        "n_prop_results": n_prop,
        "n_matched": n_matched,
        "n_with_actual": n_with_actual,
        "n_capture_times": n_capture_times,
        "closing_available": closing_available,
        "posted_with_outcomes": posted_with_outcomes,
        "skip_binary_reason": skip_binary_reason,
        "skip_clv_reason": skip_clv_reason,
        "skip_baseline4_reason": skip_baseline4_reason,
    }
