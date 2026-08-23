## 2026-08-23 -- Phase 9 beat-b3: fold-wise mean cal + L10 blend + light minutes noise
**Decided:** One coherent OOS predictive fix in `eval_predict` / `evaluation:` config (not a phase-10 start):
1. **Multiplicative mean calibration** fit each walk-forward fold on the last `mean_cal_days=45` train days using **projected** minutes (clipped to `[0.90, 1.35]`). Attacks PIT under-projection without peeking at the fold test window or the frozen holdout.
2. **Blend hierarchical per-40 with trailing-10 per-40** for pts/reb/ast (`rate_l10_blend=0.55`). Career-expanding EB priors lag the 2025-26 scoring environment; L10 is the structural signal behind baseline 3.
3. **fg3m:** calibration scales `pa_p40` only; `fg3m_l10_blend=0.0` (do not blend L10 *makes* into attempt rate — unit mismatch hurt CRPS in probes).
4. **Light projected-minutes uncertainty:** Gaussian noise around trailing-5 with `minutes_uncertainty_sd_frac=0.10` (clipped 0–42), model samples only. **Not** full phase-7 joint Dirichlet; b3 still uses point trailing-5 minutes.
5. **Component-sum PTS deferred** — retain direct NB for this pass (component path is a larger sim change; rate-location fix was the binding constraint vs b3).
**Alternatives:** Weaker role `k` only; EWM career prior rewrite in all rate models; full joint sim OOS; component PTS now.
**Why:** Baseline loss was location bias (PIT sloped under-projecting) especially on pts/ast where career EB lagged L10. Fold-wise cal + blend directly targets that gap while staying leakage-safe.
**Revisit if:** PIT slope remains material; reb intervals stay too wide (peaked PIT after minutes noise); component PTS or true phase-7 minutes clearly beat this on the same protocol.
