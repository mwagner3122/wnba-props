### Phase 9 (evaluation only) - 2026-08-23
**Built:** Walk-forward evaluation layer — `src/eval_metrics.py`, `src/eval_walkforward.py`, `src/eval_predict.py`, `src/eval_market_clv.py`, `src/evaluate.py`. CLI: `python run.py evaluate`. Config: `evaluation:` in `config.yaml`. Tests: `tests/test_evaluate.py`. **Not built:** phase 10 automation; bankroll/ROI/units; any peek at frozen holdout.
**Validation:** Walk-forward weekly only (32 folds; train through D → predict next week). `eval_start_date=2025-06-01`; **frozen holdout 2026-08-02 .. 2026-08-22 (21 days) untouched**. Predictions use **projected minutes** (trailing-5 as-of); eval rows filter realized minutes>=1. No random split.
**Baseline table (CRPS, lower better; n=9387 per market):**

| market | model | b1 season-avg | b2 trail-10 avg | b3 trail-10 per-40 × proj min | b4 market | beat 3? | beat 4? |
|---|---:|---:|---:|---:|---|---|---|
| pts | 3.2995 | 3.1627 | 3.1594 | 3.2725 | N/A | **LOSE** | N/A |
| reb | 1.3339 | 1.2604 | 1.2485 | 1.3374 | N/A | BEAT | N/A |
| ast | 0.9231 | 0.8489 | 0.8488 | 0.9131 | N/A | **LOSE** | N/A |
| fg3m | 0.5015 | 0.5043 | 0.5012 | 0.5040 | N/A | BEAT | N/A |

**Overall (row-weighted):** model CRPS **1.5145** vs b3 **1.5068** → **LOSE to baseline 3**.
**Baseline 4:** N/A — no posted two-way prices joined to realized outcomes (`prop_results` matched=0, actual_points=0; live odds are future tips only).
**PIT (verbal):** all four markets **sloped** (under-projecting on average). Coverage 50/80/95%: pts 0.581/0.846/0.954; reb 0.715/0.915/0.967; ast 0.770/0.932/0.976; fg3m 0.814/0.924/0.976 (reb/ast/fg3m intervals too wide).
**Plots:** `reports/phase9_pit_{pts,reb,ast,fg3m}.png` (gitignored PNGs; regenerate via `evaluate`). Table/JSON: `reports/phase9_baseline_table.csv`, `reports/phase9_metrics.json`.
**Binary vs posted line:** SKIPPED — see `reports/phase9_reliability.SKIPPED.txt`.
**CLV:** SKIPPED — closing lines unavailable (2 capture timestamps; no near-tip/closing on completed games). Not substituted.
**Plain gate statements:** Model does **not** clearly beat baseline 3 (loses overall; wins only reb + fg3m narrowly). Baseline 4 **cannot** be scored. **STOP** — do not start phase 10.
**Unresolved:** Need historical odds archive with outcomes before binary metrics / baseline 4 / CLV exist; PIT slope (under-projection) + over-wide intervals on reb/ast/fg3m; joint-sim minutes uncertainty not folded into every OOS row (projected-minutes point used for compute). Results do **not** look too good — no leakage celebration audit triggered.
