"""Phase 6 (rebounds only): train hierarchical EB NegativeBinomial rate model."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from src.db import connect, init_schema
from src.logging_setup import setup_logging
from src.minutes_features import time_split
from src.rates_reb_data import (
    add_asof_player_history,
    load_rates_reb_frame,
    print_variance_to_mean,
    rates_reb_config,
    variance_to_mean_report,
)
from src.rates_reb_eval import evaluate_reb
from src.rates_reb_model import RatesRebModel, shrinkage_summary
from src.stats_parse import load_config

logger = setup_logging()


def save_reb_artifacts(model, cfg, metrics, shrink_df):
    models_dir = Path(cfg["models_dir"])
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / "rates_reb_model.pkl"
    with path.open("wb") as f:
        pickle.dump(
            {"model": model, "cfg": cfg, "metrics": metrics},
            f,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    meta = {
        "path": str(path),
        "stat": "reb",
        "distribution": "NegativeBinomial(mu=reb_p40*min/40*opp_factor, r); NOT Poisson",
        "hierarchy": "league -> role/position -> player (empirical Bayes)",
        "opponent": "team-level reb-allowed factor only",
        "metrics_crps": metrics.get("crps_model"),
        "pit_shape": (metrics.get("pit") or {}).get("shape"),
        "nb_r": metrics.get("nb_r"),
        "var_to_mean_reb": ((metrics.get("variance_to_mean") or {}).get("reb") or {}).get(
            "var_to_mean"
        ),
    }
    (models_dir / "rates_reb_model_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    metrics_path = Path(cfg["metrics_path"])
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    shrink_path = Path(cfg["shrinkage_summary_path"])
    shrink_df.to_csv(shrink_path, index=False)
    print(f"Saved reb model -> {path}", flush=True)
    print(f"Saved reb metrics -> {metrics_path}", flush=True)
    print(f"Saved shrinkage summary -> {shrink_path}", flush=True)
    return path


def _print_shrinkage_overview(shrink_df):
    print("", flush=True)
    print("=== Shrinkage / ESS summary (per player, latest as-of) ===", flush=True)
    print(
        f"players={len(shrink_df)}  "
        f"reb_shrink_weight mean={shrink_df['reb_shrink_weight'].mean():.3f} "
        f"p50={shrink_df['reb_shrink_weight'].median():.3f}  "
        f"ESS mean={shrink_df['ess'].mean():.1f} p50={shrink_df['ess'].median():.1f}",
        flush=True,
    )
    cols = ["player_id", "role", "prior_reb", "ess", "reb_shrink_weight", "reb_p40"]
    print("Highest prior weight (small sample):", flush=True)
    print(shrink_df.nlargest(3, "reb_shrink_weight")[cols].to_string(index=False), flush=True)
    print("Lowest prior weight (data-dominated):", flush=True)
    print(shrink_df.nsmallest(3, "reb_shrink_weight")[cols].to_string(index=False), flush=True)


def train_rates_reb(config_path="config.yaml"):
    cfg_all = load_config(config_path)
    cfg = rates_reb_config(cfg_all)
    db_path = cfg_all.get("db_path", "data/wnba.db")
    conn = connect(db_path)
    init_schema(conn)
    n_feat = conn.execute("SELECT COUNT(*) AS c FROM player_game_features").fetchone()["c"]
    if n_feat == 0:
        print("no features found — run `python run.py features` (or clean) first", flush=True)
        return 1
    print(f"Loading reb rate frame from {db_path} ({n_feat} feature rows)...", flush=True)
    df = add_asof_player_history(load_rates_reb_frame(conn))
    print(
        f"Rows={len(df)} seasons={df['season'].min()}-{df['season'].max()} "
        f"played_rate={(df['played'].mean()):.3f}",
        flush=True,
    )
    vm = variance_to_mean_report(df)
    print_variance_to_mean(vm)
    train, test = time_split(
        df, int(cfg["train_end_season"]), int(cfg["test_start_season"])
    )
    print(
        f"Time split: train season<={cfg['train_end_season']} n={len(train)}; "
        f"test season>={cfg['test_start_season']} n={len(test)} (NO random split)",
        flush=True,
    )
    model = RatesRebModel(cfg)
    print(
        "Fitting hierarchical EB (league → role → player) for reb_p40; "
        "NB dispersion; opponent team-level reb-allowed factor only...",
        flush=True,
    )
    model.fit(train)
    print(
        f"League reb_p40={model.league_reb_p40:.4f}  NB_r={model.nb_r:.3f}",
        flush=True,
    )
    print(
        f"Role reb_p40={ {k: round(v, 3) for k, v in model.role_reb_p40.items()} }",
        flush=True,
    )
    sizes = list(model.opp_sample_size.values())
    print(
        f"reb_k_role={model.reb_k_role}; opp_k={model.opp_k} "
        f"(opp games min/median/max="
        f"{min(sizes) if sizes else 0}/"
        f"{sorted(sizes)[len(sizes)//2] if sizes else 0}/"
        f"{max(sizes) if sizes else 0})",
        flush=True,
    )
    shrink_df = shrinkage_summary(model.predict_params(df))
    _print_shrinkage_overview(shrink_df)
    metrics = evaluate_reb(model, test, cfg)
    metrics.update(
        {
            "variance_to_mean": vm,
            "train_end_season": cfg["train_end_season"],
            "test_start_season": cfg["test_start_season"],
            "stat": "reb",
            "ast_pts_started": False,
            "phase7_started": False,
        }
    )
    save_reb_artifacts(model, cfg, metrics, shrink_df)
    print("", flush=True)
    print(
        "Phase 6 IN PROGRESS: 3PM done, reb done. Assists / points NOT started. "
        "Do NOT start phase 7.",
        flush=True,
    )
    return 0


def load_rates_reb_model(models_dir="models"):
    path = Path(models_dir) / "rates_reb_model.pkl"
    if not path.exists():
        raise FileNotFoundError(
            f"no trained reb model at {path}; run `python run.py train --stat reb`"
        )
    with path.open("rb") as f:
        return pickle.load(f)["model"]
