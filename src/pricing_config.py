"""Load Phase-8 pricing tunables from config.yaml."""

from __future__ import annotations

from typing import Any


_DEFAULTS: dict[str, Any] = {
    "default_devig_method": "multiplicative",
    "kelly_fraction": 0.25,
    "min_edge": 0.03,
    "fair_mode": "consensus",  # consensus | sharp_book
    "sharp_book": "draftkings",
    "bankroll": 100.0,
    "slate_csv_path": "reports/slate_priced.csv",
    "hold_csv_path": "reports/pricing_hold.csv",
    "n_sim": None,  # inherit simulation.n_sim when null
    "random_seed": None,
    "exclude_fixture_odds": True,
    "market_stat_map": {
        "player_points": "pts",
        "player_rebounds": "reb",
        "player_assists": "ast",
        "player_threes": "fg3m",
        "player_points_rebounds_assists": "pra",
    },
}


def pricing_config(cfg_all: dict[str, Any]) -> dict[str, Any]:
    raw = dict(cfg_all.get("pricing") or {})
    out = dict(_DEFAULTS)
    out.update(raw)
    if not isinstance(out.get("market_stat_map"), dict):
        out["market_stat_map"] = dict(_DEFAULTS["market_stat_map"])
    else:
        merged = dict(_DEFAULTS["market_stat_map"])
        merged.update(out["market_stat_map"])
        out["market_stat_map"] = merged
    method = str(out["default_devig_method"]).lower().strip()
    if method not in ("multiplicative", "power"):
        raise ValueError(
            "pricing.default_devig_method must be 'multiplicative' or 'power'"
        )
    out["default_devig_method"] = method
    mode = str(out["fair_mode"]).lower().strip()
    if mode not in ("consensus", "sharp_book"):
        raise ValueError("pricing.fair_mode must be 'consensus' or 'sharp_book'")
    out["fair_mode"] = mode
    out["kelly_fraction"] = float(out["kelly_fraction"])
    out["min_edge"] = float(out["min_edge"])
    out["bankroll"] = float(out["bankroll"])
    return out
