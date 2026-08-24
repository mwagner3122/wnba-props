"""Phase 5: two-stage minutes model train entrypoint."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from src.db import connect, init_schema
from src.logging_setup import setup_logging
from src.minutes_features import load_minutes_frame, minutes_config, time_split
from src.minutes_sim import minutes_from_shares, sample_dirichlet_minutes
from src.model_minutes_core import QUANTILES, MinutesModel
from src.model_minutes_eval import evaluate_minutes
from src.stats_parse import load_config

logger = setup_logging()

def save_artifacts(
    model: MinutesModel, cfg: dict[str, Any], metrics: dict[str, Any]
) -> Path:
    models_dir = Path(cfg["models_dir"])
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / "minutes_model.pkl"
    payload = {
        "model": model,
        "feature_columns": model.feature_columns,
        "cfg": cfg,
        "metrics": metrics,
    }
    with path.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    meta = {
        "path": str(path),
        "feature_columns": model.feature_columns,
        "quantiles": list(QUANTILES),
        "share_method": cfg.get("share_method"),
        "metrics_status": metrics.get("status"),
    }
    (models_dir / "minutes_model_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    metrics_path = Path(cfg["metrics_path"])
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Saved model -> {path}", flush=True)
    print(f"Saved metrics -> {metrics_path}", flush=True)
    return path


def train_minutes(config_path: str | Path = "config.yaml") -> int:
    cfg_all = load_config(config_path)
    cfg = minutes_config(cfg_all)
    db_path = cfg_all.get("db_path", "data/wnba.db")
    conn = connect(db_path)
    init_schema(conn)

    n_feat = conn.execute("SELECT COUNT(*) AS c FROM player_game_features").fetchone()[
        "c"
    ]
    if n_feat == 0:
        print(
            "no features found — run `python run.py features` (or clean) first",
            flush=True,
        )
        return 1

    print(f"Loading minutes frame from {db_path} ({n_feat} feature rows)...", flush=True)
    df = load_minutes_frame(conn)
    print(
        f"Rows={len(df)} seasons={df['season'].min()}-{df['season'].max()} "
        f"played_rate={(df['played'].mean()):.3f}",
        flush=True,
    )
    train, test = time_split(
        df, int(cfg["train_end_season"]), int(cfg["test_start_season"])
    )
    print(
        f"Time split: train season<={cfg['train_end_season']} n={len(train)}; "
        f"test season>={cfg['test_start_season']} n={len(test)} "
        f"(NO random split)",
        flush=True,
    )
    print(
        f"Share method: {cfg['share_method']} "
        f"(independent predicted shares, renormalize to "
        f"{cfg['regulation_team_minutes']}; Dirichlet concentration="
        f"{cfg['dirichlet_concentration']} for simulation)",
        flush=True,
    )

    model = MinutesModel(cfg)
    print("Fitting DNP classifier + quantile minutes regressors...", flush=True)
    model.fit(train)
    metrics = evaluate_minutes(model, test, cfg)
    save_artifacts(model, cfg, metrics)

    demo_shares = np.array([0.17, 0.16, 0.15, 0.14, 0.12, 0.10, 0.08, 0.08])
    reg_sum = minutes_from_shares(demo_shares, overtime_periods=0).sum()
    ot_sum = minutes_from_shares(
        demo_shares, overtime_periods=1, ot_event=True
    ).sum()
    print(
        f"Sim check: regulation sum={reg_sum:.4f} (expect 200); "
        f"OT event sum={ot_sum:.4f} (expect 225)",
        flush=True,
    )
    _ = sample_dirichlet_minutes(
        demo_shares,
        concentration=float(cfg["dirichlet_concentration"]),
        n_draws=8,
        overtime_periods=0,
    )
    return 0


def load_minutes_model(models_dir: str | Path = "models") -> MinutesModel:
    path = Path(models_dir) / "minutes_model.pkl"
    if not path.exists():
        raise FileNotFoundError(
            f"no trained model found at {path}; run `python run.py train` first"
        )
    with path.open("rb") as f:
        payload = pickle.load(f)
    return payload["model"]
