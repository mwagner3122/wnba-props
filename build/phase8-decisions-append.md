
## 2026-08-23 -- Phase 8 de-vig default multiplicative; print both
**Decided:** Implement multiplicative and power de-vig; `pricing.default_devig_method: multiplicative` selects which fair_p_over feeds edge. Always print/store both methods per two-way quote (`reports/pricing_hold.csv` + console). Power solves `q_over^k + q_under^k = 1` with `scipy.optimize.brentq`.
**Alternatives:** Additive de-vig; Shin; power-as-default.
**Why:** Spec + guide section 12: balanced -115/-115 agree; lopsided markets diverge (informative). Multiplicative is the simple default; power is available without a second code path at decision time.
**Revisit if:** Validation (phase 9) shows edge/CLV sensitive to method choice.

## 2026-08-23 -- Fair P = consensus de-vig; best price = max decimal over
**Decided:** `fair_mode: consensus` averages de-vigged fair_over across books at the same (player_id, market, line). Best available over price = highest decimal odds among books. Edge = model_p_over - fair_p_over; EV and Kelly use the best over price. Optional `fair_mode: sharp_book` + `sharp_book: draftkings`.
**Alternatives:** Always use one sharp book; vig-free mid from favorite book only; blend lines across different posted lines.
**Why:** Guide section 12.3 -- conflating market estimate with executable price is costly both ways. Different books often post different lines; we only consensus within an identical line.
**Revisit if:** A trusted sharp feed is designated, or line-shopping across nearby lines is desired.

## 2026-08-23 -- Quarter Kelly default 0.25; min edge 3%; stake on $100 bankroll
**Decided:** `kelly_fraction: 0.25`, `min_edge: 0.03`, `bankroll: 100.0`. Print full Kelly and fractional; zero stake when |edge| < min_edge. CSV stake column is fractional-Kelly x bankroll (dollars on the configured bankroll), not a profit projection.
**Alternatives:** Half Kelly; edge floor 2%; omit dollar stake (fraction only).
**Why:** Spec defaults. Full Kelly assumes p is correct; it is not. Edge floor treats sub-3% edges as noise vs model error. Dollar stake makes the fraction tangible without claiming ROI.
**Revisit if:** Phase 9 calibration suggests a different floor/fraction.

## 2026-08-23 -- Model P(over) via Phase-7 projection sim on last-played rosters
**Decided:** For each upcoming odds event, stitch each side's most recent completed-game roster (played_only), remap opponent factors to the upcoming matchup, run Phase-7 joint sim (`pricing.n_sim: 5000`, seed 8), set model_p_over = P(pts > line). Explicit note: LAST PLAYED ROSTER -- not true pregame availability.
**Alternatives:** Marginal phase-6 PTS NB only; skip model_p until phase 10 availability; require stats_game_id match.
**Why:** Today's slate has no box scores yet (`stats_game_id` null). Joint component PTS matches phase 7. Honest limitation printed; phase 10 owns real availability.
**Revisit if:** Pregame availability/injury feeds land, or projection bias vs openers is large in phase 9.
