### Phase 6 (points only) - 2026-08-23
**Built:** Hierarchical empirical-Bayes points rate model -- `src/rates_pts_data.py`, `src/rates_pts_model.py`, `src/rates_pts_eval.py`, `src/model_rates_pts.py`. Distribution `PTS ~ NegativeBinomial(mu = pts_p40 x minutes/40 x opp_factor, r)` (gamma-Poisson; **NOT Poisson**). Hierarchy league -> role (G/F/C) -> player. Opponent = team-level pts-allowed factor only (sample sizes stated). Wired `python run.py train --stat pts` (3PM + reb + ast paths unchanged). Artifacts: `models/rates_pts_model.pkl` (+ meta), `reports/rates_pts_metrics.json`, `reports/rates_pts_pit.png`, `reports/rates_pts_shrinkage.csv`. Tests: `tests/test_rates_pts.py`. **Not built:** PRA/combos, component-sum PTS simulation, phase 7.
**Variance-to-mean (played):** pts **6.312**; pts_p40 7.571 -- clear overdispersion; NB justified (near-1 would have triggered reconsider).
**Holdout (train <=2024 / test >=2025; conditioned on realized minutes):**
- CRPS model **2.7279** vs season-to-date **2.7311** vs trailing-10 **2.7442** (beats both)
- PIT: **peaked** -- distributions too wide (underconfident; MOM `r~=1.63` may overspread relative to holdout)
- Shrinkage: pts prior weight mean=0.544 p50=0.532; ESS mean=64.2 p50=37.6; `pts_k_role=20`
- Opp factors: 12 train-era teams; n_games min/median/max = 206/222/250 (no playerxteam)
- League pts_p40=16.21; role G/F/C ~= 16.18 / 15.77 / 17.30; NB_r=1.633
**Status:** Phase 6 rate stats **complete** (3PM + reb + ast + pts). Stop -- do **not** start phase 7.
**Unresolved:** PIT peaked (consider larger `r` / less overdispersion, or minutes uncertainty in phase 7); expansion TOR/POR default opp factor 1.0; MAE of predictive mean slightly worse than season-to-date while CRPS is better; build-spec component-sum PTS (2PM/3PM/FTM) deferred to phase-7 simulation; phase 7 not started.
