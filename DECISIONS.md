

## 2026-08-23 — Minutes share: independent + normalize; Dirichlet for sim
**Decided:** Predict per-player minutes with quantile HGB, renormalize active players' shares to the team budget (200 regulation; +25×OT only after an explicit OT event). Use Dirichlet(`α_i = κ · share_i`, `κ=40`) when sampling joint rotations for simulation.
**Alternatives:** Full Dirichlet MLE / hierarchical concentration per rotation archetype; raw independent minutes with no renormalization.
**Why:** Spec allows independent+normalize for v1 if Dirichlet machinery is heavy; renormalization enforces the free sum constraint. Dirichlet sampling still gives the desired negative correlation in sims without fitting a full composition model.
**Revisit if:** Tail dependence under injuries looks wrong in phase 7 simulation, or a proper Dirichlet regression is worth the complexity.

## 2026-08-23 — Direct deps: scikit-learn, scipy, matplotlib (phase 5)
**Decided:** Add `scikit-learn`, `scipy`, and `matplotlib` as direct runtime dependencies.
**Alternatives:** Pure numpy IRLS logistic + homemade quantiles; skip calibration plots.
**Why:** Required for this phase — HistGradientBoosting (DNP + quantile minutes), Dirichlet sampling (`scipy`/`numpy`), calibration curve + plot to `reports/`. Fits AGENTS ask-rule (justify before adding).
**Revisit if:** A later phase standardizes on a different ML stack.

## 2026-08-23 — Minutes holdout: train ≤2024 / test ≥2025
**Decided:** Time-based split only: train seasons ≤2024, test ≥2025 (2025–2026 holdout). No random split.
**Alternatives:** Last 20% of games by date; expanding-window CV.
**Why:** Clear season boundary; matches AGENTS time-split rule; leaves two seasons (~13.8k rows) for evaluation including expansion TOR/POR.
**Revisit if:** Phase 9 wants rolling season-backtests as the primary yardstick.

## 2026-08-23 — Coverage vs trailing-5 via residual-band Winkler
**Decided:** Report quantile-regression 50/80/95 coverage as the DoD model intervals. For the stop-rule comparison vs trailing-5, build residual-band intervals around each point forecast (model median vs trail5) and declare coverage win by lower mean Winkler score (calibration + sharpness).
**Alternatives:** Compare raw |cov−nominal| only; give trail5 no intervals.
**Why:** A point baseline has no native intervals; residual bands are the apples-to-apples construction. Winkler penalizes both miscalibration and over-width so a sharper calibrated model can win.
**Revisit if:** User prefers a different coverage yardstick (e.g. interval score at fixed width).

## 2026-08-23 — Blowout proxy without spreads
**Decided:** Condition on `favoritism = team_off_rtg_shrunk − opp_def_rtg_shrunk` because historical game spreads are not in the odds tables (player_points only).
**Alternatives:** Skip game-script features until spreads are ingested; scrape historical spreads.
**Why:** Guide says team strength differential works when lines are missing; keeps phase 5 unblocked.
**Revisit if:** Closing spreads are ingested and can replace/augment this proxy.
