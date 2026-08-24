"""Phase 1 entry: wire run.py update to sportsdataverse ingest."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import sportsdataverse.wnba as wnba

from src.db import connect, get_meta, init_schema, set_meta
from src.logging_setup import setup_logging
from src.stats_build import (
    build_game_rows,
    build_player_and_availability,
    upsert_rows,
)
from src.stats_parse import (
    build_reference_tables,
    dataframe_to_records,
    dump_season_raw,
    fetch_season_frames,
    filter_franchise_games,
    load_config,
    save_raw,
    seasons_from_config,
)
from src.stats_validate import print_summary, run_validation

logger = setup_logging()

def ingest_update(config_path: str | Path = "config.yaml") -> int:
    cfg = load_config(config_path)
    db_path = cfg.get("db_path", "data/wnba.db")
    raw_dir = Path(cfg.get("raw_stats_dir", "data/raw/stats"))
    seasons = seasons_from_config(cfg)
    exclude = set(cfg.get("exclude_team_abbreviations") or [])
    fta_factor = float(cfg.get("fta_possession_factor", 0.44))
    regulation_periods = int(cfg.get("regulation_periods", 4))

    conn = connect(db_path)
    init_schema(conn)

    last_date = get_meta(conn, "last_ingested_game_date")
    logger.info("Last ingested game date: %s", last_date)

    if last_date:
        probe_season = max(seasons)
        logger.info("Checking for games after %s in season %s", last_date, probe_season)
        try:
            sched = wnba.load_wnba_schedule(seasons=[probe_season], return_as_pandas=True)
            save_raw(
                raw_dir,
                f"probe_{probe_season}_schedule_{date.today().isoformat()}.json",
                dataframe_to_records(sched),
            )
            completed = sched[sched["status_type_completed"] == True]  # noqa: E712
            if not completed.empty:
                completed = completed.copy()
                completed["game_date_str"] = completed["game_date"].astype(str).str[:10]
                newer = completed[completed["game_date_str"] > last_date]
            else:
                newer = completed
            if newer is None or len(newer) == 0:
                print("0 new games")
                checks = run_validation(conn, cfg)
                print_summary(conn, checks, new_games=0)
                conn.close()
                return 0
            seasons_to_load = [
                s for s in seasons if s >= int(str(last_date)[:4])
            ] or [probe_season]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Incremental probe failed (%s); falling back to full seasons", exc)
            seasons_to_load = seasons
    else:
        seasons_to_load = seasons

    new_game_ids: set[str] = set()
    all_player_box = []

    for season in seasons_to_load:
        frames = fetch_season_frames(season)
        dump_season_raw(raw_dir, season, frames)
        player_box = filter_franchise_games(frames["player_box"], exclude)
        if last_date:
            player_box = player_box[
                player_box["game_date"].astype(str).str[:10] > last_date
            ]
        if player_box.empty:
            logger.info("Season %s: 0 new player-box rows after filters", season)
            continue
        all_player_box.append(player_box)
        schedule = frames["schedule"]

        teams, players = build_reference_tables(player_box)
        upsert_rows(conn, "teams", teams, ["team_id"])
        upsert_rows(conn, "players", players, ["player_id"])

        game_rows = build_game_rows(player_box, schedule, fta_factor, regulation_periods)
        player_rows, avail_rows = build_player_and_availability(player_box)

        before_games = {
            r[0] for r in conn.execute("SELECT game_id FROM games").fetchall()
        }
        upsert_rows(conn, "games", game_rows, ["game_id"])
        upsert_rows(conn, "player_games", player_rows, ["game_id", "player_id"])
        upsert_rows(conn, "availability", avail_rows, ["game_id", "player_id"])
        after_ids = {g["game_id"] for g in game_rows}
        new_game_ids |= after_ids - before_games
        if not before_games:
            new_game_ids |= after_ids

        print(
            f"season {season}: games_upserted={len(game_rows)} "
            f"player_games_upserted={len(player_rows)} "
            f"availability_upserted={len(avail_rows)}"
        )

    if all_player_box:
        combined = pd.concat(all_player_box, ignore_index=True)
        max_date = str(combined["game_date"].max())[:10]
        set_meta(conn, "last_ingested_game_date", max_date)
    elif last_date is None:
        set_meta(conn, "last_ingested_game_date", "")
    conn.commit()

    n_new = len(new_game_ids)
    if n_new == 0:
        print("0 new games")
    else:
        print(f"{n_new} new games")

    checks = run_validation(conn, cfg)
    print_summary(conn, checks, new_games=n_new)
    conn.close()
    return 0
