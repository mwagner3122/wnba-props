## 2026-08-23 -- Phase 10: commit data/wnba.db (gitignore exception)
**Decided:** Keep `*.db` ignored, add explicit `!data/wnba.db` so GitHub Actions can commit the SQLite file back after each scheduled run. Record size limits: Git warns >50 MB, hard-limit 100 MB (guide §14.3).
**Alternatives:** Turso/Supabase now; Actions artifacts only (no git history of odds); VPS disk only.
**Why:** Spec/guide sweet spot for this project size (~31 MB today). Daily DB commits also defeat the 60-day schedule-disable rule.
**Revisit if:** DB approaches 50 MB — then strip raw tables from git or move hosted.

## 2026-08-23 -- Phase 10: Actions cron windows (UTC, delay-tolerant)
**Decided:** Four daily UTC crons — `0 14`, `0 18`, `0 22`, `0 1` — targeting ~10am / 2pm / 6pm / 9pm Eastern under EDT. Document EST shift (−1h Eastern) and ±10–30 min Actions delay. Not for true T−5 closing-line capture.
**Alternatives:** Single daily run; tip-relative dynamic schedule (needs VPS); more than four captures.
**Why:** Matches configured `odds.snapshots_per_day: 4` / capture_cadence; tolerates Actions jitter.
**Revisit if:** Closing-line work requires precise timing → Tier 3 VPS.

## 2026-08-23 -- Phase 10: today_out.csv manual availability
**Decided:** Header-only `today_out.csv` + `today_out.csv.example`; `project` drops OUT statuses and renormalizes minutes shares per team. No injury scraping yet.
**Alternatives:** Scrape injury feeds now; ignore availability until later.
**Why:** Guide §5.5 phase-2 approach — two minutes a day, unblocks honest projection without new deps.
**Revisit if:** Automated injury feed is trustworthy enough to replace the CSV.

## 2026-08-23 -- Phase 10: pytest as dev dependency
**Decided:** Add `pytest` under uv dev deps to run `tests/test_automation.py` (and existing suite).
**Alternatives:** Ad-hoc scripts only; system pytest.
**Why:** Tests already written in pytest style across phases; needed to verify staleness/today_out. Dev-only — not a runtime dependency.
**Revisit if:** Never.
