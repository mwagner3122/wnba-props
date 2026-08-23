"""Build games/player_games/availability rows and upsert helpers."""
from __future__ import annotations
from typing import Any
import pandas as pd
from src.stats_parse import (
    _to_float,
    _to_int,
    _to_str,
    map_availability_status,
    parse_plus_minus,
    team_possessions,
)
def build_game_rows(
    player_box: pd.DataFrame,
    schedule: pd.DataFrame,
    fta_factor: float,
    regulation_periods: int,
) -> list[dict[str, Any]]:
    if player_box.empty:
        return []
    sched_by_id: dict[str, pd.Series] = {}
    if not schedule.empty:
        for _, srow in schedule.iterrows():
            gid = _to_str(srow.get("game_id") or srow.get("id"))
            if gid:
                sched_by_id[gid] = srow
    played = player_box[player_box["did_not_play"] == False].copy()  # noqa: E712
    agg_cols = {
        "field_goals_attempted": "sum",
        "offensive_rebounds": "sum",
        "turnovers": "sum",
        "free_throws_attempted": "sum",
        "team_score": "max",
        "home_away": "first",
        "season": "first",
        "season_type": "first",
        "game_date": "first",
        "team_id": "first",
        "opponent_team_id": "first",
    }
    team_game = (
        played.groupby(["game_id", "team_id"], as_index=False)
        .agg(agg_cols)
        .rename(
            columns={
                "field_goals_attempted": "fga",
                "offensive_rebounds": "oreb",
                "turnovers": "tov",
                "free_throws_attempted": "fta",
            }
        )
    )
    games: dict[str, dict[str, Any]] = {}
    for _, tg in team_game.iterrows():
        gid = _to_str(tg["game_id"])
        assert gid is not None
        poss = team_possessions(
            {
                "fga": float(tg["fga"] or 0),
                "oreb": float(tg["oreb"] or 0),
                "tov": float(tg["tov"] or 0),
                "fta": float(tg["fta"] or 0),
            },
            fta_factor,
        )
        entry = games.setdefault(
            gid,
            {
                "game_id": gid,
                "game_date": str(tg["game_date"])[:10],
                "season": _to_int(tg["season"]),
                "season_type": _to_int(tg["season_type"]),
                "home_team_id": None,
                "away_team_id": None,
                "home_score": None,
                "away_score": None,
                "overtime_periods": 0,
                "possessions_est": None,
                "pace": None,
                "home_off_rating": None,
                "away_off_rating": None,
                "attendance": None,
                "_home_poss": None,
                "_away_poss": None,
            },
        )
        ha = str(tg["home_away"]).lower()
        tid = _to_str(tg["team_id"])
        score = _to_int(tg["team_score"])
        if ha == "home":
            entry["home_team_id"] = tid
            entry["home_score"] = score
            entry["_home_poss"] = poss
        else:
            entry["away_team_id"] = tid
            entry["away_score"] = score
            entry["_away_poss"] = poss
    for gid, entry in games.items():
        srow = sched_by_id.get(gid)
        if srow is not None:
            period = _to_float(srow.get("status_period"), 4.0) or 4.0
            entry["overtime_periods"] = max(0, int(period) - regulation_periods)
            entry["attendance"] = _to_float(srow.get("attendance"), None)
            if entry["home_team_id"] is None:
                entry["home_team_id"] = _to_str(srow.get("home_id"))
            if entry["away_team_id"] is None:
                entry["away_team_id"] = _to_str(srow.get("away_id"))
            if entry["home_score"] is None:
                entry["home_score"] = _to_int(srow.get("home_score"), None)
            if entry["away_score"] is None:
                entry["away_score"] = _to_int(srow.get("away_score"), None)
        hp = entry.pop("_home_poss", None)
        ap = entry.pop("_away_poss", None)
        if hp is not None and ap is not None:
            poss_est = (hp + ap) / 2.0
        else:
            poss_est = hp if hp is not None else ap
        entry["possessions_est"] = poss_est
        ot = entry["overtime_periods"] or 0
        minutes = 40.0 + 5.0 * ot
        entry["pace"] = (poss_est / minutes * 40.0) if poss_est and minutes else None
        if hp and entry["home_score"] is not None:
            entry["home_off_rating"] = entry["home_score"] / hp * 100.0
        if ap and entry["away_score"] is not None:
            entry["away_off_rating"] = entry["away_score"] / ap * 100.0
    return list(games.values())
def build_player_and_availability(
    player_box: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    player_rows: list[dict[str, Any]] = []
    avail_rows: list[dict[str, Any]] = []
    for _, row in player_box.iterrows():
        did_not_play = bool(row.get("did_not_play"))
        minutes = 0.0 if did_not_play else (_to_float(row.get("minutes"), 0.0) or 0.0)
        reason = _to_str(row.get("reason"))
        status = map_availability_status(
            did_not_play, reason, bool(row.get("active")) if row.get("active") is not None else None
        )
        pid = _to_str(row.get("athlete_id"))
        gid = _to_str(row.get("game_id"))
        if not pid or not gid:
            continue
        player_rows.append(
            {
                "game_id": gid,
                "game_date": str(row.get("game_date"))[:10],
                "player_id": pid,
                "player_name": _to_str(row.get("athlete_display_name")),
                "team_id": _to_str(row.get("team_id")),
                "opponent_id": _to_str(row.get("opponent_team_id")),
                "home_away": _to_str(row.get("home_away")),
                "minutes": minutes,
                "fga": 0 if did_not_play else _to_int(row.get("field_goals_attempted")),
                "fgm": 0 if did_not_play else _to_int(row.get("field_goals_made")),
                "fg3a": 0
                if did_not_play
                else _to_int(row.get("three_point_field_goals_attempted")),
                "fg3m": 0 if did_not_play else _to_int(row.get("three_point_field_goals_made")),
                "fta": 0 if did_not_play else _to_int(row.get("free_throws_attempted")),
                "ftm": 0 if did_not_play else _to_int(row.get("free_throws_made")),
                "points": 0 if did_not_play else _to_int(row.get("points")),
                "oreb": 0 if did_not_play else _to_int(row.get("offensive_rebounds")),
                "dreb": 0 if did_not_play else _to_int(row.get("defensive_rebounds")),
                "reb": 0 if did_not_play else _to_int(row.get("rebounds")),
                "ast": 0 if did_not_play else _to_int(row.get("assists")),
                "stl": 0 if did_not_play else _to_int(row.get("steals")),
                "blk": 0 if did_not_play else _to_int(row.get("blocks")),
                "tov": 0 if did_not_play else _to_int(row.get("turnovers")),
                "pf": 0 if did_not_play else _to_int(row.get("fouls")),
                "plus_minus": None if did_not_play else parse_plus_minus(row.get("plus_minus")),
                "started": 0 if did_not_play else (1 if bool(row.get("starter")) else 0),
                "dnp_reason": reason if did_not_play else None,
            }
        )
        avail_rows.append(
            {
                "game_id": gid,
                "player_id": pid,
                "status": status,
                "minutes_played": minutes,
            }
        )
    return player_rows, avail_rows
def upsert_rows(conn, table: str, rows: list[dict[str, Any]], pk_cols: list[str]) -> int:
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in pk_cols)
    if updates:
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({', '.join(pk_cols)}) DO UPDATE SET {updates}"
        )
    else:
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({', '.join(pk_cols)}) DO NOTHING"
        )
    data = [tuple(r[c] for c in cols) for r in rows]
    conn.executemany(sql, data)
    return len(rows)
