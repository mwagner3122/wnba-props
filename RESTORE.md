# Restore from backup

Exact rebuild steps if `data/wnba.db` or the odds archive is lost or corrupted.

## What a weekly backup contains

Running `uv run python run.py backup` writes `backups/<UTC-stamp>/` with:

| Path | Contents |
|---|---|
| `wnba.db` | Full SQLite database (stats + odds_snapshots + clean tables) |
| `raw_odds/*.json` | Untouched Odds API responses (re-parseable) |
| `MANIFEST.json` | Stamp + source paths |

GitHub Actions also uploads that folder as a workflow artifact (`wnba-props-backup`, 30-day retention) via `.github/workflows/weekly.yml`. **Artifacts expire.** Copy backups off the runner (USB, another laptop, cloud drive) regularly — an unverified backup that only lives on Actions is a hope.

## Rebuild steps (exact)

1. **Stop writers.** Do not run `update` / Actions while restoring.
2. **Pick a backup folder**, e.g. `backups/20260823T120000Z/` (or an extracted Actions artifact).
3. **Restore the database:**
   ```bash
   cd /path/to/wnba-props
   mkdir -p data
   cp backups/<stamp>/wnba.db data/wnba.db
   ```
4. **Restore raw odds JSON (recommended):**
   ```bash
   mkdir -p data/raw/odds
   cp backups/<stamp>/raw_odds/*.json data/raw/odds/
   ```
5. **Re-install deps if needed:** `uv sync`
6. **Sanity checks:**
   ```bash
   uv run python run.py check-staleness
   uv run python run.py audit
   # optional: rebuild clean joins from restored odds
   uv run python run.py clean
   ```
7. **If only raw JSON survived (no DB):** re-ingest stats, then re-parse odds:
   ```bash
   uv run python run.py update --skip-odds          # rebuild stats tables
   uv run python run.py update --skip-stats --dry-run  # re-parse raw odds into odds_snapshots
   uv run python run.py clean
   ```
   Note: dry-run parses the *latest* raw file only. For a full archive rebuild from many JSON files, re-parse each file with a small loop or ask the agent — do not assume one dry-run restores every historical snapshot.
8. **Models:** `models/*.pkl` are not in the weekly DB backup (gitignored). Re-train if missing:
   ```bash
   uv run python run.py train
   ```

## Matt's one-time restore test (Definition of Done)

**Status: pending-manual** — you must run this once yourself.

1. Run `uv run python run.py backup` and note the new `backups/<stamp>/` folder.
2. Copy that folder somewhere safe (Desktop / cloud).
3. Move the live DB aside: `mv data/wnba.db data/wnba.db.before_restore_test`
4. Restore: `cp backups/<stamp>/wnba.db data/wnba.db`
5. Confirm: `uv run python run.py check-staleness` (and glance at a known table / slate).
6. Put the original back if the test was destructive: `mv data/wnba.db.before_restore_test data/wnba.db`
7. Check the box: restore tested — yes / date ______

Until step 7 is done, treat backups as **unverified**.
