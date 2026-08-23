"""Hierarchical empirical-Bayes rebounds model: NegativeBinomial (not Poisson)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

ROLES = ("G", "F", "C")


@dataclass
class RatesRebModel:
    cfg: dict[str, Any]
    league_reb_p40: float = 7.0
    role_reb_p40: dict[str, float] = field(default_factory=dict)
    reb_k_role: float = 20.0
    reb_k_league: float = 80.0
    opp_reb_factor: dict[str, float] = field(default_factory=dict)
    opp_sample_size: dict[str, int] = field(default_factory=dict)
    opp_k: float = 25.0
    nb_r: float = 3.0
    fitted: bool = False

    def fit(self, train: pd.DataFrame) -> None:
        played = train[train["minutes"] > 0].copy()
        if played.empty:
            raise ValueError("rates_reb fit: empty training played rows")
        self.reb_k_league = float(self.cfg["reb_k_league"])
        self.reb_k_role = float(self.cfg["reb_k_role"])
        self.opp_k = float(self.cfg["opp_k"])
        tot_reb = float(played["reb"].sum())
        tot_min = float(played["minutes"].sum())
        self.league_reb_p40 = (tot_reb / tot_min) * 40.0 if tot_min > 0 else 7.0
        self.role_reb_p40 = {}
        for role in ROLES:
            sub = played[played["role"] == role]
            if sub.empty:
                self.role_reb_p40[role] = self.league_reb_p40
                continue
            reb, mins = float(sub["reb"].sum()), float(sub["minutes"].sum())
            obs = (reb / mins) * 40.0 if mins > 0 else self.league_reb_p40
            n_exp = mins / 40.0
            w = n_exp / (n_exp + self.reb_k_league)
            self.role_reb_p40[role] = w * obs + (1.0 - w) * self.league_reb_p40
        self.nb_r = _fit_nb_r(
            played["reb"].to_numpy(dtype=float),
            fallback=float(self.cfg["nb_r_fallback"]),
        )
        self._fit_opponent_factors(played)
        self.fitted = True

    def _fit_opponent_factors(self, played: pd.DataFrame) -> None:
        """Team-level rebounds-allowed factor only (n_games stated; no player\u00d7team)."""
        league = self.league_reb_p40
        factors, sizes = {}, {}
        for opp_id, sub in played.groupby("opponent_id", sort=False):
            reb, mins = float(sub["reb"].sum()), float(sub["minutes"].sum())
            n_games = int(sub["game_id"].nunique())
            sizes[str(opp_id)] = n_games
            obs = (reb / mins) * 40.0 if mins > 0 else league
            w = n_games / (n_games + self.opp_k)
            factors[str(opp_id)] = w * (obs / league) + (1.0 - w) * 1.0
        self.opp_reb_factor, self.opp_sample_size = factors, sizes

    def player_posterior(self, role, prior_reb, prior_minutes):
        role = role if role in self.role_reb_p40 else "F"
        mu_r = self.role_reb_p40[role]
        k = self.reb_k_role
        n_exp = float(prior_minutes) / 40.0
        obs = (
            (float(prior_reb) / float(prior_minutes)) * 40.0
            if prior_minutes > 0
            else mu_r
        )
        reb_p40 = (n_exp * obs + k * mu_r) / (n_exp + k)
        # ESS in exposure-units (40-min games); prior weight = k / (n_exp + k)
        ess = n_exp + k
        return {
            "reb_p40": float(reb_p40),
            "ess": float(ess),
            "reb_shrink_weight": float(k / ess if ess > 0 else 1.0),
            "n_exp": float(n_exp),
            "prior_reb": float(prior_reb),
            "role": role,
            "role_reb_p40": float(mu_r),
        }

    def opp_factor(self, opponent_id):
        oid = str(opponent_id)
        return float(self.opp_reb_factor.get(oid, 1.0)), int(self.opp_sample_size.get(oid, 0))

    def predict_params(self, df):
        assert self.fitted
        rows = []
        for r in df.itertuples(index=True):
            post = self.player_posterior(
                getattr(r, "role"),
                float(getattr(r, "prior_reb")),
                float(getattr(r, "prior_minutes")),
            )
            fac, n_opp = self.opp_factor(getattr(r, "opponent_id"))
            rows.append(
                {
                    "_idx": r.Index,
                    "reb_p40": post["reb_p40"],
                    "ess": post["ess"],
                    "reb_shrink_weight": post["reb_shrink_weight"],
                    "n_exp": post["n_exp"],
                    "role_reb_p40": post["role_reb_p40"],
                    "opp_reb_factor": fac,
                    "opp_n_games": float(n_opp),
                }
            )
        return pd.concat([df, pd.DataFrame(rows).set_index("_idx")], axis=1)

    def sample_reb(self, minutes, reb_p40, opp_factor, *, n_sim, rng):
        """Draw NB rebounds via gamma\u2013Poisson mixture (NOT Poisson)."""
        minutes = np.asarray(minutes, dtype=float)
        n = len(minutes)
        mu = np.clip(reb_p40 * (minutes / 40.0) * opp_factor, 0.0, None)
        r = max(float(self.nb_r), 1e-3)
        scale = np.where(mu > 0, mu / r, 0.0)
        lam = rng.gamma(shape=r, scale=scale[:, None], size=(n, n_sim))
        return rng.poisson(lam)


def _fit_nb_r(counts, *, fallback):
    """Method-of-moments NB dispersion; var = mu + mu^2/r \u21d2 r = mu^2/(var-mu)."""
    mu = float(np.mean(counts))
    var = float(np.var(counts, ddof=1)) if len(counts) > 1 else mu
    if mu <= 0 or var <= mu:
        return float(fallback)
    r = (mu * mu) / (var - mu)
    if not np.isfinite(r) or r <= 0.05:
        return float(fallback)
    return float(np.clip(r, 0.1, 500.0))


def shrinkage_summary(params):
    cols = [
        "player_id",
        "role",
        "prior_reb",
        "ess",
        "reb_shrink_weight",
        "reb_p40",
        "n_exp",
    ]
    missing = [c for c in cols if c not in params.columns]
    if missing:
        raise KeyError(f"shrinkage_summary missing columns: {missing}")
    last = (
        params.sort_values(["player_id", "game_date", "game_id"])
        .groupby("player_id", sort=False)
        .tail(1)
    )
    return last[cols].reset_index(drop=True)
