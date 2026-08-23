### Phase 6 (assists only) - 2026-08-23
**Built:** Hierarchical empirical-Bayes assists rate model -- `src/rates_ast_data.py`, `src/rates_ast_model.py`, `src/rates_ast_eval.py`, `src/model_rates_ast.py`. Distribution `AST ~ NegativeBinomial(mu = ast_p40 x minutes/40 x opp_factor, r)` (gamma-Poisson; **NOT Poisson**). Hierarchy league -> role (G/F/C) -> player. Opponent = team-level ast-allowed factor only (sample sizes stated). Wired `python run.py train --stat ast` (3PM + reb paths unchanged). Artifacts: `models/rates_ast_model.pkl` (+ meta), `reports/rates_ast_metrics.json`, `reports/rates_ast_pit.png`, `reports/rates_ast_shrinkage.csv`. Tests: `tests/test_rates_ast.py`. **Not built:** points, PRA/combos, phase 7.
**Variance-to-mean (played):** ast **2.402**; ast_p40 3.772 -- clear overdispersion; NB justified (near-1 would have triggered reconsider).
**Holdout (train <=2024 / test >=2025; conditioned on realized minutes):**
- CRPS model **0.8293** vs season-to-date **0.8324** vs trailing-10 **0.8329** (beats both)
- PIT: **peaked** -- distributions too wide (underconfident; MOM `r~=1.52` may overspread relative to holdout)
- Shrinkage: ast prior weight mean=0.544 p50=0.532; ESS mean=64.2 p50=37.6; `ast_k_role=20`
- Opp factors: 12 train-era teams; n_games min/median/max = 206/222/250 (no playerxteam)
- League ast_p40=3.92; role G/F/C ~= 4.82 / 3.05 / 2.60; NB_r=1.517
**Status:** Phase 6 **in progress**. 3PM done, reb done, ast done. Stop -- do **not** start points or phase 7.
**Unresolved:** PIT peaked (consider larger `r` / less overdispersion, or minutes uncertainty in phase 7); expansion TOR/POR default opp factor 1.0; MAE of predictive mean slightly worse than baselines while CRPS is better; pts not started.
