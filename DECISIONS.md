# Decisions

Append-only. One entry per choice that could reasonably have gone another way.
Future-you and future-agent will not remember why, and the guide's defaults are
starting points, not conclusions.

Format:

```
## YYYY-MM-DD -- <the choice>
**Decided:** what was chosen
**Alternatives:** what else was considered
**Why:** the reasoning
**Revisit if:** the condition that would change this
```

<!-- Agent: append new decisions below. Do not edit existing entries. -->

## 2026-08-23 -- Packaging via hatchling under uv
**Decided:** `pyproject.toml` uses hatchling and packages `src/` with zero runtime dependencies; CLI is stdlib argparse only.
**Alternatives:** setuptools; add click/typer for the CLI.
**Why:** Phase 0 forbids unnecessary packages; argparse is enough for stub subcommands; uv + hatchling is a common minimal layout.
**Revisit if:** a later phase needs a richer CLI framework and the user approves the package.

## 2026-08-23 -- Stub phase numbers on subcommands
**Decided:** not-implemented messages map update->1, clean->3, train->5, project->8, evaluate->9, audit->3.
**Alternatives:** a single generic "not implemented" with no phase number.
**Why:** `build/00-setup.md` asks for `not implemented -- phase N builds this`; numbers align with when AGENTS.md introduces real behavior for those commands.
**Revisit if:** a later phase owns a different subcommand than this map assumes.

## 2026-08-23 -- Stats source: sportsdataverse (Python) parquet loaders
**Decided:** Use the PyPI `sportsdataverse` package (`sportsdataverse.wnba.load_wnba_*`) for player/team box scores, schedule, and play-by-play. Raw loader output is written to `data/raw/stats/*.json` before SQLite parsing. Direct `stats.wnba.com` / `nba_api` not required for phase 1 columns.
**Alternatives:** R `wehoop`; `nba_api` with `league_id='10'`; hand-rolled stats.wnba.com HTTP with browser headers.
**Why:** Phase spec names sportsdataverse; the Python package exposes WNBA box + PBP loaders (verified on PyPI / docs) and returns DNP rows with reasons needed for `availability`.
**Revisit if:** A needed field (lineups, hustle, tracking) is missing from loaders -- then call stats.wnba.com with browser-like headers.

## 2026-08-23 -- uv add sportsdataverse, pyyaml, python-dotenv
**Decided:** Add `sportsdataverse` (WNBA ingest), `pyyaml` (read `config.yaml`), `python-dotenv` (dotenv support for later odds/env; harmless in phase 1).
**Alternatives:** stdlib-only YAML subset; defer dotenv until phase 2; call ESPN HTTP without sportsdataverse.
**Why:** Required by the phase-1 spec / guide layout; each package maps to a concrete need (fetch, config, secrets loader).
**Revisit if:** sportsdataverse becomes unmaintained or its parquet releases lag live games badly.

## 2026-08-23 -- Possession FTA coefficient 0.44
**Decided:** `POSS ~= FGA - OREB + TOV + 0.44 x FTA` with `fta_possession_factor: 0.44` in `config.yaml`. Pace = possessions per 40 minutes, adjusting minutes for OT (`40 + 5xOT`).
**Alternatives:** Derive the FT possession-ending rate from play-by-play; use a WNBA-specific coefficient from literature.
**Why:** Spec/guide default; PBP is saved raw for a later derivation if needed.
**Revisit if:** Phase that needs precise pace finds systematic bias vs PBP possession endings.

## 2026-08-23 -- Exclude All-Star / exhibition abbreviations from DB
**Decided:** Drop games involving `WIL`, `STE`, `WNBASTARS`, `USA`, `COL`, `CLA`, `COOP`, `SPO` during ingest (config `exclude_team_abbreviations`).
**Alternatives:** Keep them in `games` with a flag; ingest then filter at validation only.
**Why:** Avoids polluting franchise schedule counts and expansion-team paths; still documented as excluded rather than silently imputed.
**Revisit if:** A later phase needs All-Star minutes for some feature.

## 2026-08-23 -- Season range 2019-2026 and minutes-sum tolerance 3.5
**Decided:** Ingest `start_season: 2019` through `end_season: 2026`. Team-minutes validation allows +/-3.5 vs `200 + 25xOT` because ESPN rounded minutes commonly sum to 198-203 with no missing players.
**Alternatives:** Start at 2002 (full wehoop history); require exact 200.0; impute minutes to force the sum.
**Why:** Multi-year history without an enormous first download; tolerance matches observed rounding, not dropped rows (no |error|>3 in sample).
**Revisit if:** A source switch yields exact integer minutes or validation starts missing real parse bugs.

## 2026-08-23 -- Odds price format: American
**Decided:** Store `over_price` / `under_price` as American odds (integers such as -115, 100) via Odds API `oddsFormat=american`, configured as `odds.odds_format: american` in `config.yaml`.
**Alternatives:** Decimal odds (API default).
**Why:** US books / prop sheets commonly quote American; matches how closing-line comparisons are discussed later; easy to convert to implied probability when pricing.
**Revisit if:** A downstream phase prefers decimal for EV math and conversion noise matters.

## 2026-08-23 -- Odds sport key basketball_wnba + event-odds only for props
**Decided:** Use sport key `basketball_wnba` (verified against the-odds-api.com WNBA docs). Fetch events (quota-free), then player props via `/v4/sports/{sport}/events/{eventId}/odds` one game at a time. Default market `player_points` (config); alternate lines with `_alternate` suffix are kept when present.
**Alternatives:** Main `/odds` endpoint (featured markets only -- rejects `player_points`); other sport key spellings.
**Why:** Spec/guide require event-odds for WNBA player props; docs confirm `basketball_wnba`.
**Revisit if:** Odds API renames the sport key or adds a bulk props endpoint.

## 2026-08-23 -- update CLI: stats then odds; --dry-run is odds-only network skip
**Decided:** `run.py update` runs phase-1 stats then phase-2 odds. `--dry-run` / `--odds-dry-run` skip Odds API calls and parse the newest `data/raw/odds/*.json`, falling back to `tests/fixtures/odds/event_odds_fixture.json`. Optional `--skip-stats` / `--skip-odds` for focused runs.
**Alternatives:** Separate `update-odds` subcommand; dry-run skipping both stats and odds network.
**Why:** Spec asks for `--dry-run` on the odds path; keeping one `update` entrypoint matches phase-1 wiring and stays idempotent for stats.
**Revisit if:** Users want dry-run to also skip sportsdataverse.

## 2026-08-23 -- Clean table name: `prop_results`
**Decided:** Phase-3 joined output lives in SQLite table `prop_results` (one row per `odds_snapshots.snapshot_id`), with supporting `name_map` and `odds_events`.
**Alternatives:** `odds_joined`; overwrite/enrich `odds_snapshots` in place.
**Why:** Keeps raw odds append-only and auditable; clear name for prop line + outcome fields + flags; unmatched rows persist here with `reason_code` instead of being dropped.
**Revisit if:** A later phase needs a narrower eval-only table and `prop_results` becomes too wide.

## 2026-08-23 -- Timezone: UTC storage, join on `game_date_et`
**Decided:** Store Odds API `commence_time` as UTC in `odds_events.commence_time_utc`. Derive `game_date_et` via `zoneinfo` (`America/New_York`). Add `games.game_date_et` (migration in `db.py`) backfilled from ESPN/`sportsdataverse` `game_date`, treated as the Eastern calendar date already used by the stats source. Join odds->player_games on `player_id` + `game_date_et` (never string date arithmetic).
**Alternatives:** Join on UTC calendar date; store everything as naive local strings.
**Why:** Late Pacific tips are the next UTC day; ET calendar date is what the league schedule means by game night.
**Revisit if:** Stats source starts providing tip timestamps and we can validate ESPN `game_date` against true ET.

## 2026-08-23 -- Voided props definition
**Decided:** `is_voided=1` when a matched `player_games` row has `dnp_reason` set, or minutes <= 0 / null (including `availability` dnp/inactive). `actual_points` is set to NULL for voided rows so outcome evaluation excludes them; the row is kept with `void_reason`. Unders that played are not voided.
**Alternatives:** Delete voided rows; treat DNP as 0 points / under hits; void only official scratched injury codes.
**Why:** Spec/guide: scratched/DNP props are not unders; silent 0s catastrophically inflate under win rate.
**Revisit if:** Books void rules diverge from box-score DNP (e.g. played 1 minute then void) and we get a void feed.

## 2026-08-23 -- Fuzzy name policy: propose only
**Decided:** Exact (NFKD, strip punct, collapse space, lower) and team+date auto-write `name_map` with `mapped_by=auto_exact|auto_team_date`. Fuzzy matches are printed and listed in `reports/unmatched.md` with `reason_code=needs_fuzzy_approval` and **never** auto-accepted. Persist only via existing `name_map` or `run.py clean --approve 'Raw=player_id'` / `--approvals-file`.
**Alternatives:** Auto-accept above a similarity threshold; interactive TTY prompt each run.
**Why:** Spec forbids silent fuzzy accepts; approvals must be durable and explicit.
**Revisit if:** Matt wants a curated starter crosswalk committed to the repo.

## 2026-08-23 -- Direct deps: pandas + numpy for as-of features
**Decided:** Declare `pandas` and `numpy` as direct runtime dependencies in `pyproject.toml` (they were already transitive via sportsdataverse).
**Alternatives:** Pure stdlib + sqlite rolling; add scipy too.
**Why:** Phase-4 as-of trailing/EWM/groupby transforms are leakage-sensitive and much clearer/safer in pandas; scipy not needed yet. Justified by AGENTS ask-rule for this phase.
**Revisit if:** A later phase needs sklearn scalers (fit inside fold only) or scipy stats.

## 2026-08-23 -- Shrinkage k values (phase 4 defaults)
**Decided:** config `features.shrinkage`: `player_form_k=8`, `usage_k=10`, `team_k=12`, `opponent_k=20`, `opponent_positional_k=25`, `teammate_hist_k=30`, `expansion_extra_k=20` (added on top of team/opp k for TOR/POR).
**Alternatives:** k=1 style hot-streak chasing; identical k for all families; estimate k from empirical Bayes on full history (leaks).
**Why:** 44-game season -- prior must do real work. Opponent/positional/teammate samples are tiny so k is larger. Expansion franchises get extra prior weight. Tune later on time-based validation folds (phase 9), not by eyeballing in-sample.
**Revisit if:** Validation shows systematic under/over-shrink for a family.

## 2026-08-23 -- Shot mix without rim/mid split
**Decided:** Role shot-mix features are `three_rate_std` (fg3a/fga) and `two_rate_std` ((fga-fg3a)/fga) plus `ft_rate_std` (fta/fga), all season-to-date as-of. No rim vs mid split.
**Alternatives:** Parse sportsdataverse PBP for shot zones now.
**Why:** Box scores in `player_games` lack rim/mid location; PBP zone features can land later without changing the leakage contract.
**Revisit if:** Phase needing shot quality finds two-point lump too coarse.

## 2026-08-23 -- Cold-start priors are fixed anchors, not full-column means
**Decided:** When as-of league/position priors are missing (season game 1), use fixed anchors (pace 80, ortg/drtg 100, usage 0.20, position pts priors G/F/C = 16/15/14) rather than `fillna(column.mean())` over all rows.
**Alternatives:** Fit priors on prior seasons only; leave nulls.
**Why:** Spec forbids fillna with full-column mean (distribution leakage). Fixed anchors are non-leaky and make expansion / opener rows well-defined.
**Revisit if:** Multi-season prior seasons become the explicit hierarchical prior in rate models.

## 2026-08-23 -- Features entrypoints: `run.py features` + end of `clean`
**Decided:** `python run.py features` rebuilds `player_game_features`. `python run.py clean` also rebuilds features afterward unless `--skip-features`.
**Alternatives:** Features only inside `train`; silent module import; seventh unrelated command name.
**Why:** Spec DoD needs a readable build that prints the summary; AGENTS lists six product commands but phase 4 needs an explicit rebuild path before train exists. Idempotent DELETE+INSERT.
**Revisit if:** Feature rebuild becomes too slow nightly and should move behind `train` only.

## 2026-08-23 -- Minutes share: independent + normalize; Dirichlet for sim
**Decided:** Predict per-player minutes with quantile HGB, renormalize active players' shares to the team budget (200 regulation; +25xOT only after an explicit OT event). Use Dirichlet(`alpha_i = kappa * share_i`, `kappa=40`) when sampling joint rotations for simulation.
**Alternatives:** Full Dirichlet MLE / hierarchical concentration per rotation archetype; raw independent minutes with no renormalization.
**Why:** Spec allows independent+normalize for v1 if Dirichlet machinery is heavy; renormalization enforces the free sum constraint. Dirichlet sampling still gives the desired negative correlation in sims without fitting a full composition model.
**Revisit if:** Tail dependence under injuries looks wrong in phase 7 simulation, or a proper Dirichlet regression is worth the complexity.

## 2026-08-23 -- Direct deps: scikit-learn, scipy, matplotlib (phase 5)
**Decided:** Add `scikit-learn`, `scipy`, and `matplotlib` as direct runtime dependencies.
**Alternatives:** Pure numpy IRLS logistic + homemade quantiles; skip calibration plots.
**Why:** Required for this phase -- HistGradientBoosting (DNP + quantile minutes), Dirichlet sampling (`scipy`/`numpy`), calibration curve + plot to `reports/`. Fits AGENTS ask-rule (justify before adding).
**Revisit if:** A later phase standardizes on a different ML stack.

## 2026-08-23 -- Minutes holdout: train <=2024 / test >=2025
**Decided:** Time-based split only: train seasons <=2024, test >=2025 (2025-2026 holdout). No random split.
**Alternatives:** Last 20% of games by date; expanding-window CV.
**Why:** Clear season boundary; matches AGENTS time-split rule; leaves two seasons (~13.8k rows) for evaluation including expansion TOR/POR.
**Revisit if:** Phase 9 wants rolling season-backtests as the primary yardstick.

## 2026-08-23 -- Coverage vs trailing-5 via residual-band Winkler
**Decided:** Report quantile-regression 50/80/95 coverage as the DoD model intervals. For the stop-rule comparison vs trailing-5, build residual-band intervals around each point forecast (model median vs trail5) and declare coverage win by lower mean Winkler score (calibration + sharpness).
**Alternatives:** Compare raw |cov-nominal| only; give trail5 no intervals.
**Why:** A point baseline has no native intervals; residual bands are the apples-to-apples construction. Winkler penalizes both miscalibration and over-width so a sharper calibrated model can win.
**Revisit if:** User prefers a different coverage yardstick (e.g. interval score at fixed width).

## 2026-08-23 -- Blowout proxy without spreads
**Decided:** Condition on `favoritism = team_off_rtg_shrunk - opp_def_rtg_shrunk` because historical game spreads are not in the odds tables (player_points only).
**Alternatives:** Skip game-script features until spreads are ingested; scrape historical spreads.
**Why:** Guide says team strength differential works when lines are missing; keeps phase 5 unblocked.
**Revisit if:** Closing spreads are ingested and can replace/augment this proxy.

## 2026-08-23 -- 3PM as Binomial(3PA, p3) with Beta EB (not Poisson)
**Decided:** Model threes as `3PM ~ Binomial(3PA, p3)`. `3PA` mean = shrunk per-40 rate x minutes/40 x team opp factor, drawn from NegativeBinomial (gamma-Poisson); `p3 ~ Beta(alpha, beta)` with hierarchical EB prior league -> role -> player (kappa_role=40 prior attempts). No MCMC yet.
**Alternatives:** Poisson 3PM; Beta-Binomial with fixed attempts; full PyMC/numpyro hierarchy.
**Why:** Spec/guide: attempts and accuracy are separate; small-sample 3P% is unstable (6-for-12 != 50%). Observed var/mean for 3PA is 2.62 (>>1) so Poisson attempts are too narrow; Binomial+Beta induces the right 3PM overdispersion once attempts vary.
**Revisit if:** PIT stays sloped after era-adjusted priors, or MCMC is needed for honest posteriors in phase 9.

## 2026-08-23 -- 3PM shrinkage kappa and opponent k
**Decided:** `p3_kappa_league=200`, `p3_kappa_role=40`, `pa_k_league=80`, `pa_k_role=20`, `opp_k=25` (games) in `config.yaml` `rates_3pm`.
**Alternatives:** kappa from full MOM EB on player-level variance; weaker kappa (chase hot streaks); playerxopponent interactions.
**Why:** 44-game season -- prior must work. Role kappa=40 ~= one season of prior attempts. Opponent effects only at team level; train-era teams have 206-250 games (estimable). Playerxteam would have a handful of games -- not used.
**Revisit if:** Validation wants weaker/stronger shrink, or expansion-team opp factors need a dedicated prior.

## 2026-08-23 -- train CLI gains --stat for minutes vs 3pm
**Decided:** `python run.py train --stat all|minutes|3pm` (default `all` = minutes then 3pm).
**Alternatives:** Separate `train-rates` command; always train both with no flag.
**Why:** Spec allows extending train or `--stat 3pm`; keeps one entrypoint while allowing fast 3PM iteration without refitting minutes.
**Revisit if:** More stats arrive and `all` becomes too slow for a daily loop.

## 2026-08-23 -- Rebounds as NegativeBinomial (not Poisson)
**Decided:** Model rebounds as `REB ~ NegBin(mu = reb_p40 x minutes/40 x opp_factor, r)` via gamma-Poisson mixture. Hierarchical EB shrinks `reb_p40` league -> role (G/F/C) -> player (`reb_k_role=20` exposure units). Dispersion `r` from method-of-moments on train played counts (`r~=1.94`). No OREB/DREB split in v1. No MCMC.
**Alternatives:** Poisson (forces var=mean); separate OREB+DREB NBs; Beta-Binomial style; full PyMC hierarchy.
**Why:** Spec forbids Poisson for rebounds. Observed var/mean = **2.877** (>>1) on played rows -- Poisson would be too narrow and overstate confidence on low lines. Role hierarchy captures G vs C rate gap (~4.6 vs ~10.5 per-40).
**Revisit if:** PIT stays peaked after tuning `r` (or after phase-7 minutes uncertainty), or OREB/DREB split improves CRPS enough to justify complexity.

## 2026-08-23 -- Rebounds shrinkage k and opponent k
**Decided:** `reb_k_league=80`, `reb_k_role=20`, `opp_k=25` (games), `nb_r_fallback=3.0` in `config.yaml` `rates_reb`. Same time split as 3PM (train <=2024 / test >=2025).
**Alternatives:** Weaker k (chase form); estimate k from player-level EB MOM; playerxopponent interactions; fit `r` on holdout (leak).
**Why:** Matches 3PM pa_* scale; prior must work in a 44-game season. Opponent effects team-level only -- train-era teams have 206-250 games (estimable). Playerxteam would be a handful of games.
**Revisit if:** Peaked PIT persists and larger `r` (less overdispersion) or weaker/stronger shrink improves calibration without losing the CRPS edge.

## 2026-08-23 -- train CLI --stat gains reb
**Decided:** `python run.py train --stat all|minutes|3pm|reb` (default `all` = minutes, then 3pm, then reb).
**Alternatives:** Separate `train-reb` command; keep reb behind a hidden flag until ast/pts land.
**Why:** Continues the phase-6 `--stat` pattern; keeps 3PM path working; allows fast reb iteration without refitting minutes/3PM.
**Revisit if:** `all` becomes too slow once assists/points are added.
