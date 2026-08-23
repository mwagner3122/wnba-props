# Phase 9 beat-b3 fix notes

Same protocol as PR #13. Holdout untouched. No bankroll/ROI/units. No fake CLV.

## Change
- Fold-wise multiplicative mean calibration (`mean_cal_days=45`, scale clip [0.90, 1.35])
- L10 per-40 blend for pts/reb/ast (`rate_l10_blend=0.55`); fg3m blend=0
- Light projected-minutes noise (`minutes_uncertainty_sd_frac=0.10`)
- Direct NB PTS retained (component deferred)

## Result
Overall BEAT b3: 1.4857 vs 1.5082 (was LOSE 1.5145 vs 1.5068).
All markets BEAT b3.
