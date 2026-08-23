"""Sanity checks and overlay plots for phase-7 simulation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.sim_engine import GameSimResult, assert_minutes_budget, simulate_game
from src.sim_summarize import team_score_summary


def check_team_points(
    result: GameSimResult,
    actuals: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    scores = team_score_summary(result)
    posted = actuals.get("posted_total")
    actual_total = actuals.get("actual_total")
    sim_total = scores.get("_game_total", {})
    tol = float(cfg["game_total_abs_tol"])
    mean = float(sim_total.get("mean", float("nan")))
    out: dict[str, Any] = {
        "posted_total": posted,
        "actual_total": actual_total,
        "sim_total_mean": mean,
        "sim_total_p50": sim_total.get("p50"),
        "tol": tol,
        "teams": {k: v for k, v in scores.items() if not k.startswith("_")},
    }
    if posted is not None and np.isfinite(mean):
        out["delta_vs_posted"] = mean - float(posted)
        out["ok_vs_posted"] = bool(abs(mean - float(posted)) <= tol)
    else:
        out["delta_vs_posted"] = None
        out["ok_vs_posted"] = None
        out["note"] = "No posted game total in odds (player_points only); compared to actual total."
    if actual_total is not None and np.isfinite(mean):
        out["delta_vs_actual"] = mean - float(actual_total)
        out["ok_vs_actual"] = bool(abs(mean - float(actual_total)) <= tol)
    else:
        out["delta_vs_actual"] = None
        out["ok_vs_actual"] = None
    if out["ok_vs_posted"] is True:
        out["ok"] = True
    elif out["ok_vs_actual"] is True:
        out["ok"] = True
    elif out["ok_vs_posted"] is False or out["ok_vs_actual"] is False:
        out["ok"] = False
    else:
        out["ok"] = False
        out["note"] = (out.get("note") or "") + " No total reference available."
    return out


def check_team_rebounds(
    result: GameSimResult,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    lo = float(cfg["team_reb_low"])
    hi = float(cfg["team_reb_high"])
    out: dict[str, Any] = {"low": lo, "high": hi, "teams": {}}
    ok = True
    for tid, reb in result.team_reb_sums.items():
        mean = float(reb.mean())
        team_ok = bool(lo <= mean <= hi)
        ok = ok and team_ok
        out["teams"][tid] = {
            "mean": mean,
            "p10": float(np.percentile(reb, 10)),
            "p90": float(np.percentile(reb, 90)),
            "ok": team_ok,
        }
    out["ok"] = ok
    return out


def overlay_player_distributions(
    conn,
    *,
    player_id: str,
    player_name: str,
    season: int,
    result: GameSimResult,
    stats: list[str],
    out_path: Path,
) -> Path:
    """Overlay simulated distribution vs season game-log histogram."""
    i = result.player_ids.index(str(player_id))
    logs = pd.read_sql_query(
        """
        SELECT minutes, points AS pts, reb, ast, fg3m,
               (points + reb + ast) AS pra
        FROM player_games
        WHERE player_id = ? AND game_date >= ? AND minutes > 0
        ORDER BY game_date
        """,
        conn,
        params=(str(player_id), f"{int(season)}-01-01"),
    )
    n_stats = len(stats)
    fig, axes = plt.subplots(1, n_stats, figsize=(3.2 * n_stats, 3.2), squeeze=False)
    for ax, stat in zip(axes[0], stats):
        sim = result.draws[stat][i, :].astype(float)
        ax.hist(
            sim,
            bins=min(40, max(10, int(sim.max() - sim.min() + 1))),
            density=True,
            alpha=0.55,
            color="C0",
            label="sim",
        )
        if not logs.empty and stat in logs.columns:
            ax.hist(
                logs[stat].to_numpy(dtype=float),
                bins=min(20, max(5, int(logs[stat].max() - logs[stat].min() + 1))),
                density=True,
                alpha=0.55,
                color="C1",
                label=f"{season} log n={len(logs)}",
            )
        ax.set_title(stat)
        ax.set_xlabel(stat)
        ax.legend(fontsize=7)
    fig.suptitle(f"{player_name} ({player_id}) — sim vs {season} game log", fontsize=11)
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def build_overlay_roster_row(
    conn,
    player_id: str,
    *,
    model_3pm,
    model_reb,
    model_ast,
    model_fg2ft,
    minutes_model,
    season: int,
) -> pd.DataFrame:
    """Build a one-player synthetic roster anchored on latest as-of rates in season."""
    from src.sim_roster import load_game_roster

    row = conn.execute(
        """
        SELECT game_id FROM player_games
        WHERE player_id = ? AND game_date >= ? AND minutes > 0
        ORDER BY game_date DESC LIMIT 1
        """,
        (str(player_id), f"{int(season)}-01-01"),
    ).fetchone()
    if row is None:
        raise ValueError(f"no {season} games for player {player_id}")
    gid = str(row["game_id"])
    roster = load_game_roster(
        conn,
        gid,
        model_3pm=model_3pm,
        model_reb=model_reb,
        model_ast=model_ast,
        model_fg2ft=model_fg2ft,
        minutes_model=minutes_model,
        played_only=True,
    )
    return roster


def run_ot_minutes_check(cfg: dict[str, Any], rng: np.random.Generator) -> dict[str, Any]:
    """Unit-style check: regulation 200; +25 only after explicit OT event."""
    from src.minutes_sim import sample_dirichlet_minutes

    shares = [0.17, 0.16, 0.15, 0.14, 0.12, 0.10, 0.08, 0.08]
    reg = sample_dirichlet_minutes(
        shares,
        concentration=float(cfg["dirichlet_concentration"]),
        n_draws=200,
        overtime_periods=0,
        ot_event=False,
        rng=rng,
    )
    ot = sample_dirichlet_minutes(
        shares,
        concentration=float(cfg["dirichlet_concentration"]),
        n_draws=200,
        overtime_periods=1,
        ot_event=True,
        rng=rng,
    )
    no_ot = sample_dirichlet_minutes(
        shares,
        concentration=float(cfg["dirichlet_concentration"]),
        n_draws=50,
        overtime_periods=2,
        ot_event=False,
        rng=rng,
    )
    return {
        "regulation_mean_sum": float(reg.sum(axis=1).mean()),
        "regulation_ok": bool(np.allclose(reg.sum(axis=1), 200.0)),
        "ot_mean_sum": float(ot.sum(axis=1).mean()),
        "ot_ok": bool(np.allclose(ot.sum(axis=1), 225.0)),
        "forced_no_ot_mean_sum": float(no_ot.sum(axis=1).mean()),
        "forced_no_ot_ok": bool(np.allclose(no_ot.sum(axis=1), 200.0)),
        "ok": bool(
            np.allclose(reg.sum(axis=1), 200.0)
            and np.allclose(ot.sum(axis=1), 225.0)
            and np.allclose(no_ot.sum(axis=1), 200.0)
        ),
    }


def write_sanity_report(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
