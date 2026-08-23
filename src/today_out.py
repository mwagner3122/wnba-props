"""Manual availability override via today_out.csv (phase 10 / guide §5.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.name_normalize import normalize_name

# Status values that mean "remove from tonight's projection roster".
_OUT_STATUSES = frozenset(
    {
        "out",
        "inactive",
        "dnp",
        "dnp_injury",
        "dnp_rest",
        "dnp_coach",
        "injured",
        "rest",
        "scratch",
        "scratched",
    }
)


def today_out_path(cfg: dict[str, Any] | None = None) -> Path:
    if cfg:
        auto = cfg.get("automation") or {}
        raw = auto.get("today_out_path") or cfg.get("today_out_path")
        if raw:
            return Path(str(raw))
    return Path("today_out.csv")


def load_today_out(path: Path | str | None = None) -> pd.DataFrame:
    """Load today_out.csv if present. Empty frame if missing or blank."""
    p = Path(path) if path is not None else Path("today_out.csv")
    if not p.is_file():
        return pd.DataFrame(columns=["player_id", "player_name", "status", "note"])
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    if df.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "status", "note"])
    cols = {c.lower().strip(): c for c in df.columns}
    out = pd.DataFrame()
    if "player_id" in cols:
        out["player_id"] = df[cols["player_id"]].astype(str).str.strip()
    else:
        out["player_id"] = ""
    if "player_name" in cols:
        out["player_name"] = df[cols["player_name"]].astype(str).str.strip()
    elif "name" in cols:
        out["player_name"] = df[cols["name"]].astype(str).str.strip()
    else:
        out["player_name"] = ""
    if "status" in cols:
        out["status"] = df[cols["status"]].astype(str).str.strip().str.lower()
    else:
        out["status"] = "out"
    if "note" in cols:
        out["note"] = df[cols["note"]].astype(str)
    else:
        out["note"] = ""
    # Drop comment / blank rows
    mask = (out["player_id"].fillna("") != "") | (out["player_name"].fillna("") != "")
    out = out.loc[mask].copy()
    out = out[out["player_id"] != "nan"]
    out = out[out["player_name"] != "nan"]
    return out.reset_index(drop=True)


def out_player_ids(today_out: pd.DataFrame, roster: pd.DataFrame) -> set[str]:
    """Resolve today_out rows to player_id values present on the roster."""
    if today_out is None or today_out.empty or roster is None or roster.empty:
        return set()
    active = today_out[today_out["status"].fillna("out").str.lower().isin(_OUT_STATUSES)]
    if active.empty:
        return set()

    ids: set[str] = set()
    roster_ids = set(roster["player_id"].astype(str))
    for r in active.itertuples(index=False):
        pid = str(getattr(r, "player_id", "") or "").strip()
        if pid.lower() in ("", "nan", "none"):
            pid = ""
        if pid and pid in roster_ids:
            ids.add(pid)
            continue
        name = str(getattr(r, "player_name", "") or "").strip()
        if not name:
            continue
        want = normalize_name(name)
        if "player_name" not in roster.columns:
            continue
        for rr in roster.itertuples(index=False):
            rn = normalize_name(str(getattr(rr, "player_name", "") or ""))
            if rn and rn == want:
                ids.add(str(getattr(rr, "player_id")))
    return ids


def apply_today_out(
    roster: pd.DataFrame,
    today_out: pd.DataFrame | None,
    *,
    verbose: bool = True,
) -> pd.DataFrame:
    """Drop OUT players from a projection roster and renormalize minutes shares."""
    if roster is None or roster.empty:
        return roster
    if today_out is None or today_out.empty:
        if verbose:
            print(
                "today_out.csv: not present or empty — projecting last-played roster "
                "(not true pregame availability)",
                flush=True,
            )
        return roster

    drop_ids = out_player_ids(today_out, roster)
    if not drop_ids:
        if verbose:
            print(
                f"today_out.csv: {len(today_out)} row(s) loaded; none matched this roster",
                flush=True,
            )
        return roster

    before = len(roster)
    kept = roster[~roster["player_id"].astype(str).isin(drop_ids)].copy()
    dropped = roster[roster["player_id"].astype(str).isin(drop_ids)]
    if verbose:
        names = ", ".join(
            f"{r.player_name}({r.player_id})" for r in dropped.itertuples(index=False)
        )
        print(
            f"today_out.csv: removed {before - len(kept)} player(s) as OUT: {names}",
            flush=True,
        )

    if kept.empty:
        return kept

    # Renormalize minutes shares within each team after removals.
    if "expected_minutes_share" in kept.columns and "team_id" in kept.columns:
        for _, sub in kept.groupby("team_id", sort=False):
            idx = sub.index
            raw = kept.loc[idx, "expected_minutes_share"].fillna(0.0).clip(lower=0.01)
            total = float(raw.sum())
            if total > 0:
                kept.loc[idx, "expected_minutes_share"] = raw / total
    return kept.reset_index(drop=True)
