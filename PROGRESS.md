# Progress

**Agent: read this first. Build the first phase not marked complete, then stop.**

Mark a phase complete only when its Definition of Done checks pass and the user
has seen the output.

| # | Phase | Spec | Status |
|---|---|---|---|
| 0 | Environment and scaffold | `build/00-setup.md` | ✅ complete |
| 1 | Stats ingestion | `build/01-stats-ingestion.md` | ⬜ not started |
| 2 | Odds ingestion | `build/02-odds-ingestion.md` | ⬜ not started |
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
