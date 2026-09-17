# Results summary (all numbers produced by the code in this repository)

Sources: `results/fhlm/main_runs.csv` (200 runs), `main_summary.csv`,
`main_paired.csv`, `sweep_runs.csv` (60 runs), `tuning.json`,
`forecast_training_T20_d2.json`, figures in `results/fhlm/figures/`.
Configuration: 8 cells (3 low-latency, 5 eMBB) on a 25GE link, T = 20 slots
(10 ms), tau = 2 slots, 20,000 slots per run after 1,000 warm-up, 5 test seeds
(3000-3004) that were never used for training (1000-1015) or tuning
(2000-2003). Synthetic traffic.

## Hypothesis tested

> Under bursty and distribution-shifted traffic, allocating fronthaul budgets
> from a *quantile* forecast of each cell's deadline-feasible rate with the
> KKT (constrained newsvendor) rule reduces priority-weighted deadline
> violations compared with the same allocation driven by a point forecast and
> compared with a competent deadline-aware reactive controller, without an
> unacceptable utilisation or fairness penalty.

## Primary metric: priority-weighted deadline-violation ratio (%, mean ± std over 5 seeds)

| Method | low 0.50 | moderate 0.65 | high 0.80 | flash crowds | shift (held-out) |
|---|---|---|---|---|---|
| Static equal share | 4.16 ± 1.15 | 9.38 ± 1.77 | 15.27 ± 2.02 | 19.30 ± 2.07 | 23.65 ± 4.18 |
| Reactive proportional (EWMA) | 0.75 ± 0.34 | 3.81 ± 0.71 | 8.94 ± 1.15 | 12.25 ± 1.65 | 12.92 ± 3.47 |
| Deadline-aware reactive (persistence r*) | 0.39 ± 0.18 | 4.07 ± 0.95 | 10.86 ± 1.84 | 14.70 ± 2.67 | 14.21 ± 4.44 |
| Point forecast (GBM median) + water-fill | 0.18 ± 0.10 | 3.11 ± 0.87 | 9.63 ± 1.82 | 13.44 ± 2.65 | 12.93 ± 4.45 |
| Proposed rule with window quantiles (no ML) | 0.17 ± 0.04 | 2.41 ± 0.56 | 8.60 ± 1.74 | 12.67 ± 2.59 | 11.80 ± 4.56 |
| **Proposed (GBM quantiles + KKT)** | **0.08 ± 0.04** | **2.00 ± 0.59** | **7.89 ± 1.71** | **11.82 ± 2.56** | **11.59 ± 4.27** |
| Proposed + ACI calibration | 0.09 ± 0.02 | 2.02 ± 0.61 | 8.12 ± 1.80 | 12.24 ± 2.62 | 12.95 ± 5.17 |
| Oracle water-fill (true r*, not implementable) | 0.01 ± 0.01 | 1.56 ± 0.60 | 6.90 ± 1.68 | 10.21 ± 2.57 | 8.23 ± 4.14 |

The std across seeds is dominated by burst timing, which every method shares
seed by seed; the paired comparison below is the correct reading.

## Paired per-seed comparison (identical traces), relative reduction by the proposed method

| Baseline | low | moderate | high | flash crowds | shift |
|---|---|---|---|---|---|
| vs point forecast (same model, median only) | −53 % (5/5) | −36 % (5/5) | −18 % (5/5) | −12 % (5/5) | −10 % (5/5) |
| vs deadline-aware reactive | −79 % (5/5) | −51 % (5/5) | −27 % (5/5) | −20 % (5/5) | −18 % (5/5) |
| vs reactive proportional | −89 % (5/5) | −48 % (5/5) | −12 % (5/5) | −3 % (3/5) | −10 % (5/5) |
| vs proposed rule with window quantiles (ML ablation) | −51 % (5/5) | −17 % (5/5) | −8 % (5/5) | −7 % (5/5) | −2 % (4/5) |
| vs proposed + ACI calibration | −9 % (4/5) | −1 % (4/5) | −3 % (5/5) | −3 % (5/5) | −10 % (5/5) |

(x/5 = number of test seeds on which the proposed method had the lower metric.)

**Supported:** the hypothesis versus the point-forecast controller and versus
the deadline-aware reactive controller, in every scenario including the
held-out shift, on every seed.

**Not supported / weak:** versus the deadline-unaware proportional controller
under flash crowds (3/5 seeds, −3 %): there the LL cells are starved by the
proportional controller (17.6 % LL violations vs 4.3 %) but the eMBB class is
served so much better that the *weighted* metric is a tie. ACI calibration
does not help (see below).

## Where the gain comes from (scenario high)

| Method | LL violation | eMBB violation | utilisation | unused allocation | mean DU queueing delay | min cell service ratio |
|---|---|---|---|---|---|---|
| Reactive proportional | 14.6 % | 3.5 % | 74.7 % | 25.3 % | 3.15 ms | 0.847 |
| Deadline-aware reactive | 5.0 % | 16.4 % | 69.2 % | 30.8 % | 4.34 ms | 0.798 |
| Point forecast | 3.0 % | 15.9 % | 70.0 % | 30.0 % | 4.22 ms | 0.802 |
| Proposed | 3.2 % | 12.3 % | 72.0 % | 28.0 % | 4.22 ms | 0.845 |
| Oracle water-fill | 0.03 % | 13.4 % | 72.1 % | 27.9 % | 3.69 ms | 0.831 |

* Deadline-unaware allocation sacrifices the LL cells (14.6 %); every
  deadline-aware controller protects them at the price of eMBB.
* Inside the deadline-aware family the proposed rule has the **lowest eMBB
  loss and the highest utilisation**: it reserves margin above the median
  only where the forecast is wide (bursty LL cells at burst onset) and lets
  confident cells sit at their median, so less capacity is idle.
* Jain's index of per-cell service ratio is > 0.99 for every method (not a
  differentiator). p99 DU queueing delay is pinned at the eMBB deadline
  (10 ms) for all methods at these loads and is therefore uninformative here.
* Absolute violation levels are high because the traffic is deliberately
  heavy-tailed (Pareto ON/OFF, alpha_on = 1.5) at 0.8 mean load and budgets
  are held for 10 ms: even the oracle water-fill loses 13 % of eMBB bits.

## Ablations

1. **Point vs quantile forecast (same model, same rule family):** −10 % to
   −53 % weighted violations, 5/5 seeds in every scenario. This is the direct
   test of the "represent uncertainty" claim.
2. **ML vs non-ML quantiles under the same KKT rule:** the GBM adds −7 % to
   −51 % in the nominal traffic family but only −2 % (4/5 seeds) under the
   held-out shift, where it is out of distribution. Most of the gain over
   the baselines comes from the *rule* (deadline-feasible target + KKT split),
   not from the learned model. The window-quantile variant is the natural
   robust fallback.
3. **Online ACI calibration:** no gain — the calibrated variant is 1-9 %
   worse in the nominal family and 10 % worse under the held-out shift.
   Mechanism: the per-cell level
   offsets raise the LL quantile levels after the LL misses that the
   *coupled* shortage split necessarily produces, so the LL cells over-reserve
   and eMBB is starved (LL 5.4 % vs 7.6 %, eMBB 19.8 % vs 15.2 % under shift).
   Per-stream conformal correction does not transfer directly to a coupled
   allocation; this is reported as a negative result.
4. **Control interval sweep (scenario high, 3 seeds, forecasters retrained
   per T):**

   | T | proposed vs deadline-aware reactive | vs reactive proportional | vs oracle water-fill |
   |---|---|---|---|
   | 4 slots (2 ms) | −62 % | −27 % | −57 % |
   | 10 slots (5 ms) | −52 % | −37 % | −13 % |
   | 20 slots (10 ms) | −30 % | −18 % | +17 % |
   | 40 slots (20 ms) | −17 % | +12 % | +25 % |

   * At short intervals the KKT rule beats even the oracle-informed
     water-fill (perfect point forecast, proportional shortage split): the
     allocation rule, not only the forecast, carries the gain. Consequently
     the "oracle" is a reference for the forecast, **not** a bound.
   * At T = 40 slots (budgets held 5x the LL deadline) every deadline-aware
     controller over-reserves the LL peak rate and the deadline-unaware
     proportional controller wins on the weighted metric. Interval-level
     reservation of a deadline-feasible rate stops making sense when the
     interval is much longer than the deadline; this bounds the regime in
     which the proposed method should be used.

## Forecast quality (validation seeds, T = 20)

Empirical coverage at nominal 5/25/50/75/90/95 %: 5.6/25.6/50.7/75.3/89.9/94.9 %
(well calibrated). Median relative MAE: GBM 37 %, window median 49 %,
persistence 52 %. Mean pinball loss 0.0224 (GBM) vs 0.0293 (window quantiles).
Training: 101k rows, 12 s CPU. Note: scikit-learn's default early stopping
uses an internal 10 % split of the *training* rows (no validation/test data).

## Tuning (validation seeds 2000-2003, scenarios moderate/high)

Selected: reactive_prop margin 0, EWMA window 20; queue_aware margin 0,
1 horizon; point_forecast margin 0; proposed_cal gamma 0.005. Every positive
safety margin was worse on validation: inflating a point estimate hurts when
the shortage is split proportionally, because over-claiming cells receive
more. Longer persistence windows (3, 6 horizons) were also worse (r* over a
long window becomes a peak-rate estimate).

## Decision overhead (Python, 4-core CPU, per 10-ms control epoch)

static 0.02 ms, reactive proportional 0.03 ms, deadline-aware reactive
0.08 ms, oracle 0.08 ms, point forecast 2.3 ms, proposed 3.2 ms (window
quantiles 2.1 ms). The KKT rule itself is < 0.1 ms; the cost is feature
construction and evaluating 6 x 300 trees (vectorised numpy traversal).

## What we do NOT claim

* No real-world validation (synthetic traffic).
* No statistical-significance claim (5 seeds; win counts reported instead).
* No optimality or stability claim for the closed loop; the propositions in
  `method.md` are feasibility, equal weighted tail probability, and
  backlog-first.
* No universal superiority: ties with reactive proportional under flash
  crowds, loses to it at T = 40 slots, and the ML component adds little under
  the held-out shift.
