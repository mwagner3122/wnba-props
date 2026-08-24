#!/bin/bash
# Tier 1 (Mac): double-click to run update then project.
# Place this file inside the repo at scripts/update_and_project.command
# (or keep a copy on your Desktop that cd's into the repo — see docs/automation.md).
# One-time: chmod +x scripts/update_and_project.command
# Then double-click in Finder. A Terminal window stays open with the output.

set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
echo "=== WNBA props: update + project ==="
echo "Repo: $REPO_ROOT"
echo ""

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found on PATH. Install from https://docs.astral.sh/uv/ then retry."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "--- uv run python run.py update ---"
uv run python run.py update
echo ""
echo "--- uv run python run.py check-staleness ---"
uv run python run.py check-staleness
echo ""
echo "--- uv run python run.py project ---"
uv run python run.py project
echo ""
echo "=== Done ==="
read -r -p "Press Enter to close..."
