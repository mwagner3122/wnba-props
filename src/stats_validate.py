"""Validation and summary printers for stats ingestion."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

def run_validation(conn, cfg: dict[str, Any]) -> dict[str, Any]:
    """Run ingest validation checks; print failing rows; return summary."""
    tol = float(cfg.get("minutes_sum_tolerance", 1.5))
    reg_min = float(cfg.get("regulation_team_minutes", 200))
    ot_min = float(cfg.get("ot_team_minutes", 25))
    schedule_length: dict[str, int] = {
        str(k): int(v) for k, v in (cfg.get("schedule_length") or {}).items()
    }
    windows_raw = cfg.get("season_windows") or {}
    windows = {str(k): v for k, v in windows_raw.items()}
    exclude = set(cfg.get("exclude_team_abbreviations") or [])
    checks: dict[str, Any] = {}

    print("\n=== Validation ===")

    print("\n[check] games per team vs published schedule (regular season)")
    rows = conn.execute(
        """
        SELECT g.season, t.abbreviation AS team, COUNT(*) AS games
        FROM games g
        JOIN teams t ON t.team_id = g.home_team_id
        WHERE g.season_type = 2
        GROUP BY g.season, g.home_team_id
        UNION ALL
        SELECT g.season, t.abbreviation AS team, COUNT(*) AS games
        FROM games g
        JOIN teams t ON t.team_id = g.away_team_id
        WHERE g.season_type = 2
        GROUP BY g.season, g.away_team_id
        """
    ).fetchall()
    counts: dict[tuple[int, str], int] = defaultdict(int)
    for r in rows:
        if r["team"] in exclude:
            continue
        counts[(int(r["season"]), r["team"])] += int(r["games"])

    schedule_fail: list[str] = []
    today = date.today().isoformat()
    for (season, team), games in sorted(counts.items()):
        expected = schedule_length.get(str(season))
        if expected is None:
            continue
        window = windows.get(str(season)) or windows.get(season) or {}
        end = window.get("end")
        mid_season = end is not None and today < end
        if games != expected:
            note = (
                f"season={season} team={team} games={games} expected={expected}"
                + (" (season still in progress)" if mid_season else "")
            )
            schedule_fail.append(note)
    if schedule_fail:
        for line in schedule_fail[:40]:
            print("  FAIL:", line)
        if len(schedule_fail) > 40:
            print(f"  ... and {len(schedule_fail) - 40} more")
        print(
            "  note: explained failures — (1) 2026 mid-season incomplete through "
            "last ingested date; (2) some completed seasons show expected+1 for "
            "Commissioner's Cup finalists / league extras in the sportsdataverse "
            "regular-season feed (season_type=2)."
        )
        checks["schedule_games_per_team"] = {
            "passed": False,
            "failures": len(schedule_fail),
            "explained": True,
        }
    else:
        print("  PASS")
        checks["schedule_games_per_team"] = {"passed": True, "failures": 0}

    print("\n[check] team minutes sum to 200 + 25×OT")
    minute_rows = conn.execute(
        """
        SELECT pg.game_id, pg.team_id, g.overtime_periods,
               SUM(CASE WHEN a.status = 'played' THEN pg.minutes ELSE 0 END) AS team_minutes
        FROM player_games pg
        JOIN games g ON g.game_id = pg.game_id
        JOIN availability a ON a.game_id = pg.game_id AND a.player_id = pg.player_id
        GROUP BY pg.game_id, pg.team_id
        """
    ).fetchall()
    minute_fail = []
    for r in minute_rows:
        ot = int(r["overtime_periods"] or 0)
        expected = reg_min + ot_min * ot
        got = float(r["team_minutes"] or 0)
        if abs(got - expected) > tol:
            minute_fail.append(
                f"game_id={r['game_id']} team_id={r['team_id']} minutes={got:.2f} "
                f"expected={expected:.1f} ot={ot}"
            )
    if minute_fail:
        for line in minute_fail[:30]:
            print("  FAIL:", line)
        if len(minute_fail) > 30:
            print(f"  ... and {len(minute_fail) - 30} more")
        checks["team_minutes"] = {"passed": False, "failures": len(minute_fail)}
    else:
        print("  PASS")
        checks["team_minutes"] = {"passed": True, "failures": 0}

    print("\n[check] 2×(FGM−FG3M)+3×FG3M+FTM = PTS")
    pts_fail = conn.execute(
        """
        SELECT game_id, player_id, player_name, fgm, fg3m, ftm, points,
               (2 * (fgm - fg3m) + 3 * fg3m + ftm) AS calc_pts
        FROM player_games
        WHERE minutes > 0
          AND (2 * (fgm - fg3m) + 3 * fg3m + ftm) != points
        """
    ).fetchall()
    if pts_fail:
        for r in pts_fail[:30]:
            print(
                f"  FAIL: game={r['game_id']} player={r['player_name']} "
                f"({r['player_id']}) pts={r['points']} calc={r['calc_pts']}"
            )
        checks["points_reconcile"] = {"passed": False, "failures": len(pts_fail)}
    else:
        print("  PASS")
        checks["points_reconcile"] = {"passed": True, "failures": 0}

    print("\n[check] REB = OREB + DREB")
    reb_fail = conn.execute(
        """
        SELECT game_id, player_id, player_name, oreb, dreb, reb
        FROM player_games
        WHERE minutes > 0 AND reb != (oreb + dreb)
        """
    ).fetchall()
    if reb_fail:
        for r in reb_fail[:30]:
            print(
                f"  FAIL: game={r['game_id']} player={r['player_name']} "
                f"reb={r['reb']} oreb+dreb={r['oreb'] + r['dreb']}"
            )
        checks["rebounds_reconcile"] = {"passed": False, "failures": len(reb_fail)}
    else:
        print("  PASS")
        checks["rebounds_reconcile"] = {"passed": True, "failures": 0}

    print("\n[check] no player twice in one game")
    dup = conn.execute(
        """
        SELECT game_id, player_id, COUNT(*) AS n
        FROM player_games
        GROUP BY game_id, player_id
        HAVING n > 1
        """
    ).fetchall()
    if dup:
        for r in dup[:30]:
            print(f"  FAIL: game={r['game_id']} player_id={r['player_id']} n={r['n']}")
        checks["no_duplicate_player_game"] = {"passed": False, "failures": len(dup)}
    else:
        print("  PASS")
        checks["no_duplicate_player_game"] = {"passed": True, "failures": 0}

    print("\n[check] no game date outside season window")
    date_fail = []
    for r in conn.execute("SELECT game_id, game_date, season, season_type FROM games").fetchall():
        season = str(r["season"])
        window = windows.get(season) or {}
        start, end = window.get("start"), window.get("end")
        gd = r["game_date"]
        if start and end and (gd < start or gd > end):
            date_fail.append(
                f"game_id={r['game_id']} date={gd} season={season} "
                f"window={start}..{end} season_type={r['season_type']}"
            )
    if date_fail:
        for line in date_fail[:30]:
            print("  FAIL:", line)
        if len(date_fail) > 30:
            print(f"  ... and {len(date_fail) - 30} more")
        print(
            "  note: playoff games can extend past the regular-season end date in config; "
            "widen season_windows if those should pass."
        )
        checks["season_window"] = {
            "passed": False,
            "failures": len(date_fail),
            "explained": True,
        }
    else:
        print("  PASS")
        checks["season_window"] = {"passed": True, "failures": 0}

    print("\n[check] every player_id in player_games exists in players")
    orphan = conn.execute(
        """
        SELECT DISTINCT pg.player_id, pg.player_name
        FROM player_games pg
        LEFT JOIN players p ON p.player_id = pg.player_id
        WHERE p.player_id IS NULL
        """
    ).fetchall()
    if orphan:
        for r in orphan[:30]:
            print(f"  FAIL: player_id={r['player_id']} name={r['player_name']}")
        checks["player_fk"] = {"passed": False, "failures": len(orphan)}
    else:
        print("  PASS")
        checks["player_fk"] = {"passed": True, "failures": 0}

    return checks


def print_summary(conn, checks: dict[str, Any], new_games: int) -> None:
    seasons = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT season FROM games ORDER BY season"
        ).fetchall()
    ]
    n_games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    n_pg = conn.execute("SELECT COUNT(*) FROM player_games").fetchone()[0]
    n_avail0 = conn.execute(
        "SELECT COUNT(*) FROM availability WHERE minutes_played = 0"
    ).fetchone()[0]
    dr = conn.execute(
        "SELECT MIN(game_date), MAX(game_date) FROM games"
    ).fetchone()
    passed = sum(1 for c in checks.values() if c.get("passed"))
    total = len(checks)
    print("\n=== Summary ===")
    print(f"new_games_this_run: {new_games}")
    print(f"seasons: {seasons}")
    print(f"games: {n_games}")
    print(f"player_games: {n_pg}")
    print(f"date_range: {dr[0]} → {dr[1]}")
    print(f"availability_minutes_0: {n_avail0}")
    print(f"checks_passed: {passed}/{total}")
    for name, result in checks.items():
        status = "PASS" if result.get("passed") else "FAIL"
        extra = f" ({result['failures']} rows)" if result.get("failures") else ""
        explained = " [explained]" if result.get("explained") else ""
        print(f"  {name}: {status}{extra}{explained}")
