# Extended study: theory, Markov traffic, model-based and predictive controllers

This document describes what was added on top of the NCC 2027 submission
(`paper/main.tex`) to turn the conference result into a journal-length study
(`paper/extended/main.tex`). Every number quoted in the extended manuscript is a
macro generated from `results/fhlm/*.csv` and `results/fhlm/*.json` by
`fhlm/make_extended_tables.py`; the numbers in `docs/fhlm/extended_results.md`
are copied from the same files.

## 1. Why extend

The conference paper compared twelve controllers and found the learned-quantile
KKT rule best in every scenario of two traffic families. Three questions remained
open and are the subject of the extension:

1. What is the real control problem, and what does the one-step newsvendor rule
   approximate? (Sec. III-B of the extended paper: a finite-horizon POMDP on
   deadline-constrained queues; three tractable approximation families.)
2. What can be proved about the deadline-feasible rate r* when the traffic has a
   known stochastic structure? (Sec. V: Markov-fluid theory.)
3. Do model-based (Markov) or model-free (policy search, predictive
   back-pressure) alternatives beat the learned rule, and when? (Secs. VI-IX.)

## 2. New code

| File | Purpose |
|---|---|
| `fhlm/traffic_markov.py` | Family M: Markov-modulated Gamma sources, 3 hidden phases (idle/normal/burst), geometric sojourns; `mm_shift` uses Pareto(1.5) sojourns (semi-Markov, misspecifies every Markov model). Scaled to the target stationary load; burst phase below the cell air-interface peak. |
| `fhlm/theory.py` | Window log-MGF of the Markov-additive process, effective bandwidth `alpha(theta) = log rho(P Phi(theta)) / theta`, Chernoff-union tail bound `U(x)` on `P(r* > x)`, Doob/supermartingale bound, quantiles implied by the bound, fluid drop simulation and the shortfall sandwich `(D+1)(r*-r)^+ <= drops <= sum (a_t-r)^+`. The module docstring states and proves the propositions. |
| `fhlm/theory_validation.py` | Validates the bounds and the sandwich on Family M (`results/fhlm/theory_validation.json`, `results/fhlm/figures/paper_fig_theory.*`). |
| `fhlm/markov.py` | `fit_phase_chain` (K-phase quantisation + Dirichlet-smoothed transition estimate), `MarkovChainForecaster` (fitted chain, Monte Carlo quantiles of r* from the current phase), `ChernoffBoundForecaster` (quantiles of the bound), `MarkovOracleForecaster` (true generator + HMM forward filter; Family M reference). All expose the forecaster interface used by the KKT allocator. |
| `fhlm/controllers_ext.py` | `PredictiveMaxWeight` (Huang et al. 2016 predictive back-pressure: queue weight = queue + look-ahead x forecast median), `ClassLevelPolicy` (per-class quantile levels + learned LL weight) and `cem_search` (cross-entropy method). |
| `fhlm/demand.py` | `critical_window_lengths`, `sustainable_rates = max(r*, mean)`. |
| `fhlm/proposed.py` | Optional `volume_weights` (w_i x min(D_i + mean critical window, T)) and `queue_weights` (drift blend); both are negative results. |
| `fhlm/forecast.py`, `fhlm/train.py` | `--target sustain` trains a forecaster for the sustainable rate (negative result; models git-ignored). |
| `fhlm/run_experiments.py` | New method names (`pred_maxweight`, `cem_policy`, `eb_kkt`, `markov_kkt`, `markov_oracle_kkt`, `proposed_vc`, `*_sus`), `--family markov`, the `cem` command, `--append` on every sweep, tuning that merges new methods into an existing `tuning*.json`. |
| `fhlm/make_extended_tables.py`, `fhlm/make_figures.py` | Tables/macros for `paper/extended/`, the three-family overview figure and the regime figure. The NCC tables and figures are pinned to the original twelve controllers so the submitted PDF does not change. |
| `tests/test_fhlm_extended.py` | 13 tests: phase matrix and stationary law, Family M load and reproducibility, semi-Markov shift, Gamma MGF vs Monte Carlo, i.i.d. window MGF, effective-bandwidth monotonicity, validity of the tail bounds, the sandwich, critical window / sustainable rate, chain recovery, forecaster monotonicity and calibration, feasibility of the new controllers, CEM on a quadratic. |
| `experiments/run_extended.sh` | The whole extended pipeline (tuning, CEM, main runs, sweeps, theory validation), idempotent and append-only. |

## 3. Theory in one page

Setting: one cell, fronthaul demand `d_t` is Markov-modulated with phase chain
`P` (stationary law `pi`) and per-phase log-MGF `psi_k(theta)`; horizon `H`
slots, deadline `D`.

* Window log-MGF: `Lambda_l(theta) = log(pi^T Phi (P Phi)^{l-1} 1)`,
  `Phi = diag(exp psi_k)`.
* Effective bandwidth: `alpha(theta) = log rho(P Phi(theta)) / theta`, from the
  mean rate (theta -> 0) to the peak phase rate.
* Proposition (Chernoff-union bound): `P(r* > x) <= sum_{l=1}^{H} (H-l+1) min_theta exp(-theta x (l+D) + Lambda_l(theta)) =: U(x)`.
* Corollary (large-deadline decay): `limsup_D (1/D) log P(r* > x) <= -x theta*(x)`
  with `theta*(x) = sup{theta: alpha(theta) <= x}`; the effective-bandwidth decay
  rate of the fluid queue served at rate `x` at buffer level `x D`.
* Remark (Doob bound): removes the window count but pays a Perron prefactor that
  makes it vacuous for `D <= 20` with the Family M phase matrices.
* Proposition (shortfall sandwich), pathwise, any arrival process:
  `(D+1)(r*-r)^+ <= V(r) <= sum_t (a_t-r)^+`, `V(r)` the volume dropped at the
  deadline when serving at constant rate `r`. Hence the newsvendor objective of the
  KKT rule is (up to the factor `D_i+1`) a lower bound on the expected weighted
  violated volume, and the lower bound really carries `l*+D` (critical window
  length plus deadline), which motivated the volume-corrected variant.

Numerical validation (Family M, load 0.80, 20 000 horizons): sandwich never
violated; the union bound is valid everywhere but 25-100x conservative at tail
probabilities 1e-2 to 1e-3 for D = 4 and D = 20. That looseness is intrinsic
(union over O(H^2) windows plus the Perron prefactor) and is the quantitative
argument for learning the predictive distribution from the recent sample path
instead of bounding it from the stationary law.

## 4. New controllers

* `pred_maxweight`: MaxWeight whose priority is `w_i (Q_i + lookahead x H x median forecast of r*_i)`,
  share capped at `Q_i/T + (1+margin) x median`; no deadlines, one number of the forecast.
* `markov_kkt`: KKT rule with quantiles from a 3-phase chain fitted to the last 0.5-1.5 s of each cell.
* `eb_kkt`: KKT rule with quantiles implied by the Chernoff-union bound of the fitted chain.
* `markov_oracle_kkt` (Family M only, reference): KKT rule with the true chain and an HMM filter for the phase.
* `cem_policy`: `B_i + F_i^{-1}(p_class)` with weighted water-filling, the three parameters learned by CEM on training seeds (model-free, reward-driven; the small-parameter analogue of a DRL xApp).
* `proposed_vc`, `proposed_dw`, `proposed_sus`, `point_forecast_sus`: variants of the proposed rule motivated by the theory; all negative results, kept in the code and reported.

## 5. How to reproduce

```bash
python3 -m pytest tests/test_fhlm.py tests/test_fhlm_extended.py -q
python3 -m fhlm.train --family markov --out models/fhlm_quantile_gbm_T20_d2_markov.pkl \
        --report results/fhlm/forecast_training_T20_d2_markov.json
bash experiments/run_extended.sh                 # tuning, CEM, main runs, sweeps, theory validation (about 2 h on 4 cores)
python3 -m fhlm.make_figures
python3 -m fhlm.make_extended_tables && (cd paper/extended && pdflatex main && pdflatex main)
```

The NCC manuscript is regenerated by `python3 -m fhlm.make_paper_tables`; it
reads the same CSVs but restricts them to the original twelve controllers.
