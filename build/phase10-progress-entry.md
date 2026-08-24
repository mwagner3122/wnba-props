### Phase 10 - 2026-08-23
**Prerequisite:** Phase 9 beat-b3 PASSED (overall CRPS 1.4857 BEAT b3 1.5082; all four markets BEAT) → full automation (not data-only).
**Built:** Tier 1 double-click scripts (`scripts/update_and_project.command` / `.bat`); Tier 2 GitHub Actions (`.github/workflows/daily.yml` + `weekly.yml`); monitoring (`src/automation.py`: run log, `check-staleness`, `weekly-summary`); weekly `backup`; `RESTORE.md`; manual `today_out.csv` wired into `project` via `src/today_out.py` + `pricing_model_p.build_projection_roster`; docs `docs/automation.md` / `reports/phase10_summary.md`. `.gitignore` exception `!data/wnba.db`. CLI: `check-staleness`, `weekly-summary`, `backup`.
**DoD:**
1. Double-click scripts present + documented — **PASS**
2. Actions YAML valid + schedule/secrets/commit-back documented — **PASS** (schedule not yet live until merge + secret set)
3. Failure notification: exact Matt deliberate-break steps — **PASS** (documented; **pending-manual** for Matt to receive email)
4. Staleness check: fake-old-snapshot test — **PASS** (see `reports/phase10_staleness_dod.txt`)
5. RESTORE.md written; Matt restore test — **PASS** (procedure); restore execution — **pending-manual**
**Operating rhythm:** guide §15 (daily / weekly / monthly).
**Unresolved / stop:** Tier 3 VPS not provisioned (mentioned only). Models remain gitignored — Actions `project` uses continue-on-error so missing models do not block DB commit. Do not start any post-phase-10 work.
