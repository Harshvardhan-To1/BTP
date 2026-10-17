# Results summary (all numbers produced by the code in this repository)

Sources: `results/fhlm/main_runs.csv` (1000 synthetic-family runs + 100
oracle-KKT runs + 480 runs on the 3GPP family), `main_summary.csv`,
`main_paired.csv`, `main_paired_unweighted.csv`, `sweep_runs.csv` (240 runs),
`delay_runs.csv` (160 runs), `miscalibration_runs.csv` (180 runs),
`compression_runs.csv` (160 runs), `weights_runs.csv` (1120 runs),
`tuning.json`, `tuning_3gpp.json`, `forecast_training_T20_d2.json`,
`forecast_training_T20_d2_3gpp.json`, figures in
`results/fhlm/figures/`. The same CSVs feed the paper tables and macros in
`paper/generated/` (via `python -m fhlm.make_paper_tables`), so the paper and
this file cannot drift apart from the data. Part A numbers come from
`results/benchmark_results.csv` and the earlier report
`docs/mid_evaluation_report.md`.

Configuration: 8 cells (3 low-latency, 5 eMBB) on a 25GE link, T = 20 slots
(10 ms), tau = 2 slots, 20,000 slots per run after 1,000 warm-up, 20 test seeds
(3000-3019) that were never used for training (1000-1015) or tuning
(2000-2003). Two traffic families: "Family S" (synthetic, hand-designed,
bursty; scenarios low / moderate / high / flash crowds / shift) and "Family G"
(standards-based 3GPP models; scenarios tgpp_moderate / tgpp_high), each with
its own forecaster and its own tuning.

## Hypothesis tested

> Under bursty and distribution-shifted traffic, allocating fronthaul budgets
> from a *quantile* forecast of each cell's deadline-feasible rate with the
> KKT (constrained newsvendor) rule reduces priority-weighted deadline
> violations compared with the same allocation driven by a point forecast,
> compared with a tuned global-quantile reservation, and compared with
> competent queue-based and deadline-aware reactive controllers, without an
> unacceptable utilisation or fairness penalty.

## Primary metric: priority-weighted deadline-violation ratio (%, mean ± std over 20 seeds)

| Method | low 0.50 | moderate 0.65 | high 0.80 | flash crowds | shift (held-out) |
|---|---|---|---|---|---|
| Static equal share | 4.45 ± 1.05 | 9.65 ± 1.36 | 15.46 ± 1.51 | 19.15 ± 2.34 | 22.31 ± 2.99 |
| Reactive proportional (EWMA) | 0.83 ± 0.27 | 4.11 ± 0.69 | 9.20 ± 0.99 | 12.27 ± 2.23 | 11.70 ± 2.24 |
| MaxWeight (priority × queue, HOL-age urgency) | 0.90 ± 0.28 | 4.85 ± 0.79 | 11.54 ± 1.27 | 15.24 ± 3.02 | 12.31 ± 2.44 |
| Deadline-aware reactive (persistence r*) | 0.52 ± 0.21 | 4.24 ± 0.78 | 11.03 ± 1.33 | 14.51 ± 3.06 | 12.56 ± 2.81 |
| Point forecast (GBM median) + water-fill | 0.27 ± 0.17 | 3.23 ± 0.73 | 9.70 ± 1.34 | 13.33 ± 3.09 | 11.30 ± 2.81 |
| Fixed global quantile (tuned level 0.75) + water-fill | 0.34 ± 0.23 | 4.35 ± 1.02 | 11.76 ± 1.44 | 15.09 ± 3.17 | 12.85 ± 3.32 |
| Proposed rule with window quantiles (no ML) | 0.25 ± 0.13 | 2.57 ± 0.64 | 8.72 ± 1.34 | 12.67 ± 3.19 | 10.22 ± 2.88 |
| **Proposed (GBM quantiles + KKT)** | **0.15 ± 0.13** | **2.15 ± 0.60** | **8.00 ± 1.27** | **11.76 ± 3.08** | **10.04 ± 2.71** |
| Proposed + ACI calibration | 0.17 ± 0.13 | 2.17 ± 0.61 | 8.14 ± 1.30 | 12.27 ± 3.26 | 11.12 ± 3.22 |
| Oracle water-fill (true r*, not implementable) | 0.07 ± 0.10 | 1.62 ± 0.56 | 6.89 ± 1.28 | 10.16 ± 2.96 | 6.69 ± 2.60 |

The std across seeds is dominated by burst timing, which every method shares
seed by seed; the paired comparison below is the correct reading.

## Paired per-seed comparison (identical traces), relative reduction by the proposed method

Format: mean relative reduction [95 % percentile-bootstrap CI] seeds won / 20;
`**` Holm-corrected two-sided Wilcoxon signed-rank p < 0.01, `*` p < 0.05
(Holm correction across the baselines of each scenario).

| Baseline | low | moderate | high | flash crowds | shift |
|---|---|---|---|---|---|
| vs reactive proportional | −81 % [−87, −75] 20/20 ** | −48 % [−52, −44] 20/20 ** | −13 % [−16, −11] 20/20 ** | −4 % [−8, −1] 16/20 * | −14 % [−17, −11] 20/20 ** |
| vs MaxWeight | −83 % [−88, −77] 20/20 ** | −56 % [−59, −52] 20/20 ** | −31 % [−33, −29] 20/20 ** | −23 % [−25, −20] 20/20 ** | −18 % [−21, −16] 20/20 ** |
| vs deadline-aware reactive | −70 % [−77, −62] 20/20 ** | −49 % [−52, −47] 20/20 ** | −27 % [−29, −26] 20/20 ** | −19 % [−21, −17] 20/20 ** | −20 % [−22, −18] 20/20 ** |
| vs point forecast (same model, median only) | −43 % [−52, −33] 20/20 ** | −33 % [−36, −31] 20/20 ** | −18 % [−19, −17] 20/20 ** | −12 % [−13, −10] 20/20 ** | −11 % [−12, −10] 20/20 ** |
| vs fixed global quantile | −54 % [−63, −44] 20/20 ** | −50 % [−52, −48] 20/20 ** | −32 % [−33, −31] 20/20 ** | −22 % [−24, −20] 20/20 ** | −22 % [−23, −21] 20/20 ** |
| vs proposed rule with window quantiles (ML ablation) | −37 % [−47, −29] 20/20 ** | −16 % [−18, −15] 20/20 ** | −8 % [−9, −8] 20/20 ** | −7 % [−8, −7] 20/20 ** | −2 % [−3, −1] 16/20 ** |
| vs proposed + ACI calibration | −9 % [−15, −5] 18/20 ** | −1 % [−1, −0] 16/20 ** | −2 % [−2, −1] 19/20 ** | −4 % [−5, −3] 20/20 ** | −10 % [−11, −9] 20/20 ** |

**Supported:** the hypothesis versus the point-forecast controller, the
fixed-quantile controller, the MaxWeight controller and the deadline-aware
reactive controller, in every scenario including the held-out shift, on
every seed, with Holm-corrected p < 0.01.

**Weak:** versus the deadline-unaware proportional controller under flash
crowds (−4 %, 16/20 seeds, p = 0.03): there the proportional controller
starves the LL cells (17.8 % LL violations vs 4.6 % for the proposed rule) but
serves eMBB so much better (7.1 % vs 18.3 %) that the *weighted* metric moves
little. ACI calibration does not help (see below).

## Where the gain comes from (scenario high, 20 seeds)

| Method | LL violation | eMBB violation | utilisation | unused allocation | mean DU queueing delay | min cell service ratio | Jain (service ratio) |
|---|---|---|---|---|---|---|---|
| Reactive proportional | 14.7 % | 4.0 % | 74.7 % | 25.3 % | 3.10 ms | 0.845 | 0.996 |
| MaxWeight | 20.6 % | 2.9 % | 74.1 % | 25.9 % | 3.23 ms | 0.786 | 0.991 |
| Deadline-aware reactive | 5.2 % | 16.5 % | 69.3 % | 30.7 % | 4.37 ms | 0.783 | 0.995 |
| Point forecast | 3.1 % | 16.0 % | 70.1 % | 29.9 % | 4.23 ms | 0.787 | 0.994 |
| Fixed global quantile | 0.9 % | 22.0 % | 67.0 % | 33.0 % | 4.53 ms | 0.721 | 0.985 |
| Proposed | 3.4 % | 12.3 % | 72.2 % | 27.8 % | 4.21 ms | 0.829 | 0.997 |
| Oracle water-fill | 0.04 % | 13.4 % | 72.3 % | 27.7 % | 3.69 ms | 0.816 | 0.994 |

* Deadline-unaware allocation sacrifices the LL cells (14.7 % proportional,
  20.6 % MaxWeight: large queues are not the same as urgent queues); every
  deadline-aware controller protects them at the price of eMBB.
* Inside the deadline-aware family the proposed rule has the **lowest eMBB
  loss and the highest utilisation**: it reserves margin above the median
  only where the forecast is wide (bursty LL cells at burst onset) and lets
  confident cells sit at their median, so less capacity is idle.
* The fixed global quantile shows the opposite failure: one level (0.75) for
  every cell over-protects the LL cells (0.9 %) and wastes 33 % of the
  allocation, giving the worst eMBB loss. The per-cell level chosen by the
  KKT rule is what matters, not merely "using a quantile".
* Jain's index of per-cell service ratio is > 0.98 for every method (not a
  differentiator). p99 DU queueing delay is pinned at the eMBB deadline
  (10 ms) for all methods at these loads and is therefore uninformative here.
* Absolute violation levels are high because the traffic is deliberately
  heavy-tailed (Pareto ON/OFF, alpha_on = 1.5) at 0.8 mean load and budgets
  are held for 10 ms: even the oracle water-fill loses 13 % of eMBB bits.

## Ablations

1. **Point vs quantile forecast (same model, same rule family):** −11 % to
   −43 % weighted violations, 20/20 seeds in every scenario, p < 0.01. This
   is the direct test of the "represent uncertainty" claim.
2. **Per-cell KKT level vs one tuned global level (same forecast):** −22 % to
   −54 %, 20/20 seeds everywhere. Using the whole forecast distribution is not
   enough; the level has to be chosen per cell by the link constraint.
3. **ML vs non-ML quantiles under the same KKT rule:** the GBM adds −7 % to
   −37 % in the nominal traffic family but only −2 % (16/20 seeds, p = 0.002)
   under the held-out shift, where it is out of distribution. Most of the
   gain over the baselines comes from the *rule* (deadline-feasible target +
   KKT split), not from the learned model. The window-quantile variant is the
   natural robust fallback.
4. **Online ACI calibration:** no gain; the calibrated variant is 1-9 %
   worse in the nominal family and 10 % worse under the held-out shift.
   Mechanism: the per-cell level offsets raise the LL quantile levels after
   the LL misses that the *coupled* shortage split necessarily produces, so
   the LL cells over-reserve and eMBB is starved (LL 4.7 % vs 6.7 %, eMBB
   17.2 % vs 13.2 % under shift). Per-stream conformal correction does not
   transfer directly to a coupled allocation; reported as a negative result.

## Family G: standards-based traffic (3GPP channel + traffic models)

Nothing in this family is hand-designed. Users are dropped in a 3GPP TR 38.901
urban-macro cell (ISD 500 m, 3.5 GHz, 100 MHz, 49 dBm; LOS probability,
LOS/NLOS path loss and shadow fading per the spec), attach to the strongest of
7 fully loaded sites (the other 6 interfere), see Jakes-correlated Rayleigh
fading at 3 km/h per slot, and get a spectral efficiency from the TR 36.942
attenuated-Shannon bound quantised to the TS 38.214 CQI table. eMBB cells carry
FTP Model 3 (TR 36.814: Poisson 0.5-MByte files, 20 UEs); low-latency cells
carry XR video (TR 38.838: 60 fps, 30 Mbit/s, truncated-Gaussian frame size and
jitter). A per-cell round-robin PRB scheduler serves the UEs and the fronthaul
demand of a cell per slot is the number of PRB-layers it schedules x BFP bits
per PRB-layer. Only the number of XR UEs per LL cell and the FTP arrival rate
are calibrated (to the target mean load, within 1 %). Code:
`fhlm/traffic_3gpp.py`; traces are cached in `results/fhlm/trace_cache/`.

Weighted violation ratio (%, mean ± std over 20 test seeds) and class
breakdown at load 0.80 (`main_runs.csv`, scenarios `tgpp_*`):

| Method | tgpp_moderate 0.65 | tgpp_high 0.80 | LL (high) | eMBB (high) | unweighted (high) | util. (high) |
|---|---|---|---|---|---|---|
| static_equal | 10.75 ± 1.71 | 13.10 ± 2.13 | 6.6 | 30.8 | 19.2 | 43.6 |
| reactive_prop | 12.05 ± 2.18 | 15.94 ± 1.93 | 17.0 | 13.4 | 15.0 | 61.3 |
| maxweight | 17.51 ± 2.21 | 25.79 ± 2.15 | 32.2 | 8.3 | 19.7 | 64.6 |
| queue_aware | 8.95 ± 2.04 | 11.53 ± 1.67 | 4.2 | 31.7 | 18.5 | 53.0 |
| point_forecast | 6.00 ± 0.94 | 8.98 ± 1.09 | 1.0 | 31.1 | 16.6 | 54.4 |
| fixed_quantile | 6.80 ± 1.15 | 9.88 ± 1.24 | 0.6 | 35.5 | 18.7 | 51.8 |
| proposed_window | 6.18 ± 0.99 | 9.01 ± 1.04 | 1.6 | 29.5 | 16.0 | 56.1 |
| **proposed** | **5.08 ± 0.84** | **8.01 ± 0.99** | 1.3 | 26.6 | 14.4 | 57.8 |
| proposed_cal | 5.41 ± 0.87 | 8.27 ± 0.98 | 1.1 | 28.1 | 15.1 | 57.3 |
| proposed_transfer (forecaster trained on Family S) | 6.99 ± 1.29 | 9.89 ± 1.18 | 5.3 | 22.7 | 14.3 | 58.5 |
| oracle water-fill | 4.82 ± 0.76 | 7.85 ± 1.06 | 0.2 | 28.9 | 15.1 | 55.2 |
| oracle + KKT rule | 3.47 ± 0.57 | 6.06 ± 0.83 | 0.7 | 20.9 | 11.1 | 59.8 |

Paired comparison at tgpp_high (relative change of the weighted ratio when
switching from the row controller to the proposed rule; negative = proposed
better; 95 % bootstrap CI; seeds won by the proposed rule; Holm-corrected
Wilcoxon p):

| Proposed vs | change % [95 % CI] | wins | Holm p |
|---|---|---|---|
| static_equal | -39 [-42, -36] | 20/20 | < 0.001 |
| reactive_prop | -50 [-52, -47] | 20/20 | < 0.001 |
| maxweight | -69 [-71, -67] | 20/20 | < 0.001 |
| queue_aware | -31 [-33, -28] | 20/20 | < 0.001 |
| point_forecast | -11 [-12, -10] | 20/20 | < 0.001 |
| fixed_quantile | -19 [-20, -18] | 20/20 | < 0.001 |
| proposed_window | -11 [-12, -10] | 20/20 | < 0.001 |
| proposed_cal | -3 [-4, -2] | 19/20 | < 0.001 |
| proposed_transfer | -19 [-22, -16] | 20/20 | < 0.001 |
| oracle water-fill | +2 [0, +4] | 5/20 | 0.027 |
| oracle + KKT rule | +32 [+31, +34] | 0/20 | < 0.001 |

Reading: the main result reproduces on traffic that we did not design. The
traffic is hard in a different way (an FTP file is a burst at the full cell
rate; XR frames are periodic at 16.7 ms), so the eMBB class loses ~21 % of its
bits even with a perfect forecast under 10-ms budgets, and the
deadline-unaware controllers fall behind even static sharing. Here the proposed
rule is the best implementable controller also under the *unweighted* ratio.
The transferred forecaster (never saw a 3GPP trace) under-reserves the LL cells
and lands between the in-family point forecast and the deadline-aware reactive
controller: usable, but not better than an in-family point forecast.

Forecaster (`forecast_training_T20_d2_3gpp.json`): validation coverage
33.9 / 56.8 / 98.1 % at the 5 / 50 / 95 % quantiles (the 5 % figure is a point
mass at zero: in about a third of the horizons no file or frame arrives),
median relative error 24 % vs 39 % for persistence.

## Cost of forecast error: oracle + KKT rule

`oracle_kkt` is the proposed rule with a perfect (degenerate) forecast, i.e.
the priority-ordered fill of Proposition 2 using the true r* of the coming
horizon. The gap between `proposed` and `oracle_kkt` is what a better
forecaster could still buy; the rest is the cost of committing budgets for
10 ms.

| scenario | proposed | oracle + KKT | gap (% of proposed) |
|---|---|---|---|
| low | 0.15 | 0.05 | 70 |
| moderate | 2.15 | 0.88 | 59 |
| high | 8.00 | 4.77 | 40 |
| flash crowds | 11.76 | 8.10 | 31 |
| shift | 10.04 | 5.84 | 42 |
| tgpp_moderate | 5.08 | 3.47 | 32 |
| tgpp_high | 8.01 | 6.06 | 24 |

In the interval sweep the oracle + KKT rule reaches 1.91 % at T = 2 ms against
6.89 % for the oracle water-fill with the same perfect information: the
allocation rule, not only the forecast, carries the gain at short intervals.

## The objective matters: unweighted ratio and LL priority weight

Unweighted violation ratio (%, all bits count equally; `main_runs.csv`,
Family S, 20 seeds):

| Method | low | moderate | high | flash crowds | shift |
|---|---|---|---|---|---|
| static_equal | 5.96 | 11.95 | 18.16 | 21.76 | 23.82 |
| reactive_prop | 0.44 | **2.44** | **6.55** | **9.64** | 10.37 |
| maxweight | 0.48 | 2.73 | 7.18 | 10.44 | **10.26** |
| queue_aware | 0.40 | 4.69 | 13.81 | 18.39 | 13.50 |
| point_forecast | 0.26 | 3.93 | 12.88 | 17.62 | 12.96 |
| fixed_quantile | 0.43 | 6.14 | 16.96 | 21.31 | 16.58 |
| proposed_window | 0.19 | 2.85 | 11.12 | 16.55 | 12.18 |
| proposed (run with w_LL = 3) | **0.14** | 2.50 | 10.19 | 15.08 | 11.64 |
| proposed_cal | 0.15 | 2.52 | 10.65 | 16.33 | 14.19 |
| oracle water-fill | 0.10 | 2.39 | 10.17 | 14.73 | 9.44 |
| oracle + KKT rule | 0.07 | 1.29 | 7.02 | 11.70 | 8.17 |

So the gain of every deadline-aware controller is a priority trade: under the
unweighted ratio the plain proportional controller loses fewer total bits at
moderate and high load in Family S, because it sacrifices the small LL cells
(14.7 % of their bits at high load) to serve eMBB volume. Priority-weight
sweep (`weights_runs.csv`; every controller is told the new weight; parameters
stay those tuned at w_LL = 3; 20 seeds; weighted ratio in %):

| w_LL (Family S, high) | reactive_prop | maxweight | queue_aware | point_forecast | proposed | oracle | oracle_kkt |
|---|---|---|---|---|---|---|---|
| 1 (= unweighted) | **6.55** | 7.38 | 7.75 | 6.77 | 6.58 | 4.86 | 4.86 |
| 2 | **8.13** | 9.96 | 10.08 | 8.90 | 8.35 | 5.97 | 5.68 |
| 3 (default) | 9.20 | 11.54 | 11.03 | 9.70 | **8.00** | 6.89 | 4.77 |
| 5 | 10.56 | 13.38 | 11.69 | 10.57 | **6.93** | 8.29 | 3.63 |

| w_LL (Family G, tgpp_high) | reactive_prop | maxweight | queue_aware | point_forecast | proposed | oracle | oracle_kkt |
|---|---|---|---|---|---|---|---|
| 1 (= unweighted) | 15.01 | 19.77 | 13.19 | **10.43** | 15.92 | 8.78 | 8.78 |
| 2 | 15.62 | 23.92 | 12.50 | **9.74** | **9.74** | 8.31 | 7.78 |
| 3 (default) | 15.94 | 25.79 | 11.53 | 8.98 | **8.01** | 7.85 | 6.06 |
| 5 | 16.27 | 27.29 | 9.99 | 7.61 | **5.90** | 6.76 | 4.31 |

Reading: in Family S the rule, told w_LL = 1, matches proportional sharing and
pulls ahead from w_LL = 3. In Family G at w_LL = 1 it is clearly *worse* than
the point-forecast water-fill (15.9 vs 10.4 %): XR and FTP demand is
zero-inflated (often no frame / no file in a horizon), and at a low common
critical fractile the newsvendor solution reserves nothing beyond backlog for
many cells, an all-or-nothing allocation that the median water-fill avoids; the
LL cells then lose 21 % of their bits. The method is for operators who value a
low-latency bit at least 2-3x an eMBB bit; without that premise the simpler
controllers are at least as good. With a perfect forecast (oracle + KKT) the
rule would win at every weight, so the loss at low weights is forecast error.

## Sensitivity studies (scenario high, 10 seeds each, forecasters retrained per setting)

**Control interval T** (`sweep_runs.csv`), weighted violation ratio in %:

| T | reactive prop. | deadline-aware | point forecast | proposed | oracle WF | proposed vs deadline-aware / vs reactive prop. / vs oracle |
|---|---|---|---|---|---|---|
| 4 slots (2 ms) | 3.91 | 7.89 | 6.57 | **3.07** | 6.89 (oracle + KKT: 1.91) | −61 % / −21 % / −55 % |
| 10 slots (5 ms) | 7.42 | 10.20 | 7.53 | **5.07** | 6.01 | −50 % / −32 % / −16 % |
| 20 slots (10 ms) | 8.91 | 10.78 | 9.46 | **7.71** | 6.63 | −28 % / −13 % / +16 % |
| 40 slots (20 ms) | **11.80** | 15.84 | 14.08 | 13.15 | 10.83 | −17 % / +11 % / +21 % |

* At short intervals the KKT rule beats even the oracle-informed water-fill
  (perfect point forecast, proportional shortage split): the allocation
  rule, not only the forecast, carries the gain. The "oracle" is a reference
  for the forecast, **not** a bound.
* At T = 40 slots (budgets held 5x the LL deadline) every deadline-aware
  controller over-reserves the LL peak rate and the deadline-unaware
  proportional controller wins on the weighted metric. Interval-level
  reservation of a deadline-feasible rate stops making sense when the
  interval is much longer than the deadline; this bounds the regime in
  which the proposed method should be used.

**Telemetry delay tau** (`delay_runs.csv`), weighted violation ratio in %:

| tau | reactive prop. | deadline-aware | point forecast | proposed | proposed vs reactive prop. |
|---|---|---|---|---|---|
| 0 slots (0 ms) | 8.16 | 9.89 | 8.45 | **6.85** | −16 % |
| 2 slots (1 ms, default) | 8.91 | 10.78 | 9.46 | **7.71** | −13 % |
| 5 slots (2.5 ms) | 9.86 | 11.90 | 10.51 | **8.77** | −11 % |
| 10 slots (5 ms) | 11.30 | 13.93 | 12.45 | **11.07** | −2 % |

The ordering is preserved at every tau and the margin over the deadline-aware
controllers is stable (21-24 % vs deadline-aware reactive, 11-19 % vs point
forecast), but the margin over the deadline-unaware proportional controller
shrinks to 2 % once the state is 5 ms old (2.5x the LL deadline). Timely
telemetry is part of the operating regime, like a short control interval.

**Forecast miscalibration** (`miscalibration_runs.csv`; every forecast
quantile level shifted by eps before allocation, Kolmogorov distance |eps|):

| eps | −0.3 | −0.2 | −0.1 | 0 | +0.1 | +0.2 | +0.3 | point forecast | deadline-aware |
|---|---|---|---|---|---|---|---|---|---|
| high 0.80 | 7.80 | 7.64 | 7.61 | 7.71 | 8.13 | 9.13 | 9.45 | 9.46 | 10.78 |
| shift | 10.96 | 10.94 | 11.10 | 11.13 | 11.53 | 12.27 | 12.50 | 12.42 | 13.68 |

Under-reserving (eps < 0) is almost harmless because a common shift of all
levels is largely absorbed by the multiplier lambda. Over-reserving degrades
gradually (+23 % at eps = +0.3 at high load, +12 % under shift); even there
the rule matches the point-forecast controller and stays below the
deadline-aware reactive controller. This is the empirical counterpart of
Proposition 4 in `method.md` (loss bounded linearly in eps).

## Forecast quality (validation seeds, T = 20)

Empirical coverage at nominal 5/25/50/75/90/95 %: 5.6/25.6/50.7/75.3/89.9/94.9 %
(well calibrated). Median relative MAE: GBM 37 %, window median 49 %,
persistence 52 %. Mean pinball loss 0.0224 (GBM) vs 0.0293 (window quantiles).
Training: 101k rows, 12 s CPU. Note: scikit-learn's default early stopping
uses an internal 10 % split of the *training* rows (no validation/test data).

## Tuning (validation seeds 2000-2003, scenarios moderate/high)

Selected: reactive_prop margin 0, EWMA window 20; maxweight margin 0,
head-of-line-age weight 1; queue_aware margin 0, 1 horizon; point_forecast
margin 0; fixed_quantile level 0.75 (of 0.75 / 0.90 / 0.95); proposed_cal
gamma 0.005. Every positive safety margin was worse on validation: inflating
a point estimate hurts when the shortage is split proportionally, because
over-claiming cells receive more. Longer persistence windows (3, 6 horizons)
were also worse (r* over a long window becomes a peak-rate estimate).

## Decision overhead (Python, 4-core CPU, per 10-ms control epoch, mean over all main runs)

static 0.02 ms, reactive proportional 0.04 ms, MaxWeight 0.05 ms,
deadline-aware reactive 0.09 ms, oracle 0.09 ms, window quantiles 2.2 ms,
point forecast 2.5 ms, fixed quantile 2.5 ms, proposed 3.5 ms. The KKT rule
itself is < 0.1 ms; the cost is feature construction and evaluating 6 x 300
trees (vectorised numpy traversal). A compiled implementation would be
needed in a real O-DU.

## Part A x Part B: compression width vs allocation rule (`compression_runs.csv`, 160 runs)

Scenario `moderate`, 10 test seeds, the same user traffic in every run; only
the BFP mantissa width changes, which rescales the fronthaul bits per
PRB-layer (the Part A lever) and therefore the load offered to the link.
Weighted violation ratio in %, mean over seeds (best real controller in bold):

| BFP width | offered load | reactive prop. | deadline-aware | point forecast | proposed |
|---|---|---|---|---|---|
| 6 bits | 0.44 | 0.22 | 0.18 | 0.15 | **0.11** |
| 9 bits (default) | 0.65 | 3.90 | 4.02 | 3.00 | **1.96** |
| 12 bits | 0.86 | **11.37** | 13.84 | 12.50 | 12.01 |
| 14 bits | 0.99 | **17.29** | 20.38 | 19.16 | 20.81 |

Reading: compression decides which load regime the link is in; the
allocation rule decides how much is lost in that regime. Allocation matters
most between ~0.5 and ~0.8 load (at 0.65 the proposed rule loses half as much
as the reactive controllers). At 0.86 the proportional controller is already
slightly better on the weighted metric, and at 0.99 (sustained overload) no
allocation rule helps: protecting the low-latency cells costs more eMBB bits
than the 3:1 weight repays. In that regime the answer is more compression or
more capacity, not a better split. Not modelled: the signal-quality (NMSE)
cost of fewer mantissa bits; that side is covered by the Part A compression
curves (`results/figures/exp1_nmse_vs_cr.png`).

## Part A results carried in this repository (earlier work, not re-run this term)

* Compression study (`docs/mid_evaluation_report.md`, `results/figures/exp1..4`):
  at M = 64 antennas, N = 1200 subcarriers, SNR 20 dB on a 3GPP TDL-A
  channel, O-RAN BFP-8 gives ~3.9x at −46 dB NMSE in ~3 ms; truncated SVD
  (r = 12) ~16x at −21 dB in 18-30 ms; RAS-BFP (random sketch + QR, r = 12)
  ~16x at −18 dB in ~7 ms; CSEE (top-K delay taps, K = 300) ~13x at −21 dB in
  ~5 ms, ~63x at −19 dB with K = 60. ACAFS (split choice from channel rank)
  saves 0 % below ~15 dB SNR and 55-75 % above, versus a fixed split 6. The
  `src/` package these scripts import is not in the repository, so these
  numbers are quoted, not regenerated.
* Matrix-inversion benchmark (`results/benchmark_results.csv`, re-runnable
  with PyTorch): medians over 200 held-out well-conditioned matrices. n = 100:
  LU via LAPACK 0.17 ms (rel. error 5e-8), learned iteration
  (InverseNet-Ultra) 0.46 ms (1e-6), learned Newton-Schulz 0.95 ms (4e-4),
  Newton-Schulz 1.0 ms, SVD 2.8 ms, LU (scipy) 2.9 ms, QR 3.9 ms, direct
  neural net (InverseNet-MLP) 4.6 ms with 0.5 relative error (unusable).
  n = 500: LAPACK 18 ms, learned iteration 34 ms, LU (scipy) 56 ms, SVD
  107 ms, QR 102 ms. Lessons: n ≈ 100 fits a 0.5-ms slot on a CPU, n ≈ 500
  does not; a direct learned inverse does not work but a learned iteration
  with fixed cost does; predictable cost matters for slot deadlines.

## What we do NOT claim

* No real-world validation: two simulated traffic families (a hand-designed
  bursty one with a held-out shift, and a standards-based one built from 3GPP
  channel and traffic models with a simplified round-robin scheduler). The
  3GPP family removes the "self-generated traffic" objection only partly:
  the models are standard, the scheduler and the single-link fronthaul are
  ours.
* Part A compression figures are not regenerated in this repository (missing
  `src/` package); the inversion benchmark uses random well-conditioned
  matrices, not channel matrices. The paper therefore uses only the BFP
  width as a load lever and does not claim the Part A compression results.
* No optimality or stability claim for the closed loop; the propositions in
  `method.md` are feasibility, equal weighted tail probability, backlog-first,
  and a linear loss bound under forecast miscalibration.
* No universal superiority: only −4 % against reactive proportional under
  flash crowds, loses to it at T = 40 slots, at ≥ 0.86 offered load and
  nearly ties with it when telemetry is 5 ms old; the ML component adds
  ≈ 2 % under the held-out shift.
* The gain is a priority trade. Under the unweighted violation ratio the
  proportional controller loses fewer total bits at moderate/high load in
  Family S, and in Family G with w_LL = 1 the rule is worse than the
  point-forecast water-fill. The claim holds for operators who weight the
  low-latency class at least 2-3x.
* A forecaster transferred from the other traffic family still beats every
  reactive controller but not the in-family point forecast.
