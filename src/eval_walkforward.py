"""Walk-forward fold construction with frozen final holdout."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: int
    train_end: str  # inclusive YYYY-MM-DD
    test_start: str
    test_end: str  # inclusive


@dataclass(frozen=True)
class HoldoutWindow:
    start: str  # inclusive
    end: str  # inclusive (max data date)
    n_days: int


def _as_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def freeze_holdout(max_game_date: str | date, *, holdout_days: int = 21) -> HoldoutWindow:
    """Final ``holdout_days`` calendar days ending at max_game_date are untouched."""
    end = _as_date(max_game_date)
    start = end - timedelta(days=holdout_days - 1)
    return HoldoutWindow(start=start.isoformat(), end=end.isoformat(), n_days=holdout_days)


def build_weekly_folds(
    game_dates: pd.Series | list[str],
    *,
    holdout: HoldoutWindow,
    min_train_days: int = 60,
    week_days: int = 7,
    eval_start: str | date | None = None,
) -> list[WalkForwardFold]:
    """
    Walk-forward only: train through D, predict next week, roll forward.

    Never includes holdout dates in any test window. Never uses a random split.
    If eval_start is set, the first test window begins on/after that date (training
    may still use all earlier history via train_end).
    """
    dates = sorted({_as_date(d) for d in game_dates})
    if not dates:
        return []
    holdout_start = _as_date(holdout.start)
    eval_dates = [d for d in dates if d < holdout_start]
    if len(eval_dates) < 2:
        return []

    first = eval_dates[0]
    last = eval_dates[-1]
    folds: list[WalkForwardFold] = []
    # First train_end must leave min_train_days of history from first game.
    cursor = first + timedelta(days=min_train_days)
    if eval_start is not None:
        es = _as_date(eval_start) - timedelta(days=1)  # train_end day before first test
        if es > cursor:
            cursor = es
    fold_id = 0
    while True:
        test_start = cursor + timedelta(days=1)
        test_end = test_start + timedelta(days=week_days - 1)
        if test_start > last:
            break
        if test_end >= holdout_start:
            test_end = holdout_start - timedelta(days=1)
        if test_end < test_start:
            break
        # Only emit folds that actually have games in the test window.
        if any(test_start <= d <= test_end for d in eval_dates):
            folds.append(
                WalkForwardFold(
                    fold_id=fold_id,
                    train_end=cursor.isoformat(),
                    test_start=test_start.isoformat(),
                    test_end=test_end.isoformat(),
                )
            )
            fold_id += 1
        cursor = test_end
        if cursor >= last:
            break
    return folds


def assert_not_holdout(test_dates: list[str] | pd.Series, holdout: HoldoutWindow) -> None:
    """Raise if any requested evaluation date falls inside the frozen holdout."""
    hs, he = _as_date(holdout.start), _as_date(holdout.end)
    bad = []
    for d in test_dates:
        dd = _as_date(d)
        if hs <= dd <= he:
            bad.append(dd.isoformat())
    if bad:
        raise RuntimeError(
            "REFUSING to evaluate/tune on the frozen final holdout "
            f"[{holdout.start} .. {holdout.end}]. Offending dates (sample): "
            f"{bad[:5]}. Every look that changes something spends the only "
            "unbiased measurement. Do not pass --include-holdout."
        )


def holdout_warning_message(holdout: HoldoutWindow) -> str:
    return (
        f"FROZEN HOLDOUT: {holdout.start} .. {holdout.end} ({holdout.n_days} days). "
        "Do not evaluate on it. Do not tune on it. If you ask to peek, the answer is no -- "
        "looking and changing anything turns it into training data."
    )


def summarize_folds(folds: list[WalkForwardFold], holdout: HoldoutWindow) -> dict[str, Any]:
    return {
        "n_folds": len(folds),
        "first_train_end": folds[0].train_end if folds else None,
        "last_test_end": folds[-1].test_end if folds else None,
        "holdout_start": holdout.start,
        "holdout_end": holdout.end,
        "holdout_days": holdout.n_days,
        "method": "walk_forward_weekly",
        "random_split": False,
    }
