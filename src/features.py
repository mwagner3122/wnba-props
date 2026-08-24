"""Phase 4: build player_game_features and print summary."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.db import connect, init_schema, set_meta
from src.feature_columns import FEATURE_COLUMNS, KEY_COLUMNS, features_ddl
from src.feature_compute import compute_feature_frame, load_frames
from src.logging_setup import setup_logging
from src.stats_parse import load_config

logger = setup_logging()


def ensure_features_table(conn: sqlite3.Connection) -> None:
    conn.executescript(features_ddl())
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pgf_date ON player_game_features(game_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pgf_player ON player_game_features(player_id)"
    )
    conn.commit()


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def store_features(conn: sqlite3.Connection, frame: pd.DataFrame) -> int:
    ensure_features_table(conn)
    before = conn.execute("SELECT COUNT(*) AS c FROM player_game_features").fetchone()[
        "c"
    ]
    conn.execute("DELETE FROM player_game_features")
    cols = KEY_COLUMNS + FEATURE_COLUMNS
    # sqlite3 adapters: convert numpy / pandas NA
    records = []
    for row in frame[cols].itertuples(index=False, name=None):
        cleaned = []
        for v in row:
            if v is None or (isinstance(v, float) and not np.isfinite(v)):
                cleaned.append(None)
            elif isinstance(v, (np.floating, np.integer)):
                cleaned.append(v.item())
            elif isinstance(v, pd.Timestamp):
                cleaned.append(str(v.date()))
            else:
                cleaned.append(v)
        records.append(tuple(cleaned))
    placeholders = ",".join(["?"] * len(cols))
    col_sql = ",".join(cols)
    conn.executemany(
        f"INSERT INTO player_game_features ({col_sql}) VALUES ({placeholders})",
        records,
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) AS c FROM player_game_features").fetchone()[
        "c"
    ]
    print(
        f"player_game_features: {before} -> {after} rows "
        f"(deleted+rebuilt; idempotent)",
        flush=True,
    )
    return int(after)


def print_feature_summary(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = len(frame)
    print("", flush=True)
    print("=== Feature summary ===", flush=True)
    hdr = (
        f"{'name':32} {'cov%':>7} {'mean':>10} {'sd':>10} "
        f"{'min':>10} {'max':>10} {'nulls':>8} {'flag':>8}"
    )
    print(hdr, flush=True)
    print("-" * len(hdr), flush=True)
    flagged: list[str] = []
    for name in FEATURE_COLUMNS:
        s = pd.to_numeric(frame[name], errors="coerce")
        nulls = int(s.isna().sum())
        cov = 100.0 * (n - nulls) / n if n else 0.0
        valid = s.dropna()
        if len(valid):
            mean = float(valid.mean())
            sd = float(valid.std(ddof=0))
            vmin = float(valid.min())
            vmax = float(valid.max())
        else:
            mean = sd = vmin = vmax = float("nan")
        flag = ""
        if cov < 80.0:
            flag = ">20%null"
            flagged.append(name)
        elif len(valid) and sd == 0.0:
            flag = "zero_var"
            flagged.append(name)
        print(
            f"{name:32} {cov:7.1f} {mean:10.4f} {sd:10.4f} "
            f"{vmin:10.4f} {vmax:10.4f} {nulls:8d} {flag:>8}",
            flush=True,
        )
        rows.append(
            {
                "name": name,
                "coverage_pct": cov,
                "mean": mean,
                "sd": sd,
                "min": vmin,
                "max": vmax,
                "nulls": nulls,
                "flag": flag,
            }
        )
    print("", flush=True)
    if flagged:
        print(f"FLAGGED ({len(flagged)}): {', '.join(flagged)}", flush=True)
    else:
        print("FLAGGED: none", flush=True)
    return rows


def print_shrinkage_distribution(frame: pd.DataFrame) -> None:
    print("", flush=True)
    print("=== Effective shrinkage (prior weight k/(n+k)) ===", flush=True)
    for col, label in (
        ("player_form_prior_weight", "player_form"),
        ("team_prior_weight", "team"),
        ("opp_prior_weight", "opponent"),
    ):
        s = pd.to_numeric(frame[col], errors="coerce").dropna()
        if s.empty:
            print(f"  {label}: no values", flush=True)
            continue
        q = s.quantile([0.1, 0.5, 0.9]).to_dict()
        print(
            f"  {label}: n={len(s)} mean={s.mean():.3f} "
            f"p10={q[0.1]:.3f} p50={q[0.5]:.3f} p90={q[0.9]:.3f}",
            flush=True,
        )


def build_features(
    *,
    config_path: str | Path = "config.yaml",
    conn: sqlite3.Connection | None = None,
) -> int:
    cfg = load_config(str(config_path))
    db_path = Path(cfg.get("db_path", "data/wnba.db"))
    own_conn = conn is None
    if own_conn:
        conn = connect(db_path)
        init_schema(conn)
    assert conn is not None

    print("=== build player_game_features (phase 4) ===", flush=True)
    pg, games, players, teams = load_frames(conn)
    print(
        f"inputs: player_games={len(pg)} games={len(games)} "
        f"players={len(players)} teams={len(teams)}",
        flush=True,
    )
    frame = compute_feature_frame(pg, games, players, teams, cfg)
    print(f"computed feature rows: {len(frame)}", flush=True)
    store_features(conn, frame)
    print_shrinkage_distribution(frame)
    print_feature_summary(frame)

    # Expansion sanity
    abbr = {
        str(r["team_id"]): str(r["abbreviation"]).upper()
        for r in conn.execute("SELECT team_id, abbreviation FROM teams")
    }
    expansion = {
        str(a).upper()
        for a in (cfg.get("features") or {}).get(
            "expansion_team_abbreviations", ["TOR", "POR"]
        )
    }
    exp_ids = {tid for tid, a in abbr.items() if a in expansion}
    exp_rows = frame[frame["team_id"].isin(exp_ids)]
    print(
        f"expansion-team feature rows: {len(exp_rows)} "
        f"(teams={sorted(expansion)})",
        flush=True,
    )
    if len(exp_rows) == 0:
        print("WARNING: no expansion-team rows found", flush=True)
    else:
        null_crash = exp_rows[FEATURE_COLUMNS].isna().all(axis=1).sum()
        print(
            f"expansion rows with all-null features: {int(null_crash)}",
            flush=True,
        )

    set_meta(conn, "last_features_utc", _utc_now_iso())
    conn.commit()
    if own_conn:
        conn.close()
    return 0


def main() -> int:
    return build_features()


if __name__ == "__main__":
    raise SystemExit(main())
