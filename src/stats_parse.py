"""Parse sportsdataverse frames into DB rows."""
from __future__ import annotations
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
import pandas as pd
import sportsdataverse.wnba as wnba
import yaml
from src.logging_setup import setup_logging
from src.stats_constants import (
    AVAIL_STATUSES,
    INACTIVE_TOKENS,
    INJURY_TOKENS,
    REST_TOKENS,
)
logger = setup_logging()
def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
def seasons_from_config(cfg: dict[str, Any]) -> list[int]:
    if "seasons" in cfg and cfg["seasons"]:
        return [int(s) for s in cfg["seasons"]]
    start = int(cfg["start_season"])
    end = int(cfg["end_season"])
    return list(range(start, end + 1))
def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.isoformat()
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    if pd.isna(obj):
        return None
    return str(obj)
def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    clean = df.copy()
    for col in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[col]) or str(clean[col].dtype).startswith(
            "date"
        ):
            clean[col] = clean[col].astype(str)
    records = clean.to_dict(orient="records")
    out: list[dict[str, Any]] = []
    for row in records:
        fixed: dict[str, Any] = {}
        for k, v in row.items():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                fixed[k] = None
            elif isinstance(v, (datetime, date, pd.Timestamp)):
                fixed[k] = v.isoformat()
            elif hasattr(v, "item"):
                try:
                    fixed[k] = v.item()
                except Exception:
                    fixed[k] = _json_default(v)
            else:
                try:
                    if pd.isna(v):
                        fixed[k] = None
                    else:
                        fixed[k] = v
                except Exception:
                    fixed[k] = _json_default(v)
        out.append(fixed)
    return out
def save_raw(raw_dir: Path, name: str, payload: Any) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=_json_default)
    return path
def _to_int(v: Any, default: int | None = 0) -> int | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
def _to_float(v: Any, default: float | None = 0.0) -> float | None:
    if v is None:
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
def _to_str(v: Any) -> str | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return str(v)
def parse_plus_minus(v: Any) -> int | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    s = str(v).strip().replace("+", "")
    if s == "" or s.lower() == "nan":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None
def map_availability_status(did_not_play: bool, reason: str | None, active: bool | None) -> str:
    if not did_not_play:
        return "played"
    r = (reason or "").upper().strip()
    if any(tok in r for tok in REST_TOKENS):
        return "dnp_rest"
    if any(tok in r for tok in INACTIVE_TOKENS):
        return "inactive"
    if "COACH" in r or r == "":
        return "dnp_coach"
    if any(tok in r for tok in INJURY_TOKENS):
        return "dnp_injury"
    if r and not re.search(r"COACH", r):
        return "dnp_injury"
    return "dnp_coach"
def fetch_season_frames(season: int) -> dict[str, pd.DataFrame]:
    """Load sportsdataverse parquet loaders for one season (before parsing)."""
    logger.info("Fetching sportsdataverse WNBA loaders for season %s", season)
    player_box = wnba.load_wnba_player_boxscore(seasons=[season], return_as_pandas=True)
    team_box = wnba.load_wnba_team_boxscore(seasons=[season], return_as_pandas=True)
    schedule = wnba.load_wnba_schedule(seasons=[season], return_as_pandas=True)
    try:
        pbp = wnba.load_wnba_pbp(seasons=[season], return_as_pandas=True)
    except Exception as exc:  # noqa: BLE001 — PBP optional for possession est
        logger.warning("PBP load failed for %s (%s); continuing with box scores", season, exc)
        pbp = pd.DataFrame()
    return {
        "player_box": player_box,
        "team_box": team_box,
        "schedule": schedule,
        "pbp": pbp,
    }
def dump_season_raw(raw_dir: Path, season: int, frames: dict[str, pd.DataFrame]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for key, df in frames.items():
        out = raw_dir / f"{season}_{key}.json"
        if df is None or df.empty:
            out.write_text("[]", encoding="utf-8")
            logger.info("Raw wrote %s (0 rows)", out)
            continue
        clean = df.copy()
        for col in clean.columns:
            dtype = str(clean[col].dtype)
            if "date" in dtype or "time" in dtype:
                clean[col] = clean[col].astype(str)
        clean.to_json(out, orient="records", date_format="iso", default_handler=str)
        logger.info("Raw wrote %s (%s rows)", out, len(clean))
def filter_franchise_games(
    player_box: pd.DataFrame, exclude_abbrs: set[str]
) -> pd.DataFrame:
    if player_box.empty:
        return player_box
    abbr = player_box["team_abbreviation"].astype(str)
    opp = player_box["opponent_team_abbreviation"].astype(str)
    mask = ~abbr.isin(exclude_abbrs) & ~opp.isin(exclude_abbrs)
    return player_box.loc[mask].copy()
def build_reference_tables(
    player_box: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    teams: dict[str, dict[str, Any]] = {}
    players: dict[str, dict[str, Any]] = {}
    for _, row in player_box.iterrows():
        tid = _to_str(row.get("team_id"))
        if tid and tid not in teams:
            teams[tid] = {
                "team_id": tid,
                "abbreviation": _to_str(row.get("team_abbreviation")),
                "location": _to_str(row.get("team_location")),
                "name": _to_str(row.get("team_name")),
                "display_name": _to_str(row.get("team_display_name")),
            }
        oid = _to_str(row.get("opponent_team_id"))
        if oid and oid not in teams:
            teams[oid] = {
                "team_id": oid,
                "abbreviation": _to_str(row.get("opponent_team_abbreviation")),
                "location": _to_str(row.get("opponent_team_location")),
                "name": _to_str(row.get("opponent_team_name")),
                "display_name": _to_str(row.get("opponent_team_display_name")),
            }
        pid = _to_str(row.get("athlete_id"))
        if pid and pid not in players:
            players[pid] = {
                "player_id": pid,
                "player_name": _to_str(row.get("athlete_display_name")),
                "position": _to_str(row.get("athlete_position_abbreviation")),
            }
    return list(teams.values()), list(players.values())
def team_possessions(row_stats: dict[str, float], fta_factor: float) -> float:
    return (
        row_stats["fga"]
        - row_stats["oreb"]
        + row_stats["tov"]
        + fta_factor * row_stats["fta"]
    )
