# Progress

**Agent: read this first. Build the first phase not marked complete, then stop.**

Mark a phase complete only when its Definition of Done checks pass and the user
has seen the output.

| # | Phase | Spec | Status |
|---|---|---|---|
| 0 | Environment and scaffold | `build/00-setup.md` | ✅ complete |
| 1 | Stats ingestion | `build/01-stats-ingestion.md` | ✅ complete |
| 2 | Odds ingestion | `build/02-odds-ingestion.md` | ✅ complete |
| 3 | Cleaning and joining | `build/03-cleaning-joining.md` | ⬜ not started |
| 4 | Features | `build/04-features.md` | ⬜ not started |
| 5 | Minutes model | `build/05-minutes-model.md` | ⬜ not started |
| 6 | Rate models | `build/06-rate-models.md` | ⬜ not started |
| 7 | Simulation | `build/07-simulation.md` | ⬜ not started |
| 8 | Pricing | `build/08-pricing.md` | ⬜ not started |
| 9 | Evaluation | `build/09-evaluation.md` | ⬜ not started |
| 10 | Automation | `build/10-automation.md` | ⬜ not started |

Optional, run before phase 3 if applicable:

| — | Spreadsheet log audit | `build/03b-spreadsheet-audit.md` | ⬜ only if the user has a hand-kept prop log |

Something broken? See `build/recovery.md`.

---

## Phase log

Append one entry per completed phase: what was built, what the DoD checks
returned, and anything left unresolved.

<!-- Agent: append below this line. Do not rewrite earlier entries. -->

### Phase 0 — 2026-08-23
**Built:** `pyproject.toml` (uv, Python >=3.11, no runtime deps beyond the project itself), `run.py` CLI stubs for all six subcommands, `config.yaml` with `season: 2026`, `src/logging_setup.py` shared logger (console + `logs/wnba-props.log`), package marker `src/__init__.py`, keepdirs for `logs/`, `reports/`, `tests/`, `data/`. Confirmed existing `.gitignore` and `.env.example`.
**DoD:**
- `uv run python run.py --help` lists update/clean/train/project/evaluate/audit — pass
- `uv run python run.py update` prints `not implemented — phase 1 builds this` and exits 0 — pass
- `uv run python run.py` (no args) prints help, exits 0 — pass
- `uv sync` from clean checkout — pass
**Unresolved:** none for phase 0. User should install `uv` if needed, copy `.env.example` → `.env`, and review before phase 1.

### Phase 1 — 2026-08-23
**Built:** `src/db.py` (SQLite schema for teams/players/games/player_games/availability/ingest_meta), `src/ingest_stats.py` (sportsdataverse fetch → `data/raw/stats/*.json` → parse/upsert, possession/pace, availability including DNPs, validation), wired `run.py update`, expanded `config.yaml` seasons/tunables. Dependencies: sportsdataverse, pyyaml, python-dotenv.
**DoD:**
- `uv run python run.py update` twice; second prints `0 new games` — pass
- Validation: points/rebounds/duplicates/season window/player FK/team minutes — pass; schedule games-per-team — fail with explained rows (2026 mid-season incomplete; some teams expected+1 from Cup/extras in season_type=2) — pass (explained)
- Summary printed (seasons 2019–2026, 1930 games, 44114 player-games, 2019-05-24→2026-08-22, checks 6/7) — pass
- `availability` rows with `minutes_played=0`: 7494 — pass
- Toronto Tempo / Portland Fire present without crash — pass
**Unresolved:** 2026 regular season still in progress (ingest through 2026-08-22). Schedule-length check will keep failing until the season completes; re-run `update` as games finish. FTA 0.44 still NBA-derived.

### Phase 2 — 2026-08-23
**Built:** `src/ingest_odds.py` (The Odds API events + event-odds for `basketball_wnba`, raw → `data/raw/odds/<ISO8601>.json`, parse → `odds_snapshots`), schema in `src/db.py`, odds tunables + cadence + quota projection in `config.yaml`, CLI `run.py update` runs stats then odds with `--dry-run` / `--odds-dry-run` (no Odds API network; uses latest raw or committed fixture), `--skip-stats` / `--skip-odds`. Fixture: `tests/fixtures/odds/event_odds_fixture.json` (clearly marked `_fixture`). Unit tests: `tests/test_odds_ingest.py` (parse, dry-run insert, simulated mid-run network failure exits 1 cleanly). `python-dotenv` loads `ODDS_API_KEY` from `.env` (gitignored); key never logged.
**CLI:** `uv run python run.py update` → stats then live odds; `uv run python run.py update --dry-run` (or `--odds-dry-run`) → stats then odds from raw/fixture; `uv run python run.py update --skip-stats --odds-dry-run` → odds dry-run only.
**DoD:**
- Snapshot in `odds_snapshots` with real UTC timestamp — **PASS (live)** `captured_at_utc=2026-08-23T15:19:13Z`, inserted=261, games=6, books=5, market=player_points, players=54 (then dry-run re-parse also PASS; table_total grew append-only)
- `--dry-run` re-parses without network — pass
- Remaining quota + projected monthly usage printed — pass (live quota from API headers; dry-run prints N/A; projection 4×7×1×30 = 840 credits/month)
- Network failure mid-run logs error and exits cleanly — pass (`tests/test_odds_ingest.py::test_network_failure_mid_run_exits_cleanly`)
**Unresolved:** Scheduling of capture cadence is phase 10. Keep collecting snapshots; historical coverage still depends on plan/markets/books.
