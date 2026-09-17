# Mid-evaluation notes: opening, demo script, Q&A

Deck: `docs/fhlm/BTP_midterm_fronthaul_load_management.pptx` (16 main slides +
4 backup, speaker notes on every slide; PDF alongside). Regenerate with
`python -m fhlm.make_slides` after re-running experiments — every number on
the slides is read from `results/fhlm/`.

## 1. Opening (60-90 s)

"My project is on fronthaul load management in Open RAN. With the 7-2x
functional split, several radio units share one Ethernet fronthaul link, and
operators over-subscribe that link on purpose — in my default scenario the
eight cells' peak IQ traffic is 2.4 times the usable 25-gigabit capacity —
because cells rarely burst at the same time. When they do, the distributed
unit must decide how much of the link each cell may use, and it must decide
in advance: budgets are held for a control interval of about 10 milliseconds,
telemetry is delayed, and low-latency cells can only tolerate about 2 ms of
queueing before their IQ is useless.

I built a slot-level simulator of exactly this problem, five baseline
controllers including a deadline-aware reactive one and an oracle, and a
proposed method with two parts: a gradient-boosted forecaster that predicts
six quantiles of each cell's *deadline-feasible rate* for the next interval,
and an allocation rule derived from KKT conditions that gives every cell its
backlog rate plus the forecast quantile at which the priority-weighted
probability of needing one more bit is equal across cells.

On five test scenarios with five seeds each, the rule reduces
priority-weighted deadline violations by 10 to 50 % against the same
controller driven by a point forecast, and beats the deadline-aware reactive
baseline on every seed, including a held-out burstier traffic family. It is
only a tie with the simplest proportional controller under flash crowds,
online calibration did not help, and the ML forecaster adds little under
distribution shift — I will show those negative results too. Everything in
the deck is generated from the repository."

## 2. Live demo script (about 3 minutes)

```bash
cd <repo>
python -m pytest tests/test_fhlm.py -q                      # 13 tests, ~15 s
python -m fhlm.run_experiments demo --scenario high         # one trace, 3 controllers, ~10 s
python -m fhlm.make_figures                                 # regenerates the figures from saved CSVs
```

Say while it runs:

* Tests: "capacity compliance in every slot, non-negative queues, bit
  accounting, zero load gives zero violations, overload saturates, same seed
  gives same result, the controllers never see the future, the compiled tree
  evaluation equals scikit-learn's."
* Demo output: three lines with the weighted violation ratio, LL and eMBB
  violations, utilisation and decision time for the deadline-aware reactive,
  point-forecast and proposed controllers on the same trace. Expected order:
  proposed < point forecast < deadline-aware reactive on the primary metric.
* Open `results/fhlm/figures/fig6_demo_timeseries.png`: "grey is the demand
  of one low-latency cell, the steps are the budgets; the reactive controller
  is one interval late at every burst; the proposed controller lifts the
  budget where the predictive distribution is wide."

Full reproduction if asked (about 6 minutes on 4 cores, without the sweep):

```bash
python -m fhlm.train --out models/fhlm_quantile_gbm_T20_d2.pkl --report results/fhlm/forecast_training_T20_d2.json
python -m fhlm.run_experiments tune
python -m fhlm.run_experiments main
python -m fhlm.run_experiments sweep     # +~5 min: trains forecasters for T = 4, 10, 40
python -m fhlm.run_experiments demo
python -m fhlm.make_figures && python -m fhlm.make_slides
```

## 3. "What is novel here?"

Nothing in the ingredients is new: quantile gradient boosting, the
constrained multi-item newsvendor / KKT solution, water-filling, adaptive
conformal inference and the network-calculus notion of a deadline-feasible
rate all exist. The candidate contribution is the *combination and its
evaluation in the fronthaul budget-coordination setting*:

1. The forecast target is the **deadline-feasible rate r\*** of each cell for
   the next interval, not the traffic volume. r\* is the smallest constant
   service rate that lets no bit wait longer than the class deadline; for a
   2-ms class it is essentially the peak 4-slot burst rate. This is what
   makes the forecast deadline-aware and is why point forecasts of it are a
   poor basis for reservation (it is right-skewed).
2. The **allocation rule turns the forecast distribution into budgets under
   the shared-link constraint by equalising the priority-weighted tail
   probability** that the marginal bit is needed. The safety margin per cell
   is therefore *derived* — wide forecast or high priority gives more margin,
   confident forecast gives none — instead of being a tuned global constant.
   The tuning results show that global constants do not work here (every
   positive margin was worse on validation).
3. The **evaluation** is fair by construction (identical traces, identical
   delayed observations, train/validation/test seed split, tuned baselines,
   point-forecast ablation, non-ML ablation, held-out shift) and reports
   where the method does *not* win.

Say "proposed method" or "candidate contribution", not "novel algorithm".
If pushed: the closest works are Lagén et al. 2022 (shared 7-2x link,
reactive compression control, no forecasting) and Bega et al. DeepCog/AZTEC
(forecast-driven slice capacity, point forecasts, no per-cell deadlines, no
coupled allocation rule). Cohen et al. 2023 use conformal prediction for a
single URLLC stream; our ACI ablation shows that per-stream correction does
not transfer to a coupled allocation.

## 4. "Why is ML necessary, and how does it compare with a strong non-ML approach?"

Honest answer: ML is *useful*, not *necessary*.

* The non-ML variant of the same rule (empirical quantiles of the last 30
  horizons' r\*) already beats every baseline. The GBM adds a further 7-51 %
  reduction in the nominal traffic family — because the learned model uses
  lags, EWMAs, the last slots, spectral efficiency and the cell identity to
  sharpen and shift the quantiles — but only about 2 % under the held-out
  shift, where it is out of distribution.
* So most of the gain comes from (a) forecasting the right quantity (r\*) and
  (b) the allocation rule, not from the learning. That is why the rule is
  presented as the contribution and the GBM as the best of the forecasters
  we tried.
* The strong non-ML comparator, the deadline-aware reactive controller, has
  the same deadline knowledge, the same weights and the same water-fill; it
  loses 18-79 % because its persistence estimate of r\* is one interval late
  and is a point value.
* Cost: the GBM makes the decision about 40x more expensive (3.2 ms vs
  0.08 ms in Python per 10-ms epoch). A production DU would need a compiled
  implementation or a longer epoch; the window-quantile variant is the
  fallback if that cost is unacceptable.

## 5. Likely supervisor questions and honest answers

1. **Why is fronthaul demand not just application traffic?** In 7-2x the
   fronthaul carries frequency-domain IQ per scheduled PRB-layer, so the
   load is (user bits / spectral efficiency) x a fixed IQ constant (3,387
   bits per PRB-layer-slot at BFP-9 with 8 % overhead). Two cells with the
   same user throughput can differ 2-3x in fronthaul load. The simulator
   models this per cell with drifting spectral efficiency.
2. **Why does the controller have to decide in advance at all?** Because a
   budget is a reservation held for T slots by the DU scheduler / switch
   policer, and telemetry is tau slots old. If T = 1 and tau = 0 there is
   nothing to predict; the interval sweep shows the predictive advantage
   growing from T = 2 ms upward and the reactive controllers catching up
   only at very short T. We did not make T artificially long: 10 ms is the
   default and the sweep reports 2-20 ms.
3. **Is the oracle an upper bound?** No. It is the same water-fill rule fed
   with the true next-horizon r\*, so it removes forecast error from the
   baseline family. At T = 2 ms the proposed KKT rule beats it, which shows
   the rule matters as much as the forecast. We deliberately call it a
   "reference".
4. **Why are the absolute violation ratios so high (8-15 % at 0.8 load)?**
   Heavy-tailed Pareto ON/OFF bursts at 80 % mean load with budgets fixed
   for 10 ms produce frequent local overload; the oracle itself loses 13 % of
   eMBB bits. The traffic is synthetic and deliberately stressful. The
   relative, paired differences between controllers are the result.
5. **Where does the method fail?** (a) Under flash crowds it is a tie with
   the deadline-unaware proportional controller on the weighted metric.
   (b) At T = 20 ms — 5x the LL deadline — reserving the LL peak rate for the
   whole interval over-reserves and the proportional controller wins.
   (c) The GBM adds almost nothing under the held-out shift. (d) ACI
   calibration is harmful.
6. **Why did ACI calibration hurt?** ACI raises a cell's quantile level after
   misses. In a coupled allocation the LL misses are partly *caused* by the
   shortage split, not by forecast bias, so the correction inflates LL
   reservations and starves eMBB. A coupled calibration (adjusting lambda,
   or calibrating on the un-constrained forecast error only) is future work.
7. **Is there train-test leakage?** Training seeds 1000-1015, validation
   2000-2003, test 3000-3004 are disjoint; the forecaster is frozen before
   any test run; all features are functions of past slots only (checked by
   `test_oracle_and_controllers_never_see_future`); normalisation uses fixed
   configuration constants; tuning used validation scenarios only; the shift
   family never appears in training or tuning. scikit-learn's early stopping
   uses a 10 % split of the training rows.
8. **How were the baselines tuned? Are they artificially weak?** Grid on
   validation seeds over margins {0, 0.25, 0.5}, EWMA windows {20, 60},
   persistence windows {1, 3, 6}. Every baseline redistributes unused
   capacity. The chosen values (margin 0) were the best for them; the
   deadline-aware reactive controller uses the same weights, the same
   backlog-slack rate and the same water-fill as the point-forecast
   controller.
9. **Why the priority-weighted violation ratio as the primary metric?**
   Because the trade-off between LL and eMBB is the whole point of the
   coordination and an unweighted ratio would let a controller "win" by
   starving the small LL cells. Weights 3:1 are an operator choice; the
   per-class ratios are always reported alongside.
10. **What about fairness and utilisation?** Jain's index of per-cell
    service ratio is > 0.99 for every controller; the minimum cell service
    ratio is highest for the proposed and proportional controllers. The
    proposed method also has the highest utilisation within the deadline-
    aware family (72 % vs 69-70 %) because it reserves margin selectively.
11. **Is the allocation optimal?** Only for the surrogate objective (expected
    served demand under the forecast distribution, one interval, independent
    cells); the program is separable concave so KKT gives its global optimum.
    We claim nothing about closed-loop optimality or queue stability.
12. **How expensive is it?** 3.2 ms per 10-ms epoch in Python; 0.08 ms for
    the reactive baseline. The rule itself is microseconds; the cost is
    evaluating 1,800 trees for 8 cells. A C++/numba port or a smaller model
    would be needed in a real DU.
13. **Why gradient boosting and not an LSTM/transformer?** Six quantile GBMs
    train in 12 s on a laptop, are well calibrated on validation (coverage
    within 1 point of nominal), and the whole pipeline must be reproducible
    on CPU. A sequence model is a possible improvement, but the ablation
    shows the model is not where most of the gain is.
14. **Why synthetic traffic and how is it justified?** No per-cell PRB-level
    fronthaul traces were available. The generator follows the heavy-tailed
    ON/OFF source model (Willinger et al. 1997) plus slow regime changes and
    flash crowds; parameters are chosen so that a cell's ON-state rate stays
    below its own air-interface peak (violations come from the shared link,
    not the radio). Replacing it with public PRB-utilisation datasets is the
    first item of future work.
15. **What is left for the final evaluation?** Real/public traces;
    a skill-weighted blend of GBM and window quantiles as the fallback
    (instead of ACI); a second lever (per-cell compression) under the same
    rule; a switch-level packet queue; more seeds; ablation of the r\*
    target versus interval volume; a compiled implementation for timing.
16. **Could the DU simply export its schedule (cooperative DBA style) instead
    of forecasting?** Yes, where such an interface exists (e.g. CTI for
    PON fronthaul) it removes the need to forecast one interval ahead. Our
    setting is the case where budgets must be committed before the schedule
    is known — shared switch policers, delayed telemetry, or multi-DU
    aggregation.
17. **What exactly is "deadline violation" here?** Bits that wait in the DU
    queue longer than the class deadline (2 ms LL, 10 ms eMBB) are discarded
    and counted; it is a DU queueing deadline, not end-to-end latency. The
    O-RU T2a window and switch queueing are not modelled (budgets keep the
    link from queueing).
