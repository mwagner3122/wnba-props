## Phase 9 — Evaluation

**Walk-forward window:** Weekly folds from `eval_start_date=2025-06-01` through day before holdout; training uses all history with `game_date <= train_end`. Final **21 calendar days** (`2026-08-02`..`2026-08-22` given max game_date) are a frozen holdout — evaluate/tune refused (`--include-holdout` exits 2).
**Projected minutes:** Trailing-5 as-of mean minutes (shifted). Baseline 3 = trailing-10 per-40 × that projection. Model = hierarchical EB rate × projected minutes (phase-6 rate families), retrained each fold. Full phase-7 joint Dirichlet minutes uncertainty not applied to every OOS row (stated in metrics JSON).
**Baselines 1–2:** Season-to-date / trailing-10 **averages** (mean PPG-style), scored as tight NB (r=50) distributions for CRPS comparability — not rate×minutes.
**Baseline 4 / binary / CLV:** Skipped when `prop_results` lack matched realized outcomes and closing captures; no price substitution.
**Markets evaluated:** pts, reb, ast, fg3m (stat markets). Odds market coverage remains mostly `player_points`.
