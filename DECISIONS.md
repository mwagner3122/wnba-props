# Decisions

Append-only. One entry per choice that could reasonably have gone another way.
Future-you and future-agent will not remember why, and the guide's defaults are
starting points, not conclusions.

Format:

```
## YYYY-MM-DD — <the choice>
**Decided:** what was chosen
**Alternatives:** what else was considered
**Why:** the reasoning
**Revisit if:** the condition that would change this
```

<!-- Agent: append new decisions below. Do not edit existing entries. -->

## 2026-08-23 — Packaging via hatchling under uv
**Decided:** `pyproject.toml` uses hatchling and packages `src/` with zero runtime dependencies; CLI is stdlib argparse only.
**Alternatives:** setuptools; add click/typer for the CLI.
**Why:** Phase 0 forbids unnecessary packages; argparse is enough for stub subcommands; uv + hatchling is a common minimal layout.
**Revisit if:** a later phase needs a richer CLI framework and the user approves the package.

## 2026-08-23 — Stub phase numbers on subcommands
**Decided:** not-implemented messages map update→1, clean→3, train→5, project→8, evaluate→9, audit→3.
**Alternatives:** a single generic "not implemented" with no phase number.
**Why:** `build/00-setup.md` asks for `not implemented — phase N builds this`; numbers align with when AGENTS.md introduces real behavior for those commands.
**Revisit if:** a later phase owns a different subcommand than this map assumes.

## 2026-08-23 — Stats source: sportsdataverse (Python) parquet loaders
**Decided:** Use the PyPI `sportsdataverse` package (`sportsdataverse.wnba.load_wnba_*`) for player/team box scores, schedule, and play-by-play. Raw loader output is written to `data/raw/stats/*.json` before SQLite parsing. Direct `stats.wnba.com` / `nba_api` not required for phase 1 columns.
**Alternatives:** R `wehoop`; `nba_api` with `league_id='10'`; hand-rolled stats.wnba.com HTTP with browser headers.
**Why:** Phase spec names sportsdataverse; the Python package exposes WNBA box + PBP loaders (verified on PyPI / docs) and returns DNP rows with reasons needed for `availability`.
**Revisit if:** A needed field (lineups, hustle, tracking) is missing from loaders — then call stats.wnba.com with browser-like headers.

## 2026-08-23 — uv add sportsdataverse, pyyaml, python-dotenv
**Decided:** Add `sportsdataverse` (WNBA ingest), `pyyaml` (read `config.yaml`), `python-dotenv` (dotenv support for later odds/env; harmless in phase 1).
**Alternatives:** stdlib-only YAML subset; defer dotenv until phase 2; call ESPN HTTP without sportsdataverse.
**Why:** Required by the phase-1 spec / guide layout; each package maps to a concrete need (fetch, config, secrets loader).
**Revisit if:** sportsdataverse becomes unmaintained or its parquet releases lag live games badly.

## 2026-08-23 — Possession FTA coefficient 0.44
**Decided:** `POSS ≈ FGA − OREB + TOV + 0.44 × FTA` with `fta_possession_factor: 0.44` in `config.yaml`. Pace = possessions per 40 minutes, adjusting minutes for OT (`40 + 5×OT`).
**Alternatives:** Derive the FT possession-ending rate from play-by-play; use a WNBA-specific coefficient from literature.
**Why:** Spec/guide default; PBP is saved raw for a later derivation if needed.
**Revisit if:** Phase that needs precise pace finds systematic bias vs PBP possession endings.

## 2026-08-23 — Exclude All-Star / exhibition abbreviations from DB
**Decided:** Drop games involving `WIL`, `STE`, `WNBASTARS`, `USA`, `COL`, `CLA`, `COOP`, `SPO` during ingest (config `exclude_team_abbreviations`).
**Alternatives:** Keep them in `games` with a flag; ingest then filter at validation only.
**Why:** Avoids polluting franchise schedule counts and expansion-team paths; still documented as excluded rather than silently imputed.
**Revisit if:** A later phase needs All-Star minutes for some feature.

## 2026-08-23 — Season range 2019–2026 and minutes-sum tolerance 3.5
**Decided:** Ingest `start_season: 2019` through `end_season: 2026`. Team-minutes validation allows ±3.5 vs `200 + 25×OT` because ESPN rounded minutes commonly sum to 198–203 with no missing players.
**Alternatives:** Start at 2002 (full wehoop history); require exact 200.0; impute minutes to force the sum.
**Why:** Multi-year history without an enormous first download; tolerance matches observed rounding, not dropped rows (no |error|>3 in sample).
**Revisit if:** A source switch yields exact integer minutes or validation starts missing real parse bugs.

## 2026-08-23 — Odds price format: American
**Decided:** Store `over_price` / `under_price` as American odds (integers such as -115, 100) via Odds API `oddsFormat=american`, configured as `odds.odds_format: american` in `config.yaml`.
**Alternatives:** Decimal odds (API default).
**Why:** US books / prop sheets commonly quote American; matches how closing-line comparisons are discussed later; easy to convert to implied probability when pricing.
**Revisit if:** A downstream phase prefers decimal for EV math and conversion noise matters.

## 2026-08-23 — Odds sport key basketball_wnba + event-odds only for props
**Decided:** Use sport key `basketball_wnba` (verified against the-odds-api.com WNBA docs). Fetch events (quota-free), then player props via `/v4/sports/{sport}/events/{eventId}/odds` one game at a time. Default market `player_points` (config); alternate lines with `_alternate` suffix are kept when present.
**Alternatives:** Main `/odds` endpoint (featured markets only — rejects `player_points`); other sport key spellings.
**Why:** Spec/guide require event-odds for WNBA player props; docs confirm `basketball_wnba`.
**Revisit if:** Odds API renames the sport key or adds a bulk props endpoint.

## 2026-08-23 — update CLI: stats then odds; --dry-run is odds-only network skip
**Decided:** `run.py update` runs phase-1 stats then phase-2 odds. `--dry-run` / `--odds-dry-run` skip Odds API calls and parse the newest `data/raw/odds/*.json`, falling back to `tests/fixtures/odds/event_odds_fixture.json`. Optional `--skip-stats` / `--skip-odds` for focused runs.
**Alternatives:** Separate `update-odds` subcommand; dry-run skipping both stats and odds network.
**Why:** Spec asks for `--dry-run` on the odds path; keeping one `update` entrypoint matches phase-1 wiring and stays idempotent for stats.
**Revisit if:** Users want dry-run to also skip sportsdataverse.
