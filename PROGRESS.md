# Progress

**Agent: read this first. Build the first phase not marked complete, then stop.**

Mark a phase complete only when its Definition of Done checks pass and the user
has seen the output.

| # | Phase | Spec | Status |
|---|---|---|---|
| 0 | Environment and scaffold | `build/00-setup.md` | complete |
| 1 | Stats ingestion | `build/01-stats-ingestion.md` | complete |
| 2 | Odds ingestion | `build/02-odds-ingestion.md` | complete |
| 3 | Cleaning and joining | `build/03-cleaning-joining.md` | complete |
| 4 | Features | `build/04-features.md` | complete |
| 5 | Minutes model | `build/05-minutes-model.md` | complete |
| 6 | Rate models | `build/06-rate-models.md` | in progress (3PM + reb complete; ast/pts not started) |
| 7 | Simulation | `build/07-simulation.md` | not started |
| 8 | Pricing | `build/08-pricing.md` | not started |
| 9 | Evaluation | `build/09-evaluation.md` | not started |
| 10 | Automation | `build/10-automation.md` | not started |

Optional, run before phase 3 if applicable:

| - | Spreadsheet log audit | `build/03b-spreadsheet-audit.md` | skipped (no hand-kept log) |

Something broken? See `build/recovery.md`.

---

## Phase log

Append one entry per completed phase: what was built, what the DoD checks
returned, and anything left unresolved.

<!-- Agent: append below this line. Do not rewrite earlier entries. -->

### Phase 0 - 2026-08-23
**Built:** `pyproject.toml` (uv, Python >=3.11, no runtime deps beyond the project itself), `run.py` CLI stubs for all six subcommands, `config.yaml` with `season: 2026`, `src/logging_setup.py` shared logger (console + `logs/wnba-props.log`), package marker `src/__init__.py`, keepdirs for `logs/`, `reports/`, `tests/`, `data/`. Confirmed existing `.gitignore` and `.env.example`.
**DoD:**
- `uv run python run.py --help` lists update/clean/train/project/evaluate/audit - pass
- `uv run python run.py update` prints `not implemented - phase 1 builds this` and exits 0 - pass
- `uv run python run.py` (no args) prints help, exits 0 - pass
- `uv sync` from clean checkout - pass
**Unresolved:** none for phase 0. User should install `uv` if needed, copy `.env.example` -> `.env`, and review before phase 1.

### Phase 1 - 2026-08-23
**Built:** `src/db.py` (SQLite schema for teams/players/games/player_games/availability/ingest_meta), `src/ingest_stats.py` (sportsdataverse fetch -> `data/raw/stats/*.json` -> parse/upsert, possession/pace, availability including DNPs, validation), wired `run.py update`, expanded `config.yaml` seasons/tunables. Dependencies: sportsdataverse, pyyaml, python-dotenv.
**DoD:**
- `uv run python run.py update` twice; second prints `0 new games` - pass
- Validation: points/rebounds/duplicates/season window/player FK/team minutes - pass; schedule games-per-team - fail with explained rows (2026 mid-season incomplete; some teams expected+1 from Cup/extras in season_type=2) - pass (explained)
- Summary printed (seasons 2019-2026, 1930 games, 44114 player-games, 2019-05-24->2026-08-22, checks 6/7) - pass
- `availability` rows with `minutes_played=0`: 7494 - pass
- Toronto Tempo / Portland Fire present without crash - pass
**Unresolved:** 2026 regular season still in progress (ingest through 2026-08-22). Schedule-length check will keep failing until the season completes; re-run `update` as games finish. FTA 0.44 still NBA-derived.

### Phase 2 - 2026-08-23
**Built:** `src/ingest_odds.py` (The Odds API events + event-odds for `basketball_wnba`, raw -> `data/raw/odds/<ISO8601>.json`, parse -> `odds_snapshots`), schema in `src/db.py`, odds tunables + cadence + quota projection in `config.yaml`, CLI `run.py update` runs stats then odds with `--dry-run` / `--odds-dry-run` (no Odds API network; uses latest raw or committed fixture), `--skip-stats` / `--skip-odds`. Fixture: `tests/fixtures/odds/event_odds_fixture.json` (clearly marked `_fixture`). Unit tests: `tests/test_odds_ingest.py` (parse, dry-run insert, simulated mid-run network failure exits 1 cleanly). `python-dotenv` loads `ODDS_API_KEY` from `.env` (gitignored); key never logged.
**CLI:** `uv run python run.py update` -> stats then live odds; `uv run python run.py update --dry-run` (or `--odds-dry-run`) -> stats then odds from raw/fixture; `uv run python run.py update --skip-stats --odds-dry-run` -> odds dry-run only.
**DoD:**
- Snapshot in `odds_snapshots` with real UTC timestamp - **PASS (live)** `captured_at_utc=2026-08-23T15:19:13Z`, inserted=261, games=6, books=5, market=player_points, players=54 (then dry-run re-parse also PASS; table_total grew append-only)
- `--dry-run` re-parses without network - pass
- Remaining quota + projected monthly usage printed - pass (live quota from API headers; dry-run prints N/A; projection 4x7x1x30 = 840 credits/month)
- Network failure mid-run logs error and exits cleanly - pass (`tests/test_odds_ingest.py::test_network_failure_mid_run_exits_cleanly`)
**Unresolved:** Scheduling of capture cadence is phase 10. Keep collecting snapshots; historical coverage still depends on plan/markets/books.

### Phase 3 - 2026-08-23
**Built:** `src/clean.py` (idempotent join pipeline), `src/name_normalize.py`, schema additions in `src/db.py` (`name_map`, `odds_events`, `prop_results`, `games.game_date_et` migration), `run.py clean` with `--approve` / `--approvals-file`, `reports/unmatched.md` writer, tests in `tests/test_clean.py`.
**CLI:** `uv run python run.py clean` rebuilds clean tables from DB + `data/raw/odds`; approvals optional.
**DoD:**
- `reports/unmatched.md` exists with loss analysis (by book/month/team, top unmatched names, fuzzy section) - pass
- Before/after row counts at every step with drop reasons - pass
- Voided props flagged (`is_voided` + `void_reason`); `actual_points` nulled (unit-tested); not deleted - pass
- Nothing dropped silently - all odds rows in `prop_results` with `reason_code` - pass
**Live clean (2026-08-23):** 795 odds rows -> 795 `prop_results`; name-map rate 100%; odds<->player_game match rate 0% because captured lines are for 2026-08-23/08-24 ET tips while stats ingest ends 2026-08-22 (`reason_code=no_player_game`). Re-run `clean` after those games land in `player_games`.
**Unresolved:** Fuzzy approvals pending whenever a raw name fails exact/team+date (none on this slate). Phase 3b spreadsheet audit skipped (no hand-kept log). Do not start phase 4 until user reviews the unmatched report.

### Phase 4 - 2026-08-23
**Built:** `src/feature_columns.py`, `src/feature_asof*.py`, `src/feature_build*.py`, `src/feature_compute.py` (as-of form/role/team/opp/situational/teammate with shrinkage), `src/features.py` (build/store/summary), schema via `features_ddl()` in `init_schema`, tunables under `config.yaml` `features:`, CLI `run.py features` and post-`clean` rebuild (`--skip-features` to opt out). Tests: `tests/test_features.py` (shrink formula, 50-row as-of leakage, TOR/POR expansion). Direct deps: pandas, numpy.
**CLI:** `uv run python run.py features` (or `uv run python run.py clean` which rebuilds features after join).
**DoD:**
- As-of leakage test samples 50 player-games, rebuilds from `game_ord <= target` snapshot, asserts feature equality -- **PASS** (`tests.test_features.TestFeaturesLeakage`)
- Feature summary printed (name, cov%, mean, sd, min, max, nulls) -- **PASS**
- Flag >20% nulls or zero variance -- **PASS** (none flagged on full history build)
- Expansion TOR/POR pipeline runs without error/null crash -- **PASS** (889 rows; 0 all-null)
**Shrinkage weights (prior share k/(n+k)):** player_form mean=0.446 (p50=0.364); team mean=0.457; opponent mean=0.563.
**Unresolved:** Rim/mid shot zones deferred (box score only). `teammate_hist_k` reserved for historical-with-X-out rates not yet emitted as separate columns (vacated minutes / BH-out are live). Tune k on time-based validation in phase 9. Do not start phase 5 until user reviews the feature summary.

### Phase 5 - 2026-08-23
**Built:** Two-stage minutes model -- `src/minutes_features.py`, `src/model_minutes.py` / `src/model_minutes_core.py` / `src/model_minutes_eval.py` (DNP classifier + quantile minutes; share renormalize to 200), `src/minutes_sim.py` (Dirichlet/independent-normalize; OT +25 only after explicit OT event), artifacts under `models/`, calibration under `reports/`. Wired `python run.py train`. Tests: `tests/test_minutes.py`. Direct deps: scikit-learn, scipy, matplotlib.
**Share method:** independent predicted shares renormalized to team budget; Dirichlet (`concentration=40`) for simulation. Recorded in DECISIONS.
**CLI:** `uv run python run.py train`
**DoD:**
- MAE of median (played, known availability): **4.458** vs trailing-5 **4.960** vs last-game **5.899** -- pass
- Coverage 50/80/95% (quantile intervals): **0.517 / 0.811 / 0.953** -- pass
- Residual-band vs trailing-5 (Winkler): model **21.34** < trail5 **24.41** -- pass
- DNP log loss **0.2777**; calibration plot `reports/dnp_calibration.png` + CSV -- pass
- Sim test: regulation sums to 200; +25 only after explicit OT -- pass
- Side-by-side baselines printed -- pass
- **PASS vs trailing-5 on BOTH MAE and coverage** -- phase 5 complete; stop for user gate (do NOT start phase 6)
**Explicit:** BACKTEST KNOWS WHO PLAYED.
**Unresolved:** No historical closing spreads -- blowout proxy `favoritism = team_off_rtg_shrunk - opp_def_rtg_shrunk`. Starters via `start_rate_l10`. True pregame availability is phase 10.

### Phase 6 (3PM only) - 2026-08-23
**Built:** Hierarchical empirical-Bayes 3PM rate model -- `src/rates_3pm_data.py`, `src/rates_3pm_model.py`, `src/rates_3pm_eval.py`, `src/model_rates_3pm.py`. Distribution `3PM ~ Binomial(3PA, p3)` with NB overdispersed attempts (per-40 x minutes) and Beta `p3` shrunk league -> role (G/F/C) -> player. Opponent = team-level 3PA-allowed factor only (sample sizes stated). Wired `python run.py train --stat 3pm|minutes|all`. Artifacts: `models/rates_3pm_model.pkl` (+ meta), `reports/rates_3pm_metrics.json`, `reports/rates_3pm_pit.png`, `reports/rates_3pm_shrinkage.csv`. Tests: `tests/test_rates_3pm.py`. **Not built:** rebounds, assists, points, PRA/combos, phase 7.
**Variance-to-mean (played):** 3PM 1.77; 3PA 2.62; 3PA_p40 4.29 -- documents NB attempts + Binomial/Beta (not Poisson 3PM).
**Holdout (train <=2024 / test >=2025; conditioned on realized minutes):**
- CRPS model **0.4678** vs season-to-date **0.4698** vs trailing-10 **0.4708** (beats both on CRPS)
- PIT: **sloped** (corr~=0.69) -- systematic under-projection of 3PM on 2025-2026 holdout
- Shrinkage: p3 prior weight mean=0.494 p50=0.435; ESS mean=238.8 p50=92; kappa_role=40
- Opp factors: 12 train-era teams; n_games min/median/max = 206/222/250 (no playerxteam)
**Status:** Phase 6 **in progress**. 3PM DoD printed (historical gate). Rebounds follow in next entry.
**Unresolved (3PM):** PIT slope (era drift vs train priors likely); MAE of predictive mean slightly worse than baselines while CRPS is better (calibration/sharpness tradeoff); expansion TOR/POR have no train-era opp factor (default 1.0); minutes uncertainty not folded in until phase 7.

### Phase 6 (rebounds only) - 2026-08-23
**Built:** Hierarchical empirical-Bayes rebounds rate model -- `src/rates_reb_data.py`, `src/rates_reb_model.py`, `src/rates_reb_eval.py`, `src/model_rates_reb.py`. Distribution `REB ~ NegativeBinomial(mu = reb_p40 x minutes/40 x opp_factor, r)` (gamma-Poisson; **NOT Poisson**). Hierarchy league -> role (G/F/C) -> player. Opponent = team-level reb-allowed factor only (sample sizes stated). Wired `python run.py train --stat reb` (3PM path unchanged). Artifacts: `models/rates_reb_model.pkl` (+ meta), `reports/rates_reb_metrics.json`, `reports/rates_reb_pit.png`, `reports/rates_reb_shrinkage.csv`. Tests: `tests/test_rates_reb.py`. **Not built:** assists, points, PRA/combos, phase 7.
**Variance-to-mean (played):** reb **2.877**; oreb 1.739; dreb 2.376; reb_p40 4.795 -- clear overdispersion; NB justified (near-1 would have triggered reconsider).
**Holdout (train <=2024 / test >=2025; conditioned on realized minutes):**
- CRPS model **1.1345** vs season-to-date **1.1540** vs trailing-10 **1.1527** (beats both)
- PIT: **peaked** -- distributions too wide (underconfident; MOM `r~=1.94` may overspread relative to holdout)
- Shrinkage: reb prior weight mean=0.544 p50=0.532; ESS mean=64.2 p50=37.6; `reb_k_role=20`
- Opp factors: 12 train-era teams; n_games min/median/max = 206/222/250 (no playerxteam)
- League reb_p40=6.85; role G/F/C ~= 4.58 / 8.89 / 10.45; NB_r=1.937
**Status:** Phase 6 **in progress**. 3PM done, reb done. Stop -- do **not** start assists/points or phase 7.
**Unresolved:** PIT peaked (consider larger `r` / less overdispersion, or minutes uncertainty in phase 7); expansion TOR/POR default opp factor 1.0; OREB/DREB not split (total reb only); ast/pts not started.
