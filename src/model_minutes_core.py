"""Core minutes model class and share renormalization helpers (phase 5)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)

from src.minutes_features import MINUTES_FEATURE_COLUMNS, feature_matrix
from src.minutes_sim import team_minutes_budget

QUANTILES = (0.025, 0.10, 0.25, 0.50, 0.75, 0.90, 0.975)


class MinutesModel:
    """DNP classifier + quantile regressors on minutes | plays."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.feature_columns = list(MINUTES_FEATURE_COLUMNS)
        self.clf: HistGradientBoostingClassifier | None = None
        self.regs: dict[float, HistGradientBoostingRegressor] = {}
        self.residual_scale: float = 4.0
        self.model_residual_quantiles: dict[str, float] = {}
        self.trail5_residual_quantiles: dict[str, float] = {}

    def _hgb_kwargs(self, *, classifier: bool) -> dict[str, Any]:
        return {
            "max_depth": int(self.cfg["max_depth"]),
            "learning_rate": float(self.cfg["learning_rate"]),
            "max_iter": int(
                self.cfg["max_iter_classifier"]
                if classifier
                else self.cfg["max_iter_regressor"]
            ),
            "random_state": int(self.cfg["random_state"]),
        }

    def fit(self, train: pd.DataFrame) -> None:
        X = feature_matrix(train)
        y_dnp = train["dnp"].astype(int).to_numpy()
        self.clf = HistGradientBoostingClassifier(**self._hgb_kwargs(classifier=True))
        self.clf.fit(X, y_dnp)

        played = train[train["played"] == 1].copy()
        Xp = feature_matrix(played)
        yp = played["y_minutes"].clip(lower=0.1, upper=40.0).to_numpy()
        self.regs = {}
        for q in QUANTILES:
            reg = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=float(q),
                **self._hgb_kwargs(classifier=False),
            )
            reg.fit(Xp, yp)
            self.regs[float(q)] = reg

        played["raw_med"] = self.regs[0.50].predict(Xp)
        regulation = float(self.cfg["regulation_team_minutes"])
        ot_m = float(self.cfg["ot_team_minutes"])
        played = apply_team_renorm(
            played, "raw_med", "pred_med", regulation=regulation, ot_per_period=ot_m
        )
        resid = played["y_minutes"].to_numpy() - played["pred_med"].to_numpy()
        self.residual_scale = float(np.std(resid))
        self.model_residual_quantiles = _residual_qs(resid)

        t5 = played["trail5_minutes"].to_numpy()
        mask = np.isfinite(t5)
        t5_resid = played["y_minutes"].to_numpy()[mask] - t5[mask]
        self.trail5_residual_quantiles = _residual_qs(t5_resid)

    def predict_dnp_proba(self, df: pd.DataFrame) -> np.ndarray:
        assert self.clf is not None
        return self.clf.predict_proba(feature_matrix(df))[:, 1]

    def predict_quantile_minutes(self, df: pd.DataFrame, q: float) -> np.ndarray:
        return self.regs[float(q)].predict(feature_matrix(df))

    def predict_raw_median(self, df: pd.DataFrame) -> np.ndarray:
        return self.predict_quantile_minutes(df, 0.50)


def _residual_qs(resid: np.ndarray) -> dict[str, float]:
    return {
        "q025": float(np.quantile(resid, 0.025)),
        "q10": float(np.quantile(resid, 0.10)),
        "q25": float(np.quantile(resid, 0.25)),
        "q75": float(np.quantile(resid, 0.75)),
        "q90": float(np.quantile(resid, 0.90)),
        "q975": float(np.quantile(resid, 0.975)),
    }


def renormalize_played_group(
    g: pd.DataFrame,
    raw_col: str,
    out_col: str,
    *,
    regulation: float = 200.0,
    ot_per_period: float = 25.0,
) -> pd.DataFrame:
    """Scale predicted minutes among played players to team budget."""
    g = g.copy()
    g[out_col] = 0.0
    m = g["played"] == 1
    if not m.any():
        return g
    ot = int(g["overtime_periods"].iloc[0] or 0)
    budget = team_minutes_budget(
        ot, regulation=regulation, ot_per_period=ot_per_period, ot_event=(ot > 0)
    )
    raw = g.loc[m, raw_col].clip(lower=0.1, upper=40.0)
    s = float(raw.sum())
    g.loc[m, out_col] = (raw * (budget / s)).to_numpy() if s > 0 else (budget / m.sum())
    return g


def apply_team_renorm(
    df: pd.DataFrame,
    raw_col: str,
    out_col: str,
    *,
    regulation: float,
    ot_per_period: float,
) -> pd.DataFrame:
    parts = []
    for _, g in df.groupby(["game_id", "team_id"], sort=False):
        parts.append(
            renormalize_played_group(
                g,
                raw_col,
                out_col,
                regulation=regulation,
                ot_per_period=ot_per_period,
            )
        )
    return pd.concat(parts, axis=0).sort_index()


def interval_coverage(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean((y >= lo) & (y <= hi)))


def winkler_score(y: np.ndarray, lo: np.ndarray, hi: np.ndarray, alpha: float) -> float:
    """Mean Winkler interval score (lower is better). alpha = 1 - nominal coverage."""
    y = np.asarray(y, dtype=float)
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    width = hi - lo
    score = width.copy()
    below = y < lo
    above = y > hi
    score[below] = score[below] + (2.0 / alpha) * (lo[below] - y[below])
    score[above] = score[above] + (2.0 / alpha) * (y[above] - hi[above])
    return float(np.mean(score))
