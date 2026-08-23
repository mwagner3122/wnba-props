## 2026-08-23 -- Assists as NegativeBinomial (not Poisson)
**Decided:** Model assists as `AST ~ NegBin(mu = ast_p40 x minutes/40 x opp_factor, r)` via gamma-Poisson mixture. Hierarchical EB shrinks `ast_p40` league -> role (G/F/C) -> player (`ast_k_role=20` exposure units). Dispersion `r` from method-of-moments on train played counts (`r~=1.52`). No MCMC.
**Alternatives:** Poisson (forces var=mean); Beta-Binomial style; full PyMC hierarchy; role-free player-only EB.
**Why:** Spec forbids Poisson for assists. Observed var/mean = **2.402** (>>1) on played rows -- Poisson would be too narrow and overstate confidence on low lines. Role hierarchy captures G vs C rate gap (~4.8 vs ~2.6 per-40).
**Revisit if:** PIT stays peaked after tuning `r` (or after phase-7 minutes uncertainty).

## 2026-08-23 -- Assists shrinkage k and opponent k
**Decided:** `ast_k_league=80`, `ast_k_role=20`, `opp_k=25` (games), `nb_r_fallback=3.0` in `config.yaml` `rates_ast`. Same time split as 3PM/reb (train <=2024 / test >=2025).
**Alternatives:** Weaker k (chase form); estimate k from player-level EB MOM; playerxopponent interactions; fit `r` on holdout (leak).
**Why:** Matches reb / 3PM pa_* scale; prior must work in a 44-game season. Opponent effects team-level only -- train-era teams have 206-250 games (estimable). Playerxteam would be a handful of games.
**Revisit if:** Peaked PIT persists and larger `r` (less overdispersion) or weaker/stronger shrink improves calibration without losing the CRPS edge.

## 2026-08-23 -- train CLI --stat gains ast
**Decided:** `python run.py train --stat all|minutes|3pm|reb|ast` (default `all` = minutes, then 3pm, then reb, then ast).
**Alternatives:** Separate `train-ast` command; keep ast behind a hidden flag until pts lands.
**Why:** Continues the phase-6 `--stat` pattern; keeps 3PM and reb paths working; allows fast ast iteration without refitting earlier models.
**Revisit if:** `all` becomes too slow once points components are added.
