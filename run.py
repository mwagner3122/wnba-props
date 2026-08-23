#!/usr/bin/env python3
"""Single CLI entry point for the WNBA props model."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from src.logging_setup import setup_logging

# Subcommand -> phase that builds real behavior (stubs until then).
_PHASE_FOR = {
    "update": 1,
    "clean": 3,
    "features": 4,
    "train": 5,
    "project": 8,
    "evaluate": 9,
    "audit": 3,
}


def _not_implemented(command: str) -> int:
    phase = _PHASE_FOR[command]
    print(f"not implemented \u2014 phase {phase} builds this")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="WNBA player prop projection model",
    )
    sub = parser.add_subparsers(dest="command")

    update_p = sub.add_parser(
        "update",
        help="Ingest stats (phase 1) then odds (phase 2)",
    )
    update_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Odds path: parse most recent data/raw/odds/*.json (or fixture); no Odds API calls",
    )
    update_p.add_argument(
        "--odds-dry-run",
        action="store_true",
        help="Alias for --dry-run (odds parser only; no Odds API network)",
    )
    update_p.add_argument(
        "--skip-stats",
        action="store_true",
        help="Skip sportsdataverse stats ingest; run odds path only",
    )
    update_p.add_argument(
        "--skip-odds",
        action="store_true",
        help="Skip odds ingest; run stats path only",
    )

    clean_p = sub.add_parser(
        "clean",
        help="Join odds to player_games; write reports/unmatched.md (phase 3)",
    )
    clean_p.add_argument(
        "--approve",
        action="append",
        default=[],
        metavar="RAW=PLAYER_ID",
        help="Persist a name_map approval (repeatable). Fuzzy is never auto-accepted.",
    )
    clean_p.add_argument(
        "--approvals-file",
        default=None,
        help="CSV/lines of raw_name=player_id (or raw_name,player_id) approvals",
    )
    clean_p.add_argument(
        "--skip-features",
        action="store_true",
        help="Skip phase-4 feature rebuild after clean",
    )
    sub.add_parser(
        "features",
        help="Rebuild player_game_features (phase 4; also runs at end of clean)",
    )

    train_p = sub.add_parser(
        "train",
        help="Fit minutes (phase 5) and/or rate models (phase 6: 3pm, reb)",
    )
    train_p.add_argument(
        "--stat",
        choices=("all", "minutes", "3pm", "reb"),
        default="all",
        help="Which model(s) to train (default: all = minutes, 3pm, reb)",
    )
    for name in ("project", "evaluate", "audit"):
        sub.add_parser(name)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "update":
        odds_dry = bool(args.dry_run or args.odds_dry_run)
        rc = 0
        if not args.skip_stats:
            from src.ingest_stats import ingest_update

            rc = ingest_update()
            if rc != 0:
                return rc
        else:
            print("Skipping stats ingest (--skip-stats)", flush=True)
        if not args.skip_odds:
            from src.ingest_odds import ingest_odds

            odds_rc = ingest_odds(dry_run=odds_dry)
            if odds_rc != 0:
                return odds_rc
        else:
            print("Skipping odds ingest (--skip-odds)", flush=True)
        return 0
    if args.command == "clean":
        from src.clean import run_clean

        return run_clean(
            approve=list(args.approve or []),
            approvals_file=args.approvals_file,
            skip_features=bool(getattr(args, "skip_features", False)),
        )
    if args.command == "features":
        from src.features import build_features

        return build_features()
    if args.command == "train":
        from src.model_minutes import train_minutes
        from src.model_rates_3pm import train_rates_3pm
        from src.model_rates_reb import train_rates_reb

        stat = getattr(args, "stat", "all")
        rc = 0
        if stat in ("all", "minutes"):
            rc = train_minutes()
            if rc != 0:
                return rc
        if stat in ("all", "3pm"):
            rc = train_rates_3pm()
            if rc != 0:
                return rc
        if stat in ("all", "reb"):
            rc = train_rates_reb()
            if rc != 0:
                return rc
        return rc
    return _not_implemented(args.command)


if __name__ == "__main__":
    sys.exit(main())
