# Automation (Phase 10)

Guide references: **§14** (hosting tiers) and **§15** (daily/weekly/monthly operating rhythm).

Phase 9 beat baseline 3 (overall CRPS 1.4857 vs b3 1.5082; all four markets BEAT), so full automation (update + project) is in scope — not data-only.

## Tier 1 — Double-click scripts

| File | OS |
|---|---|
| `scripts/update_and_project.command` | Mac |
| `scripts/update_and_project.bat` | Windows |

**Where to put them:** keep them in `scripts/` inside this repo (they `cd` to the repo root automatically). Optional: make a Desktop alias/shortcut that points at the script in the repo — do not copy the script away without also updating the `cd` path.

**Mac one-time setup:**
```bash
chmod +x scripts/update_and_project.command
```
Then double-click in Finder. Terminal stays open with the output. Press Enter when finished.

**Windows:** double-click `scripts\update_and_project.bat` in Explorer. The console pauses at the end.

Both run, from repo root:
1. `uv run python run.py update`
2. `uv run python run.py check-staleness`
3. `uv run python run.py project`

## Tier 2 — GitHub Actions

Workflow: `.github/workflows/daily.yml` (plus `.github/workflows/weekly.yml` for backup + summary).

### Secrets

1. Open the repo on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
3. Name: `ODDS_API_KEY` (exact spelling)
4. Value: the same key as in your local `.env`
5. Never put the key in YAML, commits, logs, or PR text

### Schedule (UTC cron → Eastern) + DST

| Cron (UTC) | Approx Eastern (EDT, UTC−4) | Approx Eastern (EST, UTC−5) | Intent |
|---|---|---|---|
| `0 14 * * *` | 10:00 AM | 9:00 AM | Morning / line-open |
| `0 18 * * *` | 2:00 PM | 1:00 PM | Midday |
| `0 22 * * *` | 6:00 PM | 5:00 PM | Pre-tip evening |
| `0 1 * * *` | 9:00 PM | 8:00 PM | Late / near-tip |

WNBA season is mostly EDT. When clocks fall back to EST, each job lands one hour earlier Eastern — still usable for archive capture. Revisit crons if you need exact EST wall times.

**Delay warning:** scheduled Actions are routinely **10–30 minutes late** (sometimes longer). These windows tolerate that. Do **not** schedule a true closing-line grab at tip−5 minutes on Actions.

**60-day inactivity:** GitHub disables schedules on idle repos. Daily commits of `data/wnba.db` count as activity.

**DB in git:** `.gitignore` has `!data/wnba.db` so Actions can commit the DB back. Git **warns past 50 MB** and **hard-limits at 100 MB**. When approaching the limit: keep cleaned tables only, or move to Turso/Supabase (guide §14.3).

### Failure email — Matt’s deliberate-break test

GitHub emails on failed workflow runs to accounts watching the repo (and the user associated with the workflow).

**Exact test steps (do once):**
1. Repo → **Settings** → **Notifications** / ensure your GitHub email is verified; also click **Watch** → **All activity** (or at least Actions failures).
2. **Actions** → **Daily update and project** → **Run workflow** (workflow_dispatch).
3. Deliberate break — pick one:
   - Temporarily rename the secret `ODDS_API_KEY` to `ODDS_API_KEY_BROKEN` (Settings → Secrets), run the workflow, confirm it fails on `update`, then rename it back; **or**
   - Edit `daily.yml` on a test branch to `run: exit 1` as the first step, run once, revert.
4. Confirm you receive the failure email.
5. Restore the secret / YAML.

Until step 4 succeeds, treat notification as **unverified**.

### Models on Actions

`models/*.pkl` stay gitignored. `project` uses `continue-on-error: true` so a missing-model failure does not block the DB commit. To make `project` succeed on Actions: train locally and commit models (or add a train step) — optional.

## Monitoring

| Piece | Command / path |
|---|---|
| Run log | `logs/run_status.jsonl` — timestamp, records fetched, errors, remaining API quota |
| Staleness | `uv run python run.py check-staleness` — FAIL (exit 1) if newest odds snapshot > `automation.stale_hours` (default 36) |
| Weekly summary | `uv run python run.py weekly-summary` → `reports/weekly_automation_summary.md` |

## Backups

```bash
uv run python run.py backup   # -> backups/<UTC-stamp>/wnba.db + raw_odds/*.json
```

See **RESTORE.md**. Matt’s restore test is **pending-manual**.

## Manual availability (`today_out.csv`)

Edit `today_out.csv` before `project` (template + `today_out.csv.example`):

```csv
player_id,player_name,status,note
4433403,,out,Caitlin Clark resting
,Breanna Stewart,dnp_injury,
```

`project` removes matching OUT players from the projection roster and renormalizes minutes shares. Status values: `out`, `inactive`, `dnp`, `dnp_injury`, `dnp_rest`, `dnp_coach`, `injured`, `rest`, `scratch`, `scratched`.

## Tier 3 — VPS (not provisioned)

If Actions’ ±10–30 min jitter bothers you for closing-line work: ~$5/mo VPS + cron/systemd gives precise timing. Not set up in this phase — mention only.

## Operating rhythm (guide §15)

- **Daily:** confirm the run; glance at projections CSV; check slate size.
- **Weekly:** read `reports/unmatched.md`; retrain; check calibration; confirm backup.
- **Monthly:** full walk-forward re-eval vs baselines; review API spend.
