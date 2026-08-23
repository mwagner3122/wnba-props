## 2026-08-23 -- Points as NegativeBinomial (not Poisson; direct rate, not components yet)
**Decided:** Model points as `PTS ~ NegBin(mu = pts_p40 x minutes/40 x opp_factor, r)` via gamma-Poisson mixture. Hierarchical EB shrinks `pts_p40` league -> role (G/F/C) -> player (`pts_k_role=20` exposure units). Dispersion `r` from method-of-moments on train played counts (`r~=1.63`). No MCMC. Direct points rate (mirrors reb/ast) for phase-6 DoD; build-spec component sum `PTS = 2*2PM + 3*3PM + FTM` deferred to phase-7 simulation.
**Alternatives:** Poisson (forces var=mean); component-sum only (skip direct PTS); Beta-Binomial style; full PyMC hierarchy.
**Why:** Observed var/mean = **6.312** (>>1) on played rows -- strongly overdispersed like reb/ast; Poisson would be far too narrow. Phase-6 order is one stat at a time with CRPS/PIT/baselines; a direct hierarchical rate matches reb/ast wiring and CLI. Lumpy multi-modal shape from components still belongs in phase-7 joint simulation.
**Revisit if:** PIT stays peaked after tuning `r` (or after phase-7 minutes uncertainty), or component-sum CRPS clearly beats the direct NB on holdout.

## 2026-08-23 -- Points shrinkage k and opponent k
**Decided:** `pts_k_league=80`, `pts_k_role=20`, `opp_k=25` (games), `nb_r_fallback=3.0` in `config.yaml` `rates_pts`. Same time split as 3PM/reb/ast (train <=2024 / test >=2025).
**Alternatives:** Weaker k (chase form); estimate k from player-level EB MOM; playerxopponent interactions; fit `r` on holdout (leak).
**Why:** Matches reb/ast / 3PM pa_* scale; prior must work in a 44-game season. Opponent effects team-level only -- train-era teams have 206-250 games (estimable). Playerxteam would be a handful of games.
**Revisit if:** Peaked PIT persists and larger `r` (less overdispersion) or weaker/stronger shrink improves calibration without losing the CRPS edge.

## 2026-08-23 -- train CLI --stat gains pts
**Decided:** `python run.py train --stat all|minutes|3pm|reb|ast|pts` (default `all` = minutes, then 3pm, then reb, then ast, then pts).
**Alternatives:** Separate `train-pts` command; alias `points` as well as `pts`.
**Why:** Continues the phase-6 `--stat` pattern (`3pm`/`reb`/`ast` short names); keeps prior rate paths working; allows fast pts iteration without refitting earlier models. DB column remains `points`; frame aliases to `pts`.
**Revisit if:** `all` becomes too slow for a daily loop, or phase 7 wants a single joint train entrypoint.
