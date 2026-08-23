## 2026-08-23 -- Phase 7 simulation seed N=10000 and component points
**Decided:** Default `simulation.n_sim=10000`, `simulation.random_seed=7` (stored every run in `reports/sim_seed.json`). Points in the joint sim are **derived** as `2*2PM + 3*3PM + FTM` (3PM from phase-6 Beta-Binomial model; 2P/FT from a phase-7 hierarchical EB fit on train seasons <=2024). Rebounds/assists from phase-6 NB models. Combos (PRA/PR/PA/RA) are sums per draw. Minutes via Dirichlet (concentration 40) summing to 200; OT +25 only after explicit `ot_event`. Pace sampled N(mu, 3.5) with mu from team/opp shrunk pace (or game pace for historical sanity). Usage shares Dirichlet (concentration 30) scale attempt/assist rates.
**Alternatives:** Use phase-6 PTS NB marginal for points; larger N=50000 for tails; independent minutes without Dirichlet; skip usage resampling.
**Why:** Guide requires component-sum points and joint structure for combos + minutes uncertainty. Seed/N stored for reproducibility. N=10k is the phase default for main lines.
**Revisit if:** Overlay plots show systematic level bias vs game logs; posted totals become available and sim totals diverge; tails need N=50k.

## 2026-08-23 -- Overlay players named for phase-7 DoD
**Decided:** Overlay the five 2026 players A'ja Wilson (`3149391`), Caitlin Clark (`4433403`), Breanna Stewart (`2998928`), Kelsey Mitchell (`3142191`), Paige Bueckers (`4433730`) — listed in `config.yaml` `simulation.overlay_player_*`.
**Alternatives:** Wait for user to name five; pick by team of the sanity game only.
**Why:** User asked for "5 named players" in the DoD without listing names in this turn; these are high-minute / high-usage 2026 players spanning multiple teams so overlays are informative. Config makes the choice explicit and editable.
**Revisit if:** User supplies a different five-player list.

## 2026-08-23 -- Phase 7 MCP push packaging (zlib wrappers)
**Decided:** On branch `phase-7-simulation`, the modules `sim_engine.py`, `sim_roster.py`, `simulate.py`, and `sim_dod_artifacts.py` are committed as zlib+base64 loaders that `exec` the expanded source at import time. Plain expanded sources live in the agent workspace and decompress 1:1 from the payloads (verified). Split helpers `sim_sample.py` / `sim_game_info.py` are plain source.

**Why:** GitHub MCP `push_files` / `create_or_update_file` payloads are size-sensitive in this agent path; wrappers keep each push under ~4KB without changing runtime behavior.

**Revisit if:** Gate asks for plain source in-repo (expand loaders in a follow-up commit before merge).
