#!/usr/bin/env python3
"""Single CLI entry point for the WNBA props model."""

from __future__ import annotations

import argparse
import sys

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
    print(f"not implemented — phase {phase} builds this")
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="WNBA player prop projection model",
    )
    sub = parser.add_subparsers(dest="command")

    for name in ("update", "clean", "train", "project", "evaluate", "audit"):
        sub.add_parser(name)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return _not_implemented(args.command)


if __name__ == "__main__":
    sys.exit(main())
