# Study guide: the whole project in simple language

Read this top to bottom once, then use Section 9 (one-line answers) right
before the meeting. Every number here comes from files in the repository.

---

## 1. The big picture (30 seconds)

A mobile base station is split in two boxes. The **radio unit (O-RU)** sits on
the tower with the antennas. The **distributed unit (O-DU)** does the heavy
processing and can be in a nearby building. The cable between them is the
**fronthaul**.

In Open RAN the split is called **7-2x**: the radio unit does very little, so
it sends almost raw radio samples ("IQ data") to the O-DU. That is a lot of
data. One 100 MHz cell with 4 antenna layers can need up to about 7.4 Gbit/s.

So "fronthaul load management" means: **keep this link from being overloaded.**
There are only two ways:

* **Part A: make the data smaller** (compression).
* **Part B: share the link well** between several cells (allocation).

My project did both. Part A earlier, Part B this term, and one experiment that
puts them together.

---

## 2. Part A: making the data smaller

### 2.1 What the data looks like

Every slot (0.5 ms) the radio unit produces a matrix **Y** with one row per
antenna (64) and one column per subcarrier (1200). Sending it raw is too much.

### 2.2 The standard method: block floating point (BFP)

Take a block of 12 numbers, store one shared exponent, and keep only a short
"mantissa" (say 9 bits) for each number. It is what the O-RAN standard uses.
Fast, almost lossless, but only about **4x** smaller. Fewer mantissa bits =
smaller data but more quantisation noise.

### 2.3 Going further with matrix structure

To compress more you must use the *shape* of the matrix:

* **Low rank.** Antennas are correlated, so Y is "almost" a few strong
  directions. **Truncated SVD** keeps the r strongest directions: about
  **16x** smaller at -21 dB error, but an SVD of a 64 x 1200 matrix takes
  18-30 ms per slot. Too slow for a 0.5 ms slot.
* **RAS-BFP** (ours): get the same rank-r result faster. Multiply Y by a small
  random matrix ("sketch"), take a thin **QR** to get an orthonormal basis Q,
  then Y ≈ (Y Q) Qᴴ. Send BFP(YQ) and BFP(Q). About 16x at -18 dB in ~7 ms,
  3-4x faster than SVD. The theory behind it is randomised low-rank
  approximation (Halko, Martinsson, Tropp 2011).
* **CSEE** (ours): use a different structure. The radio channel has only a
  few strong delay taps. Do an inverse FFT along the subcarriers, keep the
  top-K taps, quantise. About 13x at -21 dB in ~5 ms; up to 63x with fewer
  taps.
* **ACAFS**: choose the functional split (7.2x / 7.1 / 6) per user from the
  channel rank. In simulation: no saving at low SNR, 55-75 % above ~15 dB.

**Words to know:** NMSE = normalised mean squared error (how wrong the
reconstructed matrix is; more negative dB = better). CR = compression ratio.

### 2.4 The matrix-inversion benchmark

All of the above, and also MIMO equalisation and precoding, need matrix
decompositions or inversions **every slot**. So I timed them on a CPU for
random well-conditioned matrices of size 10, 100 and 500 (200 test matrices
each).

Key numbers (medians, n = 100 / n = 500):

| Method | n = 100 | n = 500 | error |
|---|---|---|---|
| LU via LAPACK (`numpy.linalg.inv`) | 0.17 ms | 18 ms | ~1e-7 (exact) |
| QR | 3.9 ms | 102 ms | exact |
| SVD | 2.8 ms | 107 ms | exact |
| Newton-Schulz iteration | 1.0 ms | 70 ms | exact |
| Learned iteration (InverseNet-Ultra) | 0.46 ms | 34 ms | ~1e-6 |
| Direct neural net (InverseNet-MLP) | 4.6 ms | n/a | **0.5 = useless** |

Lessons:

* LU is the method to beat. QR and SVD cost several times more with no
  accuracy gain on nice matrices; use them only when you need their extra
  structure.
* A neural network that tries to output the inverse directly **does not
  work** (50 % error). A learned method that keeps the Newton-Schulz
  iteration and only learns the step sizes does work and has a **fixed,
  predictable cost** — that matters when you have a hard slot deadline.
* A 0.5 ms slot fits an n ≈ 100 inversion on a CPU; n ≈ 500 does not, so
  such matrices must be done less often, updated incrementally, or offloaded.

### 2.5 Honest status of Part A

The figures and report exist in the repo (`results/figures/exp1..4`,
`REPORT.md`, `docs/mid_evaluation_report.md`). The compression code imported
a `src/` package that is **not in the repository**, so those numbers are
quoted, not re-run this term. The inversion benchmark can be re-run (needs
PyTorch). Say this before anyone asks.

---

## 3. Part B: sharing one link between cells

### 3.1 The setup

* 8 cells share one **25 Gbit/s** Ethernet link. Their total peak is **2.4x**
  the link. This is deliberate ("statistical multiplexing"): cells rarely
  burst at the same time, so you can buy a smaller link.
* 3 cells are **low-latency** (their bits must be sent within 2 ms = 4 slots,
  priority weight 3). 5 cells are **eMBB** (normal data, 10 ms = 20 slots,
  weight 1).
* Each cell has a queue in the O-DU. A bit that waits longer than its deadline
  is **dropped and counted as a violation**.
* Every **10 ms** (20 slots) a controller gives each cell a **budget**: how
  many bits per slot it may send. Budgets must add up to at most 97 % of the
  link (3 % kept for control traffic). They are fixed for the 10 ms.
* The controller sees the state **2 slots late** and never sees the future.

### 3.2 Why fronthaul load is not the same as user traffic

In 7-2x the fronthaul carries IQ samples per **scheduled resource block**, not
user bits. Fronthaul bits = user bits ÷ spectral efficiency x 3,387 bits per
resource-block-layer (at BFP-9 with 8 % packet overhead). A cell with poor
radio conditions (low spectral efficiency) needs many more resource blocks,
hence more fronthaul, for the same user data.

### 3.3 Why decide in advance at all?

Because a budget is a **reservation** held for 10 ms, and the information is
already 2 slots old. The traffic of the next 10 ms is unknown when you decide.
If you could decide every slot with perfect information there would be nothing
to predict — but that is not how a scheduler/policer works.

### 3.4 What we measure

Main score, chosen before any tuning: **priority-weighted deadline-violation
ratio** = (3 x dropped low-latency bits + dropped eMBB bits) ÷ (3 x arrived
low-latency bits + arrived eMBB bits). Lower is better. We also report the
violation ratio per class, link utilisation, queueing delay, fairness (Jain's
index) and decision time.

### 3.5 What "demand" means: the deadline-feasible rate r\*

This is the key modelling idea. For a cell, look at the arrivals of the next
interval and its deadline D. **r\* is the smallest constant service rate at
which no bit waits longer than D.**

* For eMBB (D = 10 ms) r\* is close to the average rate.
* For low-latency (D = 2 ms) r\* is basically the **peak 2-ms burst rate**,
  which is much larger than the average and much harder to predict.

We forecast r\*, not the traffic volume. r\* is **skewed**: usually low,
sometimes very high. If you predict one number (the median), you under-serve
the bursts. If you add a fixed safety margin to everyone, you waste capacity.

Budget needed by a cell = rate to clear its current backlog in time + r\* of
the arrivals not seen yet.

---

## 4. The controllers we compare

| Controller | In plain words | Knows deadlines? | Uses a forecast? |
|---|---|---|---|
| Static equal share | link ÷ 8 for everyone | no | no |
| Reactive proportional | backlog + running average of demand, split proportionally, spare redistributed | no | no |
| Deadline-aware reactive (strong baseline) | backlog rate + last interval's r\*, priority weights, water-fill | yes | no (uses last value) |
| Point forecast + water-fill (ablation) | same, but r\* comes from the forecast **median** | yes | one number |
| **Proposed** | forecast **range** of r\* + KKT rule | yes | full range |
| Proposed, simple quantiles (no ML) | same rule, quantiles from the last 30 intervals | yes | range, no learning |
| Proposed + online calibration (ACI) | shifts a cell's quantile level after misses | yes | range |
| Oracle water-fill | knows the true next r\* — not implementable | yes | perfect number |

Every knob (safety margins, windows) was tuned on **validation seeds**, never
on test seeds. The best margin was **0 for every baseline**: adding a margin to
a single predicted number made things worse.

"Water-fill" = fill the highest-priority needs first, then the next, until the
link is full; then split any shortage proportionally.

---

## 5. The proposed method, step by step

**Step 1 — Forecast a range.** Six gradient-boosted tree models, one per
quantile (5, 25, 50, 75, 90, 95 %), predict each cell's r\* for the next
interval. Inputs: 28 features from past slots only (recent demand, lags,
running averages, queue, spectral efficiency, cell identity). Trained on
training seeds only; training takes about 12 s on a laptop.

**Step 2 — Split the link.** We want to maximise the priority-weighted amount
of demand that gets served, in expectation under the forecast, subject to the
link limit:

> maximise Σᵢ wᵢ · E[ min(backlogᵢ + r\*ᵢ, rᵢ) ]   subject to   Σᵢ rᵢ ≤ link,  0 ≤ rᵢ ≤ peakᵢ

This is a **constrained newsvendor problem**. It is concave, so the KKT
conditions give the answer in closed form:

> rᵢ = backlogᵢ + Fᵢ⁻¹(1 − λ / wᵢ),   clipped to [0, peakᵢ]

Fᵢ⁻¹ is the inverse CDF of the forecast (a straight-line interpolation through
the six quantiles). λ is **one number** found by bisection so that the budgets
add up exactly to the link.

**In words:** every cell is cut off at the same priority-weighted probability
of needing one more bit. A cell with a wide (uncertain) forecast or a high
priority automatically gets more margin. A cell with a confident forecast gets
about its median. Backlog is always funded first.

**Properties we proved (and test):** budgets are always feasible; at the
optimum every cell has the same weighted risk; backlog is funded before any
uncertain demand. If the forecast were a single number, the rule collapses to
the point-forecast water-fill — which is why that is the fair comparison.

**Cost:** the rule itself takes microseconds. The whole decision, including
evaluating 1,800 trees for 8 cells, takes about 3.2 ms in Python per 10-ms
interval (reactive baselines: 0.1 ms). A real O-DU would need a compiled
version.

---

## 6. Experiments and results

### 6.1 Setup

* Traffic is **synthetic**: a smooth part + heavy-tailed on/off bursts per
  cell + slow load changes about every second + drifting spectral efficiency.
* Five scenarios: low (0.50 load), moderate (0.65), high (0.80), flash crowds
  (0.80 with short overloads), and **shift** (held-out: bursts 1.5x stronger
  and longer, never seen in training or tuning).
* Seeds: training 1000-1015, validation 2000-2003, test 3000-3004. No overlap.
* Every controller sees exactly the same traffic, seed by seed. 8 controllers
  x 5 scenarios x 5 seeds = 200 runs, 10 s of simulated time each.

### 6.2 Main results (weighted violation ratio, %, lower is better)

| Method | low | moderate | high | flash crowds | shift |
|---|---|---|---|---|---|
| Static equal share | 4.16 | 9.38 | 15.27 | 19.30 | 23.65 |
| Reactive proportional | 0.75 | 3.81 | 8.94 | 12.25 | 12.92 |
| Deadline-aware reactive | 0.39 | 4.07 | 10.86 | 14.70 | 14.21 |
| Point forecast + water-fill | 0.18 | 3.11 | 9.63 | 13.44 | 12.93 |
| Proposed, simple quantiles (no ML) | 0.17 | 2.41 | 8.60 | 12.67 | 11.80 |
| **Proposed** | **0.08** | **2.00** | **7.89** | **11.82** | **11.59** |
| Proposed + calibration | 0.09 | 2.02 | 8.12 | 12.24 | 12.95 |
| Oracle water-fill | 0.01 | 1.56 | 6.90 | 10.21 | 8.23 |

The proposed rule is the best real controller in all 5 scenarios.

### 6.3 Seed-by-seed comparison (how much lower the proposed rule is, and on how many of 5 seeds it won)

| Compared with | low | moderate | high | flash crowds | shift |
|---|---|---|---|---|---|
| point forecast (same model, median only) | −53 % (5/5) | −36 % (5/5) | −18 % (5/5) | −12 % (5/5) | −10 % (5/5) |
| deadline-aware reactive | −79 % (5/5) | −51 % (5/5) | −27 % (5/5) | −20 % (5/5) | −18 % (5/5) |
| reactive proportional | −89 % (5/5) | −48 % (5/5) | −12 % (5/5) | **−3 % (3/5) = tie** | −10 % (5/5) |
| simple quantiles (ML ablation) | −51 % | −17 % | −8 % | −7 % | **−2 %** |

### 6.4 Where the gain comes from

At high load the proportional controller keeps eMBB nearly clean but lets the
low-latency cells lose ~15 % of their bits — it does not know about deadlines.
All deadline-aware controllers protect the low-latency cells (~3 %) and pay
with eMBB. Among them, the proposed rule loses the least eMBB (12.3 % vs
15.9 % for point forecast) and has the highest utilisation (72 %), because it
adds margin only where the forecast is uncertain. Even the oracle loses 13 % of
eMBB bits: budgets fixed for 10 ms cannot follow heavy bursts.

### 6.5 Ablations (what each piece is worth)

* **Range vs single number:** −10 % to −53 %, every seed. This is the direct
  test of "represent uncertainty".
* **ML vs simple quantiles:** the trained model adds 7-51 % on normal traffic
  but only ~2 % under the held-out shift. So **most of the gain is the rule
  (r\* target + KKT split), not the learning.** The simple-quantile version is
  the robust fallback.
* **Online calibration (ACI): made things worse** (1-9 % on normal traffic,
  10 % under shift). Why: in a coupled allocation, low-latency misses are
  partly *caused* by the shortage split, not by forecast bias, so the
  correction inflates low-latency reservations and starves eMBB. A negative
  result, reported honestly.
* **Control interval sweep** (high load, forecasters retrained per interval):

  | interval | vs deadline-aware reactive | vs reactive proportional | vs oracle |
  |---|---|---|---|
  | 2 ms | −62 % | −27 % | **−57 % (beats the oracle)** |
  | 5 ms | −52 % | −37 % | −13 % |
  | 10 ms (default) | −30 % | −18 % | +17 % |
  | 20 ms | −17 % | **+12 % (loses)** | +25 % |

  At short intervals the rule beats even a perfect single-number forecast, so
  the *rule* does real work. At 20 ms (5x the low-latency deadline) reserving
  the low-latency peak for the whole interval wastes capacity and the simple
  proportional controller wins. **The method is for intervals up to a few times
  the shortest deadline.**

### 6.6 Forecast quality

On validation data the 5 / 50 / 95 % quantiles are exceeded 5.6 / 50.7 /
94.9 % of the time — well calibrated. Median error 37 % vs 52 % for "assume
the last value" (persistence).

---

## 7. Putting A and B together

Same user traffic, same seeds; only the BFP mantissa width changes, which
changes the fronthaul bits per resource block and therefore the load:

| BFP width | load on link | best real controller | proposed vs reactive proportional |
|---|---|---|---|
| 6 bits | 0.43 | proposed | 0.04 % vs 0.13 % — almost nothing lost either way |
| 9 bits (default) | 0.63 | proposed | 1.6 % vs 3.4 % — allocation matters most here |
| 12 bits | 0.83 | tie | 10.8 % vs 10.7 % |
| 14 bits | 0.97 | reactive proportional | 19.3 % vs 16.4 % — **proposed loses** |

**Message:** compression decides which load regime you are in; allocation
decides how much is lost in that regime. Allocation helps most between ~0.5
and ~0.8 load. At ~1.0 load no allocation rule helps — you need more
compression or more capacity. Not modelled: the signal-quality cost of fewer
bits (that is what Part A's NMSE curves are for).

---

## 8. Limitations (say them before they are asked)

* Part A: compression numbers quoted, not re-run (missing `src/`); benchmark
  matrices are random and well-conditioned, not real channel matrices.
* Part B: synthetic traffic only; 5 seeds, so win counts instead of p-values.
* Not a universal win: tie with the proportional controller under flash
  crowds; loses to it at 20 ms intervals and at ~1.0 load; ML adds little
  under shift; calibration hurt.
* Simplified link: a budget-enforced pipe, no switch queue, one traffic class
  per cell, no HARQ; "violation" is a DU queueing deadline, not end-to-end
  latency.
* The oracle is a reference, not an upper bound (the rule beats it at 2 ms).
* Proofs cover feasibility, equal weighted risk and backlog-first only; no
  stability or closed-loop optimality claims.
* Decision time 3.2 ms in Python; needs a compiled version for a real O-DU.

---

## 9. One-line answers for likely questions

* **What is the problem in one sentence?** Several cells share a fronthaul
  link smaller than their total peak; decide every 10 ms how much each may
  send, before knowing the next 10 ms of traffic.
* **What is new?** Not the ingredients. The combination: forecast the
  deadline-feasible rate r\* as a *range*, and cut every cell at the same
  weighted risk under the shared-link constraint — plus a fair evaluation that
  also shows where it fails.
* **Why forecast r\* and not traffic?** Because the deadline is what matters;
  for a 2 ms class r\* is the peak burst rate, which the average hides.
* **Why a range and not one number?** r\* is skewed; one number under-serves
  bursts, and a fixed margin wastes capacity (every positive margin was worse
  on validation).
* **Why ML?** Useful, not necessary. The simple-quantile version already beats
  every baseline; the model adds 7-51 % on normal traffic, ~2 % under shift.
* **Is the oracle an upper bound?** No — it is a perfect *single-number*
  forecast fed to the water-fill rule. Our rule beats it at short intervals.
* **Where does it fail?** Flash crowds (tie), long intervals (loses), ~1.0
  load (loses), calibration (hurt).
* **How do Parts A and B connect?** Compression sets the load regime;
  allocation decides the loss in that regime. Both levers on one figure.
* **Why did the neural inverter fail but the learned iteration work?**
  Keeping the algorithm's structure and learning only the uncertain part
  works; learning the whole map does not. Same theme as Part B: the rule does
  the work, the model sharpens it.
* **Any leakage?** No: separate seed ranges, forecaster frozen before testing,
  features from past slots only (unit-tested), tuning on validation only.
* **What next?** Restore Part A's `src/` and re-run; make compression width a
  per-cell knob inside the allocation rule (joint compression + allocation —
  the paper direction); real traces; a coupled calibration; a compiled
  decision.

---

## 10. Glossary

* **O-RU / O-DU** — radio unit on the tower / processing unit nearby.
* **Fronthaul** — the link between them. **7-2x** — the O-RAN split where the
  O-RU does very little and sends IQ samples.
* **IQ data** — complex radio samples (in-phase and quadrature).
* **BFP** — block floating point compression; shared exponent, short mantissa.
* **PRB / resource block** — the smallest unit the scheduler assigns (12
  subcarriers). Fronthaul cost is per scheduled PRB-layer.
* **Spectral efficiency** — user bits per resource block; depends on radio
  quality.
* **Statistical multiplexing** — buying a link smaller than the total peak
  because peaks rarely coincide.
* **Slot** — 0.5 ms. **Control interval T** — 20 slots = 10 ms.
* **Deadline-feasible rate r\*** — smallest constant rate that serves the next
  arrivals with no bit late.
* **Quantile** — the value below which X % of outcomes fall. Six quantiles =
  a picture of the range.
* **Newsvendor problem** — how much to stock when demand is uncertain and both
  too little and too much cost something.
* **KKT conditions** — the equations that characterise the optimum of a
  constrained optimisation problem.
* **Water-fill** — fill highest-priority needs first until the link is full.
* **ACI** — adaptive conformal inference; an online rule that widens or
  narrows prediction intervals after misses.
* **NMSE** — normalised mean squared error (dB). **CR** — compression ratio.
* **SVD / QR / LU** — matrix factorisations; SVD gives the best low-rank
  approximation, QR an orthonormal basis, LU the fastest exact inverse.
* **Newton-Schulz** — an inversion method using only matrix multiplications.
