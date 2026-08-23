"""Phase 7 simulation tunables (all magic numbers from config.yaml)."""

from __future__ import annotations

from typing import Any


def simulation_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Merge simulation defaults; never invent undocumented metrics."""
    s = dict(cfg.get("simulation") or {})
    minutes_cfg = cfg.get("minutes") or {}
    s.setdefault("n_sim", 10_000)
    s.setdefault("random_seed", 7)
    s.setdefault("dirichlet_concentration", float(minutes_cfg.get("dirichlet_concentration", 40.0)))
    s.setdefault("usage_dirichlet_concentration", 30.0)
    s.setdefault("pace_sd", 3.5)
    s.setdefault("league_pace_anchor", 80.0)
    s.setdefault("regulation_team_minutes", float(cfg.get("regulation_team_minutes", 200.0)))
    s.setdefault("ot_team_minutes", float(cfg.get("ot_team_minutes", 25.0)))
    s.setdefault("ot_prob", 0.0)  # OT only after explicit event unless set > 0 for experiment
    s.setdefault("models_dir", "models")
    s.setdefault("summary_dir", "reports/sim_summaries")
    s.setdefault("overlay_dir", "reports")
    s.setdefault("sanity_path", "reports/sim_sanity.json")
    s.setdefault("prob_table_path", "reports/sim_prob_ge_k.csv")
    s.setdefault("seed_path", "reports/sim_seed.json")
    # Overlay players named in DECISIONS (user-named / documented).
    s.setdefault(
        "overlay_player_ids",
        [
            "3149391",  # A'ja Wilson
            "4433403",  # Caitlin Clark
            "2998928",  # Breanna Stewart
            "3142191",  # Kelsey Mitchell
            "4433730",  # Paige Bueckers
        ],
    )
    s.setdefault(
        "overlay_player_names",
        [
            "A'ja Wilson",
            "Caitlin Clark",
            "Breanna Stewart",
            "Kelsey Mitchell",
            "Paige Bueckers",
        ],
    )
    s.setdefault("overlay_season", int(cfg.get("season", 2026)))
    s.setdefault("overlay_stats", ["pts", "reb", "ast", "fg3m", "pra"])
    # Hierarchical EB for 2P / FT components (phase-7 local; not full phase-6 train).
    s.setdefault("fg2_kappa_league", 200.0)
    s.setdefault("fg2_kappa_role", 40.0)
    s.setdefault("pa2_k_league", 80.0)
    s.setdefault("pa2_k_role", 20.0)
    s.setdefault("ft_kappa_league", 120.0)
    s.setdefault("ft_kappa_role", 30.0)
    s.setdefault("fta_k_league", 80.0)
    s.setdefault("fta_k_role", 20.0)
    s.setdefault("pa2_nb_r_fallback", 5.0)
    s.setdefault("fta_nb_r_fallback", 4.0)
    s.setdefault("train_end_season", int(minutes_cfg.get("train_end_season", 2024)))
    # Team-rebounds realistic band (both teams combined, regulation WNBA).
    s.setdefault("team_reb_low", 28.0)
    s.setdefault("team_reb_high", 55.0)
    s.setdefault("game_total_abs_tol", 18.0)
    s.setdefault("line_k_radius", 5)
    s.setdefault("default_lines", {"pts": 18.5, "reb": 6.5, "ast": 4.5, "fg3m": 1.5, "pra": 28.5})
    return s
