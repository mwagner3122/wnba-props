"""Phase 6 (3PM only): train hierarchical EB Binomial/Beta rate model."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import pandas as pd

from src.db import connect, init_schema
from src.logging_setup import setup_logging
from src.minutes_features import time_split
from src.rates_3pm_data import (
    add_asof_player_history,
    load_rates_3pm_frame,
    print_variance_to_mean,
    rates_3pm_config,
    variance_to_mean_report,
)
from src.rates_3pm_eval import evaluate_3pm
from src.rates_3pm_model import Rates3PMModel, shrinkage_summary
from src.stats_parse import load_config

logger = setup_logging()


def save_3pm_artifacts(model, cfg, metrics, shrink_df):
    models_dir = Path(cfg["models_dir"])
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / "rates_3pm_model.pkl"
    with path.open("wb") as f:
        pickle.dump({"model": model, "cfg": cfg, "metrics": metrics}, f, protocol=pickle.HIGHEST_PROTOCOL)
    meta = {
        "path": str(path), "stat": "3pm",
        "distribution": "Binomial(3PA, p3) with Beta hierarchical p3; NB attempts",
        "hierarchy": "league -> role/position -> player (empirical Bayes)",
        "opponent": "team-level 3PA-allowed factor only",
        "metrics_crps": metrics.get("crps_model"),
        "pit_shape": (metrics.get("pit") or {}).get("shape"),
    }
    (models_dir / "rates_3pm_model_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    metrics_path = Path(cfg["metrics_path"])
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    shrink_path = Path(cfg["shrinkage_summary_path"])
    shrink_df.to_csv(shrink_path, index=False)
    print(f"Saved 3PM model -> {path}", flush=True)
    print(f"Saved 3PM metrics -> {metrics_path}", flush=True)
    print(f"Saved shrinkage summary -> {shrink_path}", flush=True)
    return path


def _print_shrinkage_overview(shrink_df):
    print("", flush=True)
    print("=== Shrinkage / ESS summary (per player, latest as-of) ===", flush=True)
    print(
        f"players={len(shrink_df)}  "
        f"p3_shrink_weight mean={shrink_df['p3_shrink_weight'].mean():.3f} "
        f"p50={shrink_df['p3_shrink_weight'].median():.3f}  "
        f"ESS mean={shrink_df['ess'].mean():.1f} p50={shrink_df['ess'].median():.1f}",
        flush=True,
    )
    print(
        f"pa_shrink_weight mean={shrink_df['pa_shrink_weight'].mean():.3f} "
        f"p50={shrink_df['pa_shrink_weight'].median():.3f}",
        flush=True,
    )
    cols = ["player_id", "role", "prior_fg3a", "ess", "p3_shrink_weight", "p3_mean"]
    print("Highest p3 prior weight (small sample):", flush=True)
    print(shrink_df.nlargest(3, "p3_shrink_weight")[cols].to_string(index=False), flush=True)
    print("Lowest p3 prior weight (data-dominated):", flush=True)
    print(shrink_df.nsmallest(3, "p3_shrink_weight")[cols].to_string(index=False), flush=True)


def train_rates_3pm(config_path="config.yaml"):
    cfg_all = load_config(config_path)
    cfg = rates_3pm_config(cfg_all)
    db_path = cfg_all.get("db_path", "data/wnba.db")
    conn = connect(db_path)
    init_schema(conn)
    n_feat = conn.execute("SELECT COUNT(*) AS c FROM player_game_features").fetchone()["c"]
    if n_feat == 0:
        print("no features found — run `python run.py features` (or clean) first", flush=True)
        return 1
    print(f"Loading 3PM rate frame from {db_path} ({n_feat} feature rows)...", flush=True)
    df = add_asof_player_history(load_rates_3pm_frame(conn))
    print(f"Rows={len(df)} seasons={df['season'].min()}-{df['season'].max()} played_rate={(df['played'].mean()):.3f}", flush=True)
    vm = variance_to_mean_report(df)
    print_variance_to_mean(vm)
    train, test = time_split(df, int(cfg["train_end_season"]), int(cfg["test_start_season"]))
    print(f"Time split: train season<={cfg['train_end_season']} n={len(train)}; test season>={cfg['test_start_season']} n={len(test)} (NO random split)", flush=True)
    model = Rates3PMModel(cfg)
    print("Fitting hierarchical EB (league → role → player) for p3 Beta + 3PA rate; opponent team-level 3PA factor only...", flush=True)
    model.fit(train)
    print(f"League p3={model.league_p3:.4f}  pa_p40={model.league_pa_p40:.4f}  NB_r(attempts)={model.pa_nb_r:.3f}", flush=True)
    print(f"Role p3={ {k: round(v, 4) for k, v in model.role_p3.items()} }  Role pa_p40={ {k: round(v, 3) for k, v in model.role_pa_p40.items()} }", flush=True)
    sizes = list(model.opp_sample_size.values())
    print(f"Beta κ_role={model.kappa_role}; pa_k_role={model.pa_k_role}; opp_k={model.opp_k} (opp games min/median/max={min(sizes) if sizes else 0}/{sorted(sizes)[len(sizes)//2] if sizes else 0}/{max(sizes) if sizes else 0})", flush=True)
    shrink_df = shrinkage_summary(model.predict_params(df))
    _print_shrinkage_overview(shrink_df)
    metrics = evaluate_3pm(model, test, cfg)
    metrics.update({"variance_to_mean": vm, "train_end_season": cfg["train_end_season"], "test_start_season": cfg["test_start_season"], "stat": "3pm", "reb_ast_pts_started": False})
    save_3pm_artifacts(model, cfg, metrics, shrink_df)
    print("", flush=True)
    print("Phase 6 IN PROGRESS: 3PM complete. Rebounds / assists / points NOT started. Do NOT start phase 7.", flush=True)
    return 0


def load_rates_3pm_model(models_dir="models"):
    path = Path(models_dir) / "rates_3pm_model.pkl"
    if not path.exists():
        raise FileNotFoundError(f"no trained 3PM model at {path}; run `python run.py train --stat 3pm`")
    with path.open("rb") as f:
        return pickle.load(f)["model"]
