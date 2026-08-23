"""Hierarchical empirical-Bayes 3PM model: Binomial(3PA, p3) with Beta p3."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import numpy as np
import pandas as pd

ROLES = ("G", "F", "C")

@dataclass
class Rates3PMModel:
    cfg: dict[str, Any]
    league_p3: float = 0.34
    league_pa_p40: float = 4.0
    role_p3: dict[str, float] = field(default_factory=dict)
    role_pa_p40: dict[str, float] = field(default_factory=dict)
    kappa_role: float = 40.0
    kappa_league: float = 200.0
    pa_k_role: float = 20.0
    pa_k_league: float = 80.0
    opp_pa_factor: dict[str, float] = field(default_factory=dict)
    opp_sample_size: dict[str, int] = field(default_factory=dict)
    opp_k: float = 25.0
    pa_nb_r: float = 4.0
    fitted: bool = False

    def fit(self, train: pd.DataFrame) -> None:
        played = train[train["minutes"] > 0].copy()
        if played.empty:
            raise ValueError("rates_3pm fit: empty training played rows")
        self.kappa_league = float(self.cfg["p3_kappa_league"])
        self.kappa_role = float(self.cfg["p3_kappa_role"])
        self.pa_k_league = float(self.cfg["pa_k_league"])
        self.pa_k_role = float(self.cfg["pa_k_role"])
        self.opp_k = float(self.cfg["opp_k"])
        tot_m, tot_a = float(played["fg3m"].sum()), float(played["fg3a"].sum())
        self.league_p3 = (tot_m / tot_a) if tot_a > 0 else 0.34
        tot_min = float(played["minutes"].sum())
        self.league_pa_p40 = (tot_a / tot_min) * 40.0 if tot_min > 0 else 4.0
        self.role_p3, self.role_pa_p40 = {}, {}
        for role in ROLES:
            sub = played[played["role"] == role]
            if sub.empty:
                self.role_p3[role] = self.league_p3
                self.role_pa_p40[role] = self.league_pa_p40
                continue
            a, m, mins = float(sub["fg3a"].sum()), float(sub["fg3m"].sum()), float(sub["minutes"].sum())
            obs_p3 = (m / a) if a > 0 else self.league_p3
            w = a / (a + self.kappa_league) if (a + self.kappa_league) > 0 else 0.0
            self.role_p3[role] = w * obs_p3 + (1.0 - w) * self.league_p3
            obs_pa = (a / mins) * 40.0 if mins > 0 else self.league_pa_p40
            n_exp = mins / 40.0
            w_pa = n_exp / (n_exp + self.pa_k_league)
            self.role_pa_p40[role] = w_pa * obs_pa + (1.0 - w_pa) * self.league_pa_p40
        self.pa_nb_r = _fit_nb_r(played["fg3a"].to_numpy(dtype=float), fallback=float(self.cfg["pa_nb_r_fallback"]))
        self._fit_opponent_factors(played)
        self.fitted = True

    def _fit_opponent_factors(self, played: pd.DataFrame) -> None:
        league = self.league_pa_p40
        factors, sizes = {}, {}
        for opp_id, sub in played.groupby("opponent_id", sort=False):
            a, mins = float(sub["fg3a"].sum()), float(sub["minutes"].sum())
            n_games = int(sub["game_id"].nunique())
            sizes[str(opp_id)] = n_games
            obs = (a / mins) * 40.0 if mins > 0 else league
            w = n_games / (n_games + self.opp_k)
            factors[str(opp_id)] = w * (obs / league) + (1.0 - w) * 1.0
        self.opp_pa_factor, self.opp_sample_size = factors, sizes

    def player_posterior(self, role, prior_fg3m, prior_fg3a, prior_minutes):
        role = role if role in self.role_p3 else "F"
        mu_r, kappa = self.role_p3[role], self.kappa_role
        makes, attempts = float(prior_fg3m), float(prior_fg3a)
        misses = max(attempts - makes, 0.0)
        alpha = mu_r * kappa + makes
        beta = (1.0 - mu_r) * kappa + misses
        ess = alpha + beta
        n_exp = float(prior_minutes) / 40.0
        obs_pa = (attempts / float(prior_minutes)) * 40.0 if prior_minutes > 0 else self.role_pa_p40[role]
        k = self.pa_k_role
        return {"alpha": float(alpha), "beta": float(beta), "p3_mean": float(alpha / (alpha + beta)),
                "ess": float(ess), "p3_shrink_weight": float(kappa / ess if ess > 0 else 1.0),
                "pa_p40": float((n_exp * obs_pa + k * self.role_pa_p40[role]) / (n_exp + k)),
                "pa_shrink_weight": float(k / (n_exp + k)), "n_exp": float(n_exp),
                "prior_fg3a": float(attempts), "role": role, "role_p3": float(mu_r),
                "role_pa_p40": float(self.role_pa_p40[role])}

    def opp_factor(self, opponent_id):
        oid = str(opponent_id)
        return float(self.opp_pa_factor.get(oid, 1.0)), int(self.opp_sample_size.get(oid, 0))

    def predict_params(self, df):
        assert self.fitted
        rows = []
        for r in df.itertuples(index=True):
            post = self.player_posterior(getattr(r, "role"), float(getattr(r, "prior_fg3m")),
                                         float(getattr(r, "prior_fg3a")), float(getattr(r, "prior_minutes")))
            fac, n_opp = self.opp_factor(getattr(r, "opponent_id"))
            rows.append({"_idx": r.Index, "p3_alpha": post["alpha"], "p3_beta": post["beta"],
                         "p3_mean": post["p3_mean"], "ess": post["ess"],
                         "p3_shrink_weight": post["p3_shrink_weight"], "pa_p40": post["pa_p40"],
                         "pa_shrink_weight": post["pa_shrink_weight"], "n_exp": post["n_exp"],
                         "role_p3": post["role_p3"], "role_pa_p40": post["role_pa_p40"],
                         "opp_pa_factor": fac, "opp_n_games": float(n_opp)})
        return pd.concat([df, pd.DataFrame(rows).set_index("_idx")], axis=1)

    def sample_3pm(self, minutes, pa_p40, alpha, beta, opp_factor, *, n_sim, rng):
        minutes = np.asarray(minutes, dtype=float)
        n = len(minutes)
        mu_pa = np.clip(pa_p40 * (minutes / 40.0) * opp_factor, 0.0, None)
        r = max(float(self.pa_nb_r), 1e-3)
        scale = np.where(mu_pa > 0, mu_pa / r, 0.0)
        lam = rng.gamma(shape=r, scale=scale[:, None], size=(n, n_sim))
        pa = rng.poisson(lam)
        p = rng.beta(alpha[:, None], beta[:, None], size=(n, n_sim))
        threes = np.zeros((n, n_sim), dtype=np.int64)
        mask = pa > 0
        threes[mask] = rng.binomial(pa[mask], p[mask])
        return threes

def _fit_nb_r(counts, *, fallback):
    mu = float(np.mean(counts))
    var = float(np.var(counts, ddof=1)) if len(counts) > 1 else mu
    if mu <= 0 or var <= mu:
        return float(fallback)
    r = (mu * mu) / (var - mu)
    if not np.isfinite(r) or r <= 0.05:
        return float(fallback)
    return float(np.clip(r, 0.1, 500.0))

def shrinkage_summary(params):
    cols = ["player_id", "role", "prior_fg3a", "ess", "p3_shrink_weight", "pa_shrink_weight", "p3_mean", "pa_p40", "n_exp"]
    missing = [c for c in cols if c not in params.columns]
    if missing:
        raise KeyError(f"shrinkage_summary missing columns: {missing}")
    last = params.sort_values(["player_id", "game_date", "game_id"]).groupby("player_id", sort=False).tail(1)
    return last[cols].reset_index(drop=True)
