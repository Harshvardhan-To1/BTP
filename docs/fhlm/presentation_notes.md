# Mid-evaluation notes: opening, demo script, Q&A

Deck: `docs/fhlm/BTP_midterm_fronthaul_load_management.pptx` (18 main slides +
6 backup, speaker notes on every slide; PDF alongside). Rebuild with
`python -m fhlm.make_slides` after re-running experiments — every Part B
number on the slides is read from `results/fhlm/`, the Part A inversion table
from `results/benchmark_results.csv`.

## 1. Opening (60-90 s)

"My project is about fronthaul load management in Open RAN. The fronthaul is
the link between the radio unit on the tower and the processing unit. In the
7-2x split it carries raw radio samples, so it is one of the most loaded links
in the network. There are two ways to manage that load.

The first is to make the data smaller. In the first part of my project I
studied compression methods that use the structure of the IQ matrix — truncated
SVD, a randomised sketch plus QR, and delay-domain sparsity — and compared them
with the standard O-RAN block-floating-point compression. Because all of these
depend on matrix decompositions and inversions running inside a half-millisecond
slot, I also benchmarked how fast LU, QR, SVD, Newton-Schulz and learned
inverters actually run on a CPU.

The second way is to share one link well between several cells. Operators
over-subscribe the link on purpose — in my scenario eight cells' peak traffic
is 2.4 times the link — because cells rarely burst together. When they do, the
processing unit must decide how much each cell may send, and it must decide in
advance: budgets are held for about 10 milliseconds, telemetry is late, and
low-latency cells can only wait about 2 milliseconds. I built a simulator of
this, five reference controllers including one that knows the future, and a
new rule: forecast each cell's need as a range, then split the link so that
every cell is cut at the same priority-weighted risk.

On five test scenarios the rule cuts priority-weighted deadline violations by
10 to 50 percent compared with the same controller using a single predicted
number, and beats the deadline-aware reactive controller on every seed. It ties
with the simplest controller under flash crowds, loses to it when budgets are
held for 20 ms, and the machine-learning model adds little under a traffic
shift — I will show those too. Finally, one experiment runs both levers on the
same traffic: compression decides how much load reaches the link, allocation
decides who loses data when it is full. Everything in the deck is generated
from the repository."

## 2. Live demo script (about 3 minutes)

```bash
cd <repo>
python -m pytest tests/test_fhlm.py -q                      # 14 tests, ~15 s
python -m fhlm.run_experiments demo --scenario high         # one trace, 3 controllers, ~10 s
python -m fhlm.make_figures                                 # rebuilds the figures from saved CSVs
```

Say while it runs:

* Tests: "the link limit holds in every slot, queues never go negative, bits
  are counted correctly, zero load gives zero violations, overload saturates,
  same seed gives same result, controllers never see the future, the fast
  tree evaluation equals scikit-learn's, and changing the compression width
  changes fronthaul bits but not user bits."
* Demo output: three lines with the weighted violation ratio, low-latency
  and eMBB violations, utilisation and decision time for the deadline-aware
  reactive, point-forecast and proposed controllers on the same trace.
  Expected order: proposed < point forecast < deadline-aware reactive.
* Open `results/fhlm/figures/fig6_demo_timeseries.png`: "grey is the demand
  of one low-latency cell, the steps are the budgets; the reactive controller
  is one interval late at every burst; the proposed controller raises the
  budget where the forecast range is wide."
* If asked about Part A: open `results/inference_time.png` and
  `results/figures/exp1_nmse_vs_cr.png`. Say clearly that the compression
  figures are from the earlier run and the `src/` package is not in the repo.

Full reproduction if asked (about 7 minutes on 4 cores, without the sweep):

```bash
python -m fhlm.train --out models/fhlm_quantile_gbm_T20_d2.pkl --report results/fhlm/forecast_training_T20_d2.json
python -m fhlm.run_experiments tune
python -m fhlm.run_experiments main
python -m fhlm.run_experiments sweep            # +~5 min: trains forecasters for T = 4, 10, 40
python -m fhlm.run_experiments compression --scenario moderate
python -m fhlm.run_experiments demo
python -m fhlm.make_figures && python -m fhlm.make_slides
```

## 3. "What is new here?"

None of the ingredients is new: quantile gradient boosting, the constrained
newsvendor / KKT solution, water-filling, adaptive conformal inference and the
network-calculus idea of a deadline-feasible rate all exist. The candidate
contribution is the *combination and its fair evaluation in the shared
fronthaul setting*:

1. We forecast the **deadline-feasible rate r\*** of each cell for the next
   interval, not the traffic volume. r\* is the smallest constant service
   rate at which no bit waits longer than its deadline; for a 2-ms class it is
   basically the peak 2-ms burst rate. That is what makes the forecast
   deadline-aware, and it is why a single predicted number is a poor basis for
   a reservation (r\* is skewed: usually low, sometimes very high).
2. The **allocation rule turns the forecast range into budgets under the
   shared-link constraint by cutting every cell at the same priority-weighted
   risk** of needing one more bit. The safety margin of each cell is therefore
   *derived* — a wide forecast or a high priority gives more margin, a
   confident forecast gives none — instead of being one tuned constant. Tuning
   showed that one constant does not work here (every positive margin was
   worse on validation).
3. The **evaluation** is fair by construction (same traffic, same delayed
   observations, separate training / validation / test seeds, tuned
   baselines, single-number ablation, non-ML ablation, held-out shift) and it
   reports where the method does *not* win.

Say "proposed method" or "candidate contribution", not "novel algorithm".
If pushed: the closest works are Lagén et al. 2022 (shared 7-2x link, reactive
compression control, no forecast) and Bega et al. DeepCog / AZTEC (forecast
first, then slice capacity; single predicted number, no per-cell deadlines, no
coupled rule). Cohen et al. 2023 use conformal prediction for one URLLC
stream; our calibration ablation shows that per-stream correction does not
carry over to a coupled allocation.

## 4. "Why machine learning, and how does it compare with a strong non-ML method?"

Honest answer: ML is *useful*, not *necessary*.

* The same rule with simple empirical quantiles (last 30 intervals) already
  beats every baseline. The trained model adds a further 7-51 % on normal
  traffic — it uses lags, running averages, the last slots, spectral
  efficiency and the cell identity to sharpen the range — but only about 2 %
  under the held-out shift, where it is out of its training range.
* So most of the gain comes from (a) forecasting the right quantity (r\*) and
  (b) the allocation rule, not from learning. That is why the rule is the
  contribution and the model is "the best forecaster we tried".
* The strong non-ML comparator, the deadline-aware reactive controller, has
  the same deadline knowledge, the same weights and the same water-fill; it
  loses 18-79 % because its estimate of r\* is one interval late and is a
  single number.
* Cost: the model makes the decision about 40x more expensive (3.2 ms vs
  0.08 ms in Python per 10-ms epoch). A real DU would need a compiled version
  or a longer epoch; the simple-quantile variant is the fallback.
* Part A gives the same lesson from the other side: a neural network that
  directly outputs a matrix inverse fails (~50 % error), while a learned
  iteration that keeps the Newton-Schulz structure works. Keeping the
  mathematical structure and learning only what is uncertain is the theme.

## 5. Likely supervisor questions and honest answers

### Part A (compression, decomposition, inversion)

1. **Why does compression need matrix decomposition?** Block floating point
   only shortens the numbers (~4x). To go further you must use the structure
   of the IQ matrix: it has low rank because antennas are correlated
   (truncated SVD, RAS-BFP) and it is sparse in the delay domain because the
   channel has few strong taps (CSEE). Both are matrix factorisations.
2. **What is RAS-BFP in one sentence?** Multiply Y by a random sketch matrix
   to get a small r x N matrix, take its thin QR to get an orthonormal basis Q,
   write Y ≈ (Y Q) Qᴴ and send BFP(YQ) and BFP(Q). It gets the SVD's rank-r
   quality (up to a factor 1 + ε, Halko-Martinsson-Tropp) at O(rMN) instead of
   O(MN·min(M,N)) cost.
3. **Why benchmark inversion at all?** Equalisation, precoding and the
   encoders all need decompositions or inverses every slot (0.5 ms). The
   benchmark shows what fits: LU via LAPACK at n = 100 takes 0.17 ms, at
   n = 500 it takes 18 ms — so large matrices must be inverted less often,
   tracked incrementally, or offloaded. It also shows that predictable cost
   (fixed-step iterations) matters as much as average speed.
4. **Why did the direct neural inverter fail?** The map from a matrix to its
   inverse is extremely non-smooth near ill-conditioning and the output has
   n² entries; a fully connected net fits the training set but does not
   generalise (0.36-0.53 relative error). The learned Newton-Schulz variant
   keeps the algorithm and learns only step coefficients, so it works (1e-6
   at n = 100) and its cost is fixed.
5. **Can you re-run Part A?** The inversion benchmark yes (needs PyTorch).
   The compression experiments import a `src/` package that is not in the
   repository, so those figures are quoted from the saved files; restoring the
   package is the first Part A item of future work.
6. **How do Part A and Part B connect?** The simulator's fronthaul cost per
   resource block is exactly the compression setting (BFP width). The A + B
   slide runs the same user traffic at 6 / 9 / 12 / 14 bits: compression
   moves the system along the load axis (0.43 → 0.97), allocation decides how
   much is lost at a given load. Allocation helps most between 0.5 and 0.8;
   at ~1.0 load only more compression or more capacity helps. The
   signal-quality cost of fewer bits is not modelled in Part B — that is what
   Part A's NMSE curves are for.

### Part B (sharing the link)

7. **Why is fronthaul demand not just user traffic?** In 7-2x the fronthaul
   carries IQ samples per scheduled resource block, so the load is
   (user bits ÷ spectral efficiency) x a fixed constant (3,387 bits per
   PRB-layer-slot at BFP-9 with 8 % overhead). Two cells with the same user
   throughput can differ 2-3x in fronthaul load. The simulator models this
   per cell with drifting spectral efficiency.
8. **Why must the controller decide in advance?** A budget is a reservation
   held for T slots by the DU scheduler or a switch policer, and telemetry is
   tau slots old. With T = 1 and tau = 0 there is nothing to predict; the
   interval sweep shows the predictive advantage from 2 ms upward. 10 ms is
   the default and the sweep reports 2-20 ms.
9. **Is the oracle an upper bound?** No. It is the same water-fill rule fed
   with the true next-interval r\*, so it removes forecast error from that
   family. At T = 2 ms the proposed rule beats it, which shows that the rule
   matters as much as the forecast. We call it a "reference".
10. **Why are the absolute violation ratios so high (8-15 % at 0.8 load)?**
    Heavy-tailed bursts at 80 % mean load with budgets fixed for 10 ms cause
    frequent local overload; even the oracle loses 13 % of eMBB bits. The
    traffic is synthetic and deliberately stressful; the paired differences
    between controllers are the result.
11. **Where does the method fail?** (a) Flash crowds: tie with the
    proportional controller. (b) T = 20 ms (5x the low-latency deadline):
    reserving the low-latency peak for the whole interval over-reserves and
    the proportional controller wins. (c) The model adds almost nothing under
    the held-out shift. (d) Online calibration hurts. (e) At ~1.0 load
    (BFP-14 in the A + B experiment) no allocation rule helps.
12. **Why did online calibration hurt?** It raises a cell's quantile level
    after misses. In a coupled allocation, low-latency misses are partly
    *caused* by the shortage split, not by forecast bias, so the correction
    inflates low-latency reservations and starves eMBB. A coupled calibration
    (adjusting λ, or calibrating on the unconstrained forecast error only) is
    future work.
13. **Is there train-test leakage?** Training seeds 1000-1015, validation
    2000-2003, test 3000-3004 do not overlap; the forecaster is frozen before
    any test run; all features use past slots only (checked by a test);
    normalisation uses fixed configuration constants; tuning used validation
    scenarios only; the shift family never appears in training or tuning.
14. **How were the baselines tuned?** Grid on validation seeds over margins
    {0, 0.25, 0.5}, running-average windows {20, 60}, persistence windows
    {1, 3, 6}. Every baseline redistributes unused capacity. Margin 0 was best
    for all of them; the deadline-aware reactive controller uses the same
    weights, backlog rate and water-fill as the point-forecast controller.
15. **Why the priority-weighted violation ratio as the main score?** The
    trade-off between low-latency and eMBB cells is the whole point; an
    unweighted ratio would let a controller "win" by starving the small
    low-latency cells. Weights 3:1 are an operator choice; per-class ratios
    are always reported alongside.
16. **Fairness and utilisation?** Jain's index of per-cell service ratio is
    > 0.99 for every controller. The proposed method has the highest
    utilisation within the deadline-aware family (72 % vs 69-70 %) because it
    adds margin only where the forecast is uncertain.
17. **Is the allocation optimal?** Only for the one-interval surrogate
    objective (expected served demand under the forecast, independent cells);
    that problem is separable and concave so KKT gives its global optimum. We
    claim nothing about closed-loop optimality or queue stability.
18. **How expensive is it?** 3.2 ms per 10-ms epoch in Python; 0.08 ms for
    the reactive baseline. The rule itself takes microseconds; the cost is
    evaluating 1,800 trees for 8 cells. A C++/numba port or a smaller model
    would be needed in a real DU.
19. **Why gradient boosting and not an LSTM / transformer?** Six quantile
    models train in 12 s on a laptop, are well calibrated on validation
    (coverage within 1 point of nominal), and the whole pipeline must run on
    a CPU. A sequence model is a possible improvement, but the ablation shows
    the model is not where most of the gain is.
20. **Why synthetic traffic?** No per-cell resource-block-level fronthaul
    traces were available. The generator follows the heavy-tailed ON/OFF
    source model (Willinger et al. 1997) plus slow load changes and flash
    crowds; parameters keep a cell's ON-state rate below its own radio peak
    (violations come from the shared link, not the radio). Public
    PRB-utilisation datasets are the first Part B item of future work.
21. **Could the DU simply export its schedule instead of forecasting?** Yes,
    where such an interface exists (e.g. CTI for PON fronthaul) it removes
    the need to forecast. Our setting is the case where budgets must be
    committed before the schedule is known — shared switch policers, delayed
    telemetry, or multi-DU aggregation.
22. **What exactly is a "deadline violation" here?** Bits that wait in the DU
    queue longer than the class deadline (2 ms low-latency, 10 ms eMBB) are
    discarded and counted; it is a DU queueing deadline, not end-to-end
    latency. The O-RU receive window and switch queueing are not modelled
    (budgets keep the link from queueing).
23. **What is left for the final evaluation?** Part A: restore `src/`, re-run
    Exp 1-4, benchmark on realistic channel matrices. A + B: make the
    compression width a per-cell knob of the allocation rule (trade signal
    quality for load). Part B: real / public traces; a skill-weighted mix of
    trained and simple quantiles as the fallback; a switch-level queue; more
    seeds; a compiled implementation.
