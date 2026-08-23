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

    for name in ("clean", "train", "project", "evaluate", "audit"):
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
    return _not_implemented(args.command)


if __name__ == "__main__":
    sys.exit(main())
