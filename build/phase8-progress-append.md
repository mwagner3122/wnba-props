
### Phase 8 (pricing only) - 2026-08-23
**Built:** Pricing layer -- `src/pricing_odds.py` (American->implied, hold, multiplicative + power de-vig via `brentq`), `src/pricing_kelly.py` (edge, EV vs best price, full + fractional Kelly, min-edge floor), `src/pricing_config.py`, `src/pricing_markets.py` (slate quotes, hold printout both methods, fair P vs best available over price), `src/pricing_model_p.py` (projection roster from each side's last played game + Phase-7 joint sim -> model P(over)), `src/project.py`. Wired `python run.py project`. Config under `pricing:`. Tests: `tests/test_pricing.py` (12). Artifacts: `reports/pricing_hold.csv`, `reports/slate_priced.csv`. **Not built:** bankroll graph, profit projection, ROI, phase 9 evaluation.
**DoD (evidenced on live slate capture 2026-08-23T15:19:13Z):**
1. Hold printed per two-way market -- **PASS** (549 quotes; mean hold ~= 6.75%; sample Awak Kuier FD 8.5 hold=6.64%)
2. Both de-vig methods side by side -- **PASS** (hold CSV + console: mult vs power; balanced ~= agree, lopsided -250/+190 diverges: mult fair_over~=67.4% vs power~=69.0%)
3. Fair vs best price clearly distinguished -- **PASS** (console labels FAIR_P(over) vs BEST_PRICE; CSV columns `fair_p_over` / `best_price`+`book`; edge = model_p - fair_p; EV vs best price)
4. Slate CSV sorted by edge -- **PASS** -> `reports/slate_priced.csv` (67 rows locally; sample committed; regenerate full with `python run.py project`)
**CLI:** `uv run python run.py project`
**Status:** Phase 8 **complete**. STOP -- wait for user gate. Do **not** start phase 9.
**Unresolved:** Projection uses LAST PLAYED roster per team (not true pregame availability -- phase 10); 2/67 markets missing model_p (player on odds but not in last-played roster); odds markets still player_points-only; name_map can collapse distinct raw names onto one player_id (aggregated by player_id); phase 9 has not validated that edges are real -- no ROI/bankroll claims.
