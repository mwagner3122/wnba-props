### Phase 9 beat-b3 fix - 2026-08-23
**Built:** Focused OOS calibration pass (HOLD phase 10). `src/eval_predict.py` (plain): fold-wise mean calibration + L10 rate blend (pts/reb/ast) + light projected-minutes noise; `src/evaluate.py` expanded/plain + honesty fields; tunables under `config.yaml` `evaluation:`. Re-ran `python run.py evaluate` (same walk-forward protocol; holdout untouched).
**Before (PR #13 tip):** overall model CRPS **1.5145** vs b3 **1.5068** → **LOSE**. Per-market vs b3: pts LOSE, reb BEAT, ast LOSE, fg3m BEAT. PIT all sloped (under-projecting).
**After:**

| market | model | b3 | plain |
|---|---:|---:|---|
| pts | 3.2286 | 3.2799 | **BEAT** |
| reb | 1.3176 | 1.3359 | **BEAT** |
| ast | 0.8981 | 0.9129 | **BEAT** |
| fg3m | 0.4986 | 0.5039 | **BEAT** |

**Overall (row-weighted):** model CRPS **1.4857** vs b3 **1.5082** → **BEAT baseline 3**.
**Baseline 4 / CLV / binary:** still N/A / SKIPPED (unchanged honesty).
**PIT:** pts/ast/fg3m still **sloped** but milder (pts corr 0.84→0.61); reb **peaked** (minutes noise widened). Coverage 50/80/95%: pts 0.622/0.861/0.959; reb 0.728/0.924/0.973; ast 0.793/0.942/0.982; fg3m 0.833/0.936/0.982.
**Plain gate:** Model **BEATS baseline 3** overall and on all four markets. Baseline 4 still N/A. **STOP for gate — do not start phase 10.**
**Unresolved:** PIT residual slope; reb over-width; no historical closing/posted lines for b4/CLV/binary; component-sum PTS still deferred; not full phase-7 joint minutes.
