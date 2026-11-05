# Extended study: theory, Markov traffic, model-based and predictive controllers

This document describes what was added on top of the NCC 2027 submission
(`paper/main.tex`) to turn the conference result into a journal-length study
(`paper/extended/main.tex`). Every number quoted in the extended manuscript is a
macro generated from `results/fhlm/*.csv` and `results/fhlm/*.json` by
`fhlm/make_extended_tables.py`; Sec. 6 below copies the headline numbers from
the same files.

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
| `fhlm/proposed.py` | Optional `volume_weights` (w_i x min(D_i + mean critical window, T)) and `queue_weights` (drift blend), both negative results; optional `ll_weight` (the internal newsvendor weight of the 2-ms class, tuned on validation seeds, `proposed_tw`); `last_lambda` records the KKT multiplier of the last decision for diagnostics. |
| `fhlm/lambda_diagnostic.py` | Records lambda* of the KKT rule over 3 test seeds x 8000 slots on the high-load scenario of each family (`results/fhlm/lambda_diagnostic.json`): fraction of binding epochs, fraction in which lambda* >= w_eMBB (every eMBB cell at its lowest quantile plus slack), LL quantile level at the median lambda*. This is the measurement behind the "saturation" explanation of Sec. 6. |
| `fhlm/forecast.py`, `fhlm/train.py` | `--target sustain` trains a forecaster for the sustainable rate (negative result; models git-ignored). |
| `fhlm/run_experiments.py` | New method names (`pred_maxweight`, `cem_policy`, `eb_kkt`, `markov_kkt`, `markov_oracle_kkt`, `proposed_vc`, `proposed_tw`, `*_sus`), `--family markov`, the `cem` command, `--append` on every sweep, tuning that merges new methods into an existing `tuning*.json`. |
| `fhlm/make_extended_tables.py`, `fhlm/make_figures.py` | Tables/macros for `paper/extended/`, the three-family overview figure and the regime figure. The NCC tables and figures are pinned to the original twelve controllers so the submitted PDF does not change. |
| `tests/test_fhlm_extended.py` | 14 tests: phase matrix and stationary law, Family M load and reproducibility, semi-Markov shift, Gamma MGF vs Monte Carlo, i.i.d. window MGF, effective-bandwidth monotonicity, validity of the tail bounds, the sandwich, critical window / sustainable rate, chain recovery, forecaster monotonicity and calibration, feasibility of the new controllers, CEM on a quadratic, `ll_weight = w_LL` reduces to the plain rule. |
| `experiments/run_extended.sh`, `experiments/run_extended_2.sh` | The whole extended pipeline (tuning, CEM, main runs, sweeps, theory validation; the second script adds `proposed_tw` and the sweeps of the CEM policy), idempotent and append-only. Logs in `results/fhlm/ext_*.log`, `ext2_*.log`. |

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
* `proposed_tw`: the KKT rule unchanged except that the newsvendor weight of the 2-ms class inside the rule is one scalar in {0.75, 1, 1.5, 2, 3, 4} chosen on validation seeds (S: 2, G: 2, M: 4); the metric keeps the operator weight 3. Tests whether the gap to the learned policies is "wrong constant" or "wrong structure".
* `proposed_vc`, `proposed_dw`, `proposed_sus`, `point_forecast_sus`: variants of the proposed rule motivated by the theory; all negative results, kept in the code and reported.

## 5. How to reproduce

```bash
python3 -m pytest tests/test_fhlm.py tests/test_fhlm_extended.py -q
python3 -m fhlm.train --family markov --out models/fhlm_quantile_gbm_T20_d2_markov.pkl \
        --report results/fhlm/forecast_training_T20_d2_markov.json
bash experiments/run_extended.sh                 # tuning, CEM, main runs, sweeps, theory validation (about 2 h on 4 cores)
bash experiments/run_extended_2.sh               # proposed_tw everywhere, CEM sweeps (about 1 h)
python3 -m fhlm.lambda_diagnostic                # KKT multiplier statistics (a few minutes)
python3 -m fhlm.make_figures
python3 -m fhlm.make_extended_tables && (cd paper/extended && pdflatex main && pdflatex main)
```

The NCC manuscript is regenerated by `python3 -m fhlm.make_paper_tables`; it
reads the same CSVs but restricts them to the original twelve controllers.

## 6. Results in brief (test seeds, V_w in %, lower is better)

| Scenario | GBM + KKT (NCC rule) | Predictive MaxWeight | Policy search (CEM) | Markov-chain KKT | Tuned-weight KKT | Best implementable |
|---|---|---|---|---|---|---|
| S low 0.50 | 0.15 | 0.14 | 0.13 | 0.25 | 0.18 | CEM |
| S moderate 0.65 | 2.15 | 1.62 | 1.77 | 2.65 | 2.21 | predictive MaxWeight |
| S high 0.80 | 8.00 | 6.15 | 6.57 | 8.64 | 7.88 | predictive MaxWeight |
| S flash crowd | 11.76 | 9.69 | 10.20 | 12.44 | 11.49 | predictive MaxWeight |
| S shift | 10.04 | 10.25 | 9.73 | 10.22 | 9.90 | CEM |
| G moderate 0.65 | 5.08 | 7.57 | 4.58 | 6.44 | 4.98 | CEM |
| G high 0.80 | 8.01 | 11.36 | 7.17 | 8.77 | 7.83 | CEM |
| M moderate 0.65 | 0.92 | 1.64 | 0.88 | 1.24 | 0.85 | tuned-weight KKT |
| M high 0.80 | 4.94 | 4.79 | 3.93 | 5.12 | 4.88 | CEM |
| M shift 0.80 | 5.52 | 4.80 | 4.17 | 5.39 | 5.31 | CEM |

(Exact values with standard deviations, paired changes, Holm-corrected p-values
and seed-win counts are in `paper/extended/generated/tab_main_*.tex` and
`tab_head_to_head.tex`; the tuned-weight column is from
`results/fhlm/main_summary.csv`.)

What this says, honestly:

1. Within the twelve controllers of the NCC paper the learned-quantile KKT rule is
   still best in all ten scenarios, including the new Markov family; it is the best
   controller with no tuned parameter.
2. Two controllers that use the *same* forecaster beat it. The CEM policy (three
   reward-learned parameters: p_LL about 0.8, p_eMBB about 0.5, w_LL about 1) is the
   best implementable controller in 6/10 scenarios, predictive MaxWeight (forecast
   median plus queues, no deadline model) in 3/10, all on the bursty synthetic
   family, and the tuned-weight KKT rule in 1/10.
3. Re-tuning the LL weight inside the KKT rule is **not** enough: 8.00 -> 7.88 (S),
   8.01 -> 7.83 (G), 4.94 -> 4.88 (M) at high load, one order of magnitude less than
   the CEM gain. `lambda_diagnostic.json` shows why: the capacity constraint binds in
   ~100 % of high-load epochs and in 50-58 % of them lambda* >= w_eMBB, so every eMBB
   cell is already at its lowest quantile plus proportional slack; the weight has
   nothing left to move. The CEM gain comes from decoupled per-class levels and a
   different sharing rule, i.e. from the structure, not from the constant.
4. A Markov chain fitted online (no training data) is within 3 % (M) and 9 % (G) of
   the learned rule at high load and still 5.39 % vs 5.52 % under the semi-Markov
   shift; the true-model reference with an HMM filter gives 4.89 % (M high), the
   oracle 1.84 %. The Chernoff-bound rule is the worst deadline-aware controller
   everywhere (bounds 25-100x conservative at 2-10 ms deadlines).
5. Regime (S high, interval sweep): at T = 2 and 5 ms the reservation (KKT) beats
   predictive MaxWeight; at T = 10 and 20 ms, with bursts shorter than the interval,
   back-pressure wins; with long bursts (Family G files and XR frames) the
   reservation wins at every T.
6. Compression (moderate scenario, BFP 6/9/12/14 bits): the NCC conclusion holds for
   the new controllers; allocation matters between loads of about 0.5 and 0.8 and
   nothing helps at 0.99.
