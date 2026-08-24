"""Unmatched report writer for phase 3 clean."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.clean_approvals import _team_display
from src.clean_prep import (
    REASON_AMBIGUOUS_TEAM,
    REASON_FUZZY,
    _utc_now_iso,
)

def write_unmatched_report(
    conn: sqlite3.Connection,
    report_path: Path,
    *,
    name_resolution: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Write reports/unmatched.md and return summary metrics."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    team_names = _team_display(conn)

    total = conn.execute("SELECT COUNT(*) AS c FROM prop_results").fetchone()["c"]
    matched = conn.execute(
        "SELECT COUNT(*) AS c FROM prop_results WHERE match_status = 'matched'"
    ).fetchone()["c"]
    matched_nonvoid = conn.execute(
        """
        SELECT COUNT(*) AS c FROM prop_results
        WHERE match_status = 'matched' AND is_voided = 0
        """
    ).fetchone()["c"]
    voided = conn.execute(
        "SELECT COUNT(*) AS c FROM prop_results WHERE is_voided = 1"
    ).fetchone()["c"]
    overall_rate = (matched / total) if total else 0.0

    by_book = conn.execute(
        """
        SELECT book,
               COUNT(*) AS n,
               SUM(CASE WHEN match_status = 'matched' THEN 1 ELSE 0 END) AS m
        FROM prop_results
        GROUP BY book
        ORDER BY book
        """
    ).fetchall()

    by_month = conn.execute(
        """
        SELECT substr(COALESCE(game_date_et, 'unknown'), 1, 7) AS month,
               COUNT(*) AS n,
               SUM(CASE WHEN match_status = 'matched' THEN 1 ELSE 0 END) AS m
        FROM prop_results
        GROUP BY month
        ORDER BY month
        """
    ).fetchall()

    by_team = conn.execute(
        """
        SELECT COALESCE(team_id, 'unmatched') AS team_id,
               COUNT(*) AS n,
               SUM(CASE WHEN match_status = 'matched' THEN 1 ELSE 0 END) AS m
        FROM prop_results
        GROUP BY team_id
        ORDER BY n DESC
        """
    ).fetchall()

    unmatched_odds = conn.execute(
        """
        SELECT player_name_raw, game_date_et, reason_code, book, COUNT(*) AS n
        FROM prop_results
        WHERE match_status != 'matched'
        GROUP BY player_name_raw, game_date_et, reason_code, book
        ORDER BY n DESC, player_name_raw
        """
    ).fetchall()

    top_names = conn.execute(
        """
        SELECT player_name_raw, COUNT(*) AS n
        FROM prop_results
        WHERE match_status != 'matched'
        GROUP BY player_name_raw
        ORDER BY n DESC, player_name_raw
        LIMIT 20
        """
    ).fetchall()

    # Player-games with no odds (expected)
    pg_no_odds = conn.execute(
        """
        SELECT pg.game_date, pg.player_name, pg.team_id, pg.player_id
        FROM player_games pg
        WHERE NOT EXISTS (
            SELECT 1 FROM prop_results pr
            WHERE pr.player_id = pg.player_id
              AND pr.game_date_et = pg.game_date
              AND pr.match_status = 'matched'
        )
        ORDER BY pg.game_date DESC, pg.player_name
        LIMIT 200
        """
    ).fetchall()
    pg_no_odds_count = conn.execute(
        """
        SELECT COUNT(*) AS c FROM player_games pg
        WHERE NOT EXISTS (
            SELECT 1 FROM prop_results pr
            WHERE pr.player_id = pg.player_id
              AND pr.game_date_et = pg.game_date
              AND pr.match_status = 'matched'
        )
        """
    ).fetchone()["c"]

    fuzzy_section: list[str] = []
    for raw, info in sorted(name_resolution.items(), key=lambda x: x[0].lower()):
        if info.get("reason_code") == REASON_FUZZY or (
            info.get("proposals") and not info.get("player_id")
        ):
            if info.get("reason_code") not in (REASON_FUZZY, REASON_AMBIGUOUS_TEAM):
                continue
            fuzzy_section.append(f"- `{raw}` ({info.get('reason_code')})")
            for p in info.get("proposals") or []:
                fuzzy_section.append(
                    f"  - propose player_id={p['player_id']} "
                    f"name={p['player_name']!r} score={p['score']}"
                )

    lines: list[str] = []
    lines.append("# Unmatched report")
    lines.append("")
    lines.append(f"Generated: `{_utc_now_iso()}` (UTC)")
    lines.append("")
    lines.append("## Match rate summary")
    lines.append("")
    lines.append(f"- Odds rows in `prop_results`: **{total}**")
    lines.append(f"- Matched (player_game found): **{matched}** ({overall_rate:.1%})")
    lines.append(f"- Matched non-void (outcome-eligible): **{matched_nonvoid}**")
    lines.append(f"- Voided (kept, outcome nulled): **{voided}**")
    named = conn.execute(
        "SELECT COUNT(*) AS c FROM prop_results WHERE player_id IS NOT NULL"
    ).fetchone()["c"]
    lines.append(
        f"- Name-mapped (player_id set, may still lack player_game): **{named}** "
        f"({(named / total) if total else 0.0:.1%})"
    )
    lines.append("")
    lines.append("### By book")
    lines.append("")
    lines.append("| Book | Rows | Matched | Rate |")
    lines.append("|---|---:|---:|---:|")
    for r in by_book:
        rate = (r["m"] / r["n"]) if r["n"] else 0.0
        lines.append(f"| {r['book']} | {r['n']} | {r['m']} | {rate:.1%} |")
    lines.append("")
    lines.append("### By month (game_date_et)")
    lines.append("")
    lines.append("| Month | Rows | Matched | Rate |")
    lines.append("|---|---:|---:|---:|")
    for r in by_month:
        rate = (r["m"] / r["n"]) if r["n"] else 0.0
        lines.append(f"| {r['month']} | {r['n']} | {r['m']} | {rate:.1%} |")
    lines.append("")
    lines.append("### By team")
    lines.append("")
    lines.append("| Team | Rows | Matched | Rate |")
    lines.append("|---|---:|---:|---:|")
    for r in by_team:
        label = team_names.get(str(r["team_id"]), str(r["team_id"]))
        rate = (r["m"] / r["n"]) if r["n"] else 0.0
        lines.append(f"| {label} | {r['n']} | {r['m']} | {rate:.1%} |")
    lines.append("")
    lines.append("## Odds rows with no player-game")
    lines.append("")
    lines.append(
        "Every unmatched odds row is retained in `prop_results` with "
        "`player_id` null or set and a `reason_code` (never silently dropped)."
    )
    lines.append("")
    lines.append("| Raw name | Date (ET) | Book | Reason | Count |")
    lines.append("|---|---|---|---|---:|")
    for r in unmatched_odds[:500]:
        lines.append(
            f"| {r['player_name_raw']} | {r['game_date_et'] or '-'} | "
            f"{r['book']} | {r['reason_code']} | {r['n']} |"
        )
    if len(unmatched_odds) > 500:
        lines.append(f"| ... | ... | ... | ... | {len(unmatched_odds) - 500} more groups |")
    lines.append("")
    lines.append("## Top 20 unmatched names by frequency")
    lines.append("")
    lines.append("| Raw name | Unmatched rows |")
    lines.append("|---|---:|")
    for r in top_names:
        lines.append(f"| {r['player_name_raw']} | {r['n']} |")
    lines.append("")
    lines.append("## Player-games with no odds (expected)")
    lines.append("")
    lines.append(
        f"Total player-games without a matched prop row: **{pg_no_odds_count}** "
        "(not everyone gets props; showing up to 200 most recent)."
    )
    lines.append("")
    lines.append("| Date | Player | Team ID | Player ID |")
    lines.append("|---|---|---|---|")
    for r in pg_no_odds:
        lines.append(
            f"| {r['game_date']} | {r['player_name']} | {r['team_id']} | {r['player_id']} |"
        )
    lines.append("")
    lines.append("## Fuzzy proposals (needs approval - NOT auto-applied)")
    lines.append("")
    if fuzzy_section:
        lines.append(
            "Approve with `python run.py clean --approve 'Raw Name=player_id'` "
            "or `--approvals-file path.csv`, then re-run clean."
        )
        lines.append("")
        lines.extend(fuzzy_section)
    else:
        lines.append("_No fuzzy proposals this run._")
    lines.append("")
    lines.append("## Reason code legend")
    lines.append("")
    lines.append("| Code | Meaning |")
    lines.append("|---|---|")
    lines.append("| `matched` | Joined to a player_game on game_date_et |")
    lines.append("| `missing_event_meta` | No commence_time/teams in odds_events for odds game_id |")
    lines.append("| `no_name_match` | Could not map raw name to player_id |")
    lines.append("| `needs_fuzzy_approval` | Fuzzy candidates printed; awaiting `--approve` |")
    lines.append("| `ambiguous_team_date` | Multiple roster hits for team+date |")
    lines.append("| `no_player_game` | Name mapped but no player_game on that ET date |")
    lines.append("")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {
        "total": total,
        "matched": matched,
        "matched_nonvoid": matched_nonvoid,
        "voided": voided,
        "overall_rate": overall_rate,
        "report_path": str(report_path),
    }
    return summary
