## 2026-08-23 — Direct deps: pandas + numpy for as-of features
**Decided:** Declare `pandas` and `numpy` as direct runtime dependencies in `pyproject.toml` (they were already transitive via sportsdataverse).
**Alternatives:** Pure stdlib + sqlite rolling; add scipy too.
**Why:** Phase-4 as-of trailing/EWM/groupby transforms are leakage-sensitive and much clearer/safer in pandas; scipy not needed yet. Justified by AGENTS ask-rule for this phase.
**Revisit if:** A later phase needs sklearn scalers (fit inside fold only) or scipy stats.

## 2026-08-23 — Shrinkage k values (phase 4 defaults)
**Decided:** config `features.shrinkage`: `player_form_k=8`, `usage_k=10`, `team_k=12`, `opponent_k=20`, `opponent_positional_k=25`, `teammate_hist_k=30`, `expansion_extra_k=20` (added on top of team/opp k for TOR/POR).
**Alternatives:** k=1 style hot-streak chasing; identical k for all families; estimate k from empirical Bayes on full history (leaks).
**Why:** 44-game season — prior must do real work. Opponent/positional/teammate samples are tiny so k is larger. Expansion franchises get extra prior weight. Tune later on time-based validation folds (phase 9), not by eyeballing in-sample.
**Revisit if:** Validation shows systematic under/over-shrink for a family.

## 2026-08-23 — Shot mix without rim/mid split
**Decided:** Role shot-mix features are `three_rate_std` (fg3a/fga) and `two_rate_std` ((fga−fg3a)/fga) plus `ft_rate_std` (fta/fga), all season-to-date as-of. No rim vs mid split.
**Alternatives:** Parse sportsdataverse PBP for shot zones now.
**Why:** Box scores in `player_games` lack rim/mid location; PBP zone features can land later without changing the leakage contract.
**Revisit if:** Phase needing shot quality finds two-point lump too coarse.

## 2026-08-23 — Cold-start priors are fixed anchors, not full-column means
**Decided:** When as-of league/position priors are missing (season game 1), use fixed anchors (pace 80, ortg/drtg 100, usage 0.20, position pts priors G/F/C = 16/15/14) rather than `fillna(column.mean())` over all rows.
**Alternatives:** Fit priors on prior seasons only; leave nulls.
**Why:** Spec forbids fillna with full-column mean (distribution leakage). Fixed anchors are non-leaky and make expansion / opener rows well-defined.
**Revisit if:** Multi-season prior seasons become the explicit hierarchical prior in rate models.

## 2026-08-23 — Features entrypoints: `run.py features` + end of `clean`
**Decided:** `python run.py features` rebuilds `player_game_features`. `python run.py clean` also rebuilds features afterward unless `--skip-features`.
**Alternatives:** Features only inside `train`; silent module import; seventh unrelated command name.
**Why:** Spec DoD needs a readable build that prints the summary; AGENTS lists six product commands but phase 4 needs an explicit rebuild path before train exists. Idempotent DELETE+INSERT.
**Revisit if:** Feature rebuild becomes too slow nightly and should move behind `train` only.
