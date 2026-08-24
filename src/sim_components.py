"""Lightweight hierarchical EB for 2PM and FTM components (phase-7 simulation).

Points are derived as PTS = 2*2PM + 3*3PM + FTM. 3PM comes from the phase-6
model; 2P and FT are fit here with the same league->role->player EB pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

ROLES = ("G", "F", "C")


def _fit_nb_r(counts: np.ndarray, *, fallback: float) -> float:
    mu = float(np.mean(counts))
    var = float(np.var(counts, ddof=1)) if len(counts) > 1 else mu
    if mu <= 0 or var <= mu:
        return float(fallback)
    r = (mu * mu) / (var - mu)
    if not np.isfinite(r) or r <= 0.05:
        return float(fallback)
    return float(np.clip(r, 0.1, 500.0))


@dataclass
class RatesFg2FtModel:
    """2PA/2PM Beta-Binomial + FTA/FTM Beta-Binomial with NB attempts."""

    cfg: dict[str, Any]
    league_p2: float = 0.45
    league_pa2_p40: float = 8.0
    league_ft: float = 0.80
    league_fta_p40: float = 4.0
    role_p2: dict[str, float] = field(default_factory=dict)
    role_pa2_p40: dict[str, float] = field(default_factory=dict)
    role_ft: dict[str, float] = field(default_factory=dict)
    role_fta_p40: dict[str, float] = field(default_factory=dict)
    pa2_nb_r: float = 5.0
    fta_nb_r: float = 4.0
    fitted: bool = False

    def fit(self, train: pd.DataFrame) -> None:
        played = train[train["minutes"] > 0].copy()
        if played.empty:
            raise ValueError("fg2/ft fit: empty training played rows")
        played = played.copy()
        played["fg2a"] = (played["fga"] - played["fg3a"]).clip(lower=0)
        played["fg2m"] = (played["fgm"] - played["fg3m"]).clip(lower=0)

        tot_m2 = float(played["fg2m"].sum())
        tot_a2 = float(played["fg2a"].sum())
        tot_ftm = float(played["ftm"].sum())
        tot_fta = float(played["fta"].sum())
        tot_min = float(played["minutes"].sum())

        self.league_p2 = (tot_m2 / tot_a2) if tot_a2 > 0 else 0.45
        self.league_pa2_p40 = (tot_a2 / tot_min) * 40.0 if tot_min > 0 else 8.0
        self.league_ft = (tot_ftm / tot_fta) if tot_fta > 0 else 0.80
        self.league_fta_p40 = (tot_fta / tot_min) * 40.0 if tot_min > 0 else 4.0

        k2l = float(self.cfg["fg2_kappa_league"])
        kftl = float(self.cfg["ft_kappa_league"])
        pa2_kl = float(self.cfg["pa2_k_league"])
        fta_kl = float(self.cfg["fta_k_league"])

        self.role_p2, self.role_pa2_p40 = {}, {}
        self.role_ft, self.role_fta_p40 = {}, {}
        for role in ROLES:
            sub = played[played["role"] == role]
            if sub.empty:
                self.role_p2[role] = self.league_p2
                self.role_pa2_p40[role] = self.league_pa2_p40
                self.role_ft[role] = self.league_ft
                self.role_fta_p40[role] = self.league_fta_p40
                continue
            a2, m2 = float(sub["fg2a"].sum()), float(sub["fg2m"].sum())
            fta, ftm = float(sub["fta"].sum()), float(sub["ftm"].sum())
            mins = float(sub["minutes"].sum())
            obs_p2 = (m2 / a2) if a2 > 0 else self.league_p2
            w = a2 / (a2 + k2l) if (a2 + k2l) > 0 else 0.0
            self.role_p2[role] = w * obs_p2 + (1.0 - w) * self.league_p2
            obs_pa2 = (a2 / mins) * 40.0 if mins > 0 else self.league_pa2_p40
            n_exp = mins / 40.0
            w_pa = n_exp / (n_exp + pa2_kl)
            self.role_pa2_p40[role] = w_pa * obs_pa2 + (1.0 - w_pa) * self.league_pa2_p40

            obs_ft = (ftm / fta) if fta > 0 else self.league_ft
            w_ft = fta / (fta + kftl) if (fta + kftl) > 0 else 0.0
            self.role_ft[role] = w_ft * obs_ft + (1.0 - w_ft) * self.league_ft
            obs_fta = (fta / mins) * 40.0 if mins > 0 else self.league_fta_p40
            w_fta = n_exp / (n_exp + fta_kl)
            self.role_fta_p40[role] = w_fta * obs_fta + (1.0 - w_fta) * self.league_fta_p40

        self.pa2_nb_r = _fit_nb_r(
            played["fg2a"].to_numpy(dtype=float),
            fallback=float(self.cfg["pa2_nb_r_fallback"]),
        )
        self.fta_nb_r = _fit_nb_r(
            played["fta"].to_numpy(dtype=float),
            fallback=float(self.cfg["fta_nb_r_fallback"]),
        )
        self.fitted = True

    def player_posterior(
        self,
        role: str,
        prior_fg2m: float,
        prior_fg2a: float,
        prior_ftm: float,
        prior_fta: float,
        prior_minutes: float,
    ) -> dict[str, float]:
        role = role if role in self.role_p2 else "F"
        k2 = float(self.cfg["fg2_kappa_role"])
        kft = float(self.cfg["ft_kappa_role"])
        pa2_k = float(self.cfg["pa2_k_role"])
        fta_k = float(self.cfg["fta_k_role"])

        makes2, att2 = float(prior_fg2m), float(prior_fg2a)
        miss2 = max(att2 - makes2, 0.0)
        a2 = self.role_p2[role] * k2 + makes2
        b2 = (1.0 - self.role_p2[role]) * k2 + miss2

        ftm, fta = float(prior_ftm), float(prior_fta)
        miss_ft = max(fta - ftm, 0.0)
        aft = self.role_ft[role] * kft + ftm
        bft = (1.0 - self.role_ft[role]) * kft + miss_ft

        n_exp = float(prior_minutes) / 40.0
        obs_pa2 = (
            (att2 / float(prior_minutes)) * 40.0
            if prior_minutes > 0
            else self.role_pa2_p40[role]
        )
        obs_fta = (
            (fta / float(prior_minutes)) * 40.0
            if prior_minutes > 0
            else self.role_fta_p40[role]
        )
        return {
            "p2_alpha": float(a2),
            "p2_beta": float(b2),
            "p2_mean": float(a2 / (a2 + b2)),
            "ft_alpha": float(aft),
            "ft_beta": float(bft),
            "ft_mean": float(aft / (aft + bft)),
            "pa2_p40": float(
                (n_exp * obs_pa2 + pa2_k * self.role_pa2_p40[role]) / (n_exp + pa2_k)
            ),
            "fta_p40": float(
                (n_exp * obs_fta + fta_k * self.role_fta_p40[role]) / (n_exp + fta_k)
            ),
            "role": role,
        }

    def sample_2pm(
        self,
        minutes: np.ndarray,
        pa2_p40: np.ndarray,
        alpha: np.ndarray,
        beta: np.ndarray,
        pace_factor: np.ndarray,
        *,
        n_sim: int,
        rng: np.random.Generator,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (fg2m, fg2a) shape (n_players, n_sim)."""
        minutes = np.asarray(minutes, dtype=float)
        n = len(minutes)
        mu = np.clip(pa2_p40 * (minutes / 40.0) * pace_factor, 0.0, None)
        r = max(float(self.pa2_nb_r), 1e-3)
        scale = np.where(mu > 0, mu / r, 0.0)
        lam = rng.gamma(shape=r, scale=scale[:, None], size=(n, n_sim))
        pa = rng.poisson(lam)
        p = rng.beta(alpha[:, None], beta[:, None], size=(n, n_sim))
        makes = np.zeros((n, n_sim), dtype=np.int64)
        mask = pa > 0
        makes[mask] = rng.binomial(pa[mask], p[mask])
        return makes, pa

    def sample_ftm(
        self,
        minutes: np.ndarray,
        fta_p40: np.ndarray,
        alpha: np.ndarray,
        beta: np.ndarray,
        pace_factor: np.ndarray,
        *,
        n_sim: int,
        rng: np.random.Generator,
    ) -> tuple[np.ndarray, np.ndarray]:
        minutes = np.asarray(minutes, dtype=float)
        n = len(minutes)
        mu = np.clip(fta_p40 * (minutes / 40.0) * pace_factor, 0.0, None)
        r = max(float(self.fta_nb_r), 1e-3)
        scale = np.where(mu > 0, mu / r, 0.0)
        lam = rng.gamma(shape=r, scale=scale[:, None], size=(n, n_sim))
        fta = rng.poisson(lam)
        p = rng.beta(alpha[:, None], beta[:, None], size=(n, n_sim))
        makes = np.zeros((n, n_sim), dtype=np.int64)
        mask = fta > 0
        makes[mask] = rng.binomial(fta[mask], p[mask])
        return makes, fta


def load_component_train_frame(conn) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT
            f.game_id, f.player_id, f.game_date, f.season, f.team_id, f.opponent_id,
            f.position,
            pg.minutes AS minutes, pg.fga AS fga, pg.fgm AS fgm,
            pg.fg3a AS fg3a, pg.fg3m AS fg3m, pg.fta AS fta, pg.ftm AS ftm
        FROM player_game_features f
        JOIN player_games pg USING (game_id, player_id)
        ORDER BY f.player_id, f.game_date, f.game_id
        """,
        conn,
    )
    for c in ("minutes", "fga", "fgm", "fg3a", "fg3m", "fta", "ftm"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["position"] = df["position"].fillna("F").astype(str)
    df["role"] = (
        df["position"].str.upper().str[0].map({"G": "G", "F": "F", "C": "C"}).fillna("F")
    )
    return df


def add_asof_fg2_ft_history(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["player_id", "game_date", "game_id"]).copy()
    out["fg2a"] = (out["fga"] - out["fg3a"]).clip(lower=0)
    out["fg2m"] = (out["fgm"] - out["fg3m"]).clip(lower=0)
    g = out.groupby("player_id", sort=False)
    out["prior_fg2m"] = g["fg2m"].cumsum().shift(1).fillna(0.0)
    out["prior_fg2a"] = g["fg2a"].cumsum().shift(1).fillna(0.0)
    out["prior_ftm"] = g["ftm"].cumsum().shift(1).fillna(0.0)
    out["prior_fta"] = g["fta"].cumsum().shift(1).fillna(0.0)
    out["prior_minutes"] = g["minutes"].cumsum().shift(1).fillna(0.0)
    return out
