# Phase 10 status

Phase 10 automation is on branch `phase-10-automation`.

- Operator doc: `docs/automation.md` (and `reports/phase10_summary.md`)
- Progress entry: `build/phase10-progress-entry.md` (fold into `PROGRESS.md` on merge)
- Decisions: `build/phase10-decisions-entry.md` (fold into `DECISIONS.md` on merge)
- Config: `config.automation.yaml` fragment — merge under `automation:` in `config.yaml` (code defaults apply if omitted)
- Guide: §14 / §15

## Definition of Done
1. Double-click scripts — **PASS**
2. Actions YAML — **PASS** (enable after merge + set `ODDS_API_KEY` secret)
3. Failure email — **pending-manual** (exact steps in docs/automation.md)
4. Staleness fake-old — **PASS** (`reports/phase10_staleness_dod.txt`)
5. RESTORE.md — **PASS**; Matt restore test — **pending-manual**

**STOP after Phase 10 — do not start later work.**
