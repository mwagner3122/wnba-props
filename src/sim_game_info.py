"""Game metadata helpers for phase-7 simulation."""

from __future__ import annotations

from typing import Any

def pick_sanity_game_id(conn, season: int = 2026) -> str:
    row = conn.execute(
        """
        SELECT game_id FROM games
        WHERE season = ? AND overtime_periods = 0
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY game_date DESC
        LIMIT 1
        """,
        (int(season),),
    ).fetchone()
    if row is None:
        row = conn.execute(
            """
            SELECT game_id FROM games
            WHERE overtime_periods = 0 AND home_score IS NOT NULL
            ORDER BY game_date DESC LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise RuntimeError("no completed regulation game found for sanity sim")
    return str(row["game_id"] if hasattr(row, "keys") else row[0])


def game_actuals(conn, game_id: str) -> dict[str, Any]:
    g = conn.execute(
        """
        SELECT game_id, game_date, home_team_id, away_team_id,
               home_score, away_score, pace, overtime_periods, possessions_est
        FROM games WHERE game_id = ?
        """,
        (str(game_id),),
    ).fetchone()
    if g is None:
        raise ValueError(f"unknown game {game_id}")
    info = {k: g[k] for k in g.keys()}
    info["actual_total"] = (
        float(info["home_score"]) + float(info["away_score"])
        if info["home_score"] is not None
        else None
    )
    info["posted_total"] = None  # odds ingest is player_points only so far
    reb = conn.execute(
        """
        SELECT team_id, SUM(reb) AS team_reb, SUM(points) AS team_pts,
               SUM(minutes) AS team_min
        FROM player_games WHERE game_id = ?
        GROUP BY team_id
        """,
        (str(game_id),),
    ).fetchall()
    info["team_actuals"] = {
        str(r["team_id"]): {
            "reb": float(r["team_reb"] or 0),
            "pts": float(r["team_pts"] or 0),
            "minutes": float(r["team_min"] or 0),
        }
        for r in reb
    }
    return info
