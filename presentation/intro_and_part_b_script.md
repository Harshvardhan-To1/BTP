# Introduction and Part B — Script and Likely Questions

Script for the **introduction** (title, slides 1–6) and **Part B** (slides
18–34) of `presentation/BTP_final_deck.pdf`. Slide numbers are the numbers in
the bottom-right corner of each slide. Every number here matches the deck and
the results in `results/fhlm/`.

This is the **full-length** version: about 3 minutes for the introduction and
about 10 minutes for Part B at 140 words a minute. If you are giving the whole
deck in a 12-minute slot, use the timings in `final_deck_script.md` and say
only the **bold** sentence on each slide below. The question lists are the same
either way.

How to use it:

- Normal text is what you say. *[Italics in brackets]* tell you where to
  point.
- **Bold** marks the one sentence per slide to keep if you run short.
- Under each slide, **Likely questions** lists what examiners most often ask
  about that slide, with a short answer you can say out loud. The first
  question in each list is the one most likely to come.

| Section | Slides | Target time |
|---|---|---|
| Introduction | Title, 1–6 | 3:10 |
| Part B setting | 18–20 | 1:50 |
| B1: KKT newsvendor rule | 21–28 | 4:20 |
| B2: Bayesian Transformer | 29–30 | 1:20 |
| B3: back-pressure newsvendor | 31–34 | 2:20 |
| **Total** | | **about 13:00** |

---

# Part 1 — Introduction

## Title — Fronthaul Load Management for B5G Wireless Communications  *[0:15]*

Good morning. We are Harshvardhan Choudhary and Mayank Yadav, and this is our
B.Tech. project, guided by Dr. Sumit Gautam: fronthaul load management for
beyond-5G wireless networks.

In one sentence: the fronthaul is the most heavily loaded link in a modern
base station, and we attack that load from two sides. We make the data
smaller, and we share the link more intelligently.

**Likely questions**

- *What does "B5G" add here; isn't this a 5G problem?* It is a 5G problem
  that gets worse beyond 5G. More antennas (massive MIMO), wider bandwidths
  and denser cells all multiply the fronthaul rate, so the problem grows with
  every generation.
- *Why "load management" and not just "compression"?* Because compression is
  only one lever. Even perfectly compressed data can overload a shared link
  when several cells burst at once. That second lever, allocation, is Part B.

---

## Slide 1 — Roadmap  *[0:20]*

*[Walk the five boxes left to right.]* We start with background: what the
fronthaul is and why it is overloaded. Part A makes the data smaller and the
distributed unit faster. Part B shares one link between many cells. Then we
show how the two parts work together, and we wrap up.

*[Point to the box at the bottom.]* One principle runs through the whole
project.

**Keep the mathematical structure of the problem, and learn only what is
uncertain.**

**Likely questions**

- *What does "learn only what is uncertain" mean concretely?* In Part A we
  keep the Newton–Schulz iteration and learn only its starting point. In
  Part B we keep the closed-form allocation rule and learn only the forecast
  distribution of each cell's need. We never ask a network to learn the
  whole map from input to answer; when we tried that (a network predicting a
  matrix inverse directly), it failed.
- *Who did which part?* *[Answer honestly according to your split; the deck
  hands over from Speaker 1 to Speaker 2 at Part B.]*

---

## Slide 2 — How a phone reaches the Internet: fronthaul, midhaul, backhaul  *[0:45]*

*[Point to the diagram, left to right.]* A phone talks over the air to the
antennas on the mast. From there the signal crosses three transport links.

*[Point to the red link and the first table row.]* The **fronthaul** joins
the radio unit, the O-RU, at the mast to the distributed unit, the O-DU. It
carries digitised radio samples, called IQ samples, for every antenna and
every resource block. That is 7 to over 100 gigabits per second per cell,
with a latency budget of about 100 microseconds.

*[Second row.]* The **midhaul** joins the distributed unit to the central
unit over the 3GPP F1 interface. It carries user packets, so its rate is
roughly the user data rate, within a few milliseconds.

*[Third row.]* The **backhaul** joins the central unit to the 5G core and
carries many cells' traffic, within about 10 milliseconds.

**The fronthaul has the highest rate and the tightest deadline, because a
late radio sample is useless. Its cost decides how many cells an operator can
afford to deploy, so this project is about the fronthaul.**

**Likely questions**

- *Why is the fronthaul latency budget about 100 microseconds?* The radio
  timing loops, especially HARQ acknowledgements, leave very little time for
  transport. Light in fibre travels about 5 microseconds per kilometre, so a
  100 microsecond budget limits the fibre to roughly 20 kilometres.
- *Why is the fronthaul rate so much higher than the user data rate?* It
  carries the raw radio waveform per antenna, not the decoded bits. Every
  antenna and every resource block is sent, with 16-bit I and Q values,
  whatever the coding rate of the user data.
- *What protocol is used on the fronthaul?* In O-RAN it is eCPRI over
  Ethernet (the "Open Fronthaul" interface); older C-RAN used CPRI.
- *Which link do you study, and why not the others?* Only the fronthaul. The
  midhaul and backhaul carry packet traffic with millisecond budgets, and
  standard packet networking already handles them.

---

## Slide 3 — From D-RAN to Open RAN: the 7-2x functional split  *[0:35]*

*[Top row.]* In a traditional distributed RAN, the baseband unit sits at each
site.

*[Middle row.]* Centralised RAN pools the baseband units in one place, but
the CPRI link between them ships samples at a **constant** rate,
proportional to bandwidth times antennas, even when the cell is idle.

*[Bottom row.]* Open RAN uses the **7-2x split**. The FFT stays in the radio
unit, so the fronthaul carries frequency-domain IQ **only for the resource
blocks that are actually scheduled**, compressed with block floating point,
over Ethernet. So the load now **follows the traffic**, and several cells can
be statistically multiplexed onto one link.

**Fronthaul load is the number of scheduled resource-block layers times the
bits per resource-block layer, not the number of application bits. Both
parts of our project build on that fact.**

**Likely questions**

- *What is a "functional split"?* It is where the processing chain of the
  base station is cut between the radio unit and the distributed unit. 3GPP
  numbers the options 1 to 8; option 8 is CPRI, sending raw time-domain
  samples; 7-2x is a low-PHY split defined by O-RAN.
- *Why 7-2x and not a higher split like option 2?* A higher split sends far
  less data, but the radio unit becomes complex and expensive, and you lose
  centralised processing across antennas and cells, such as massive-MIMO
  processing and coordinated transmission. 7-2x is the compromise that O-RAN
  standardised.
- *What is block floating point (BFP)?* Take a block of 12 numbers (one
  resource block), store one shared exponent, and keep only a short mantissa
  of, say, 9 bits for each value. It is the O-RAN standard compression: simple
  and fast, but it saves only about 2 times against 16-bit IQ.
- *What does "statistical multiplexing" mean here?* Cells rarely peak at the
  same moment, so an operator can buy one link smaller than the sum of the
  peaks. That saves money, but it means that when bursts do coincide, someone
  loses data. Part B decides who.
- *Is precoding in the O-RU part of 7-2x?* Yes, optionally. O-RAN defines
  "Category A" radio units without precoding and "Category B" radio units with
  it. Our downlink precoding-placement result on slide 14 compares these two
  options.

---

## Slide 4 — Why the fronthaul is the bottleneck  *[0:40]*

*[Point to the diagram.]* Here is our setting. Eight radio units, three
low-latency and five broadband, share one 25-gigabit Ethernet link to an O-DU
pool. The sum of their peaks is 2.44 times the link capacity.

*[Under the figure.]* For scale: a 64-antenna cell needs about 34 gigabits per
second raw, and even a 100 megahertz cell with 4 layers and 9-bit BFP peaks at
about 7.4 gigabits per second.

*[First red box.]* That gives two problems. First, the data are large and the
time is short. BFP gives only about 2 times over 16-bit IQ. And every
half-millisecond slot, the O-DU has to invert a small Gram matrix for all 273
resource blocks. With numpy and LAPACK that takes 3.2 milliseconds for 16
users, **six times longer than the slot**.

*[Second red box.]* Second, the link is shared and smaller than the peak.
When bursts coincide, someone loses data. Low-latency cells tolerate only 2
milliseconds of delay. And the budgets have to be set every 10 milliseconds,
on telemetry that is already 1 millisecond old, before the traffic is seen.

**Problem one is solved by Part A, problem two by Part B.**

**Likely questions**

- *Why 273 resource blocks?* That is the maximum number of resource blocks
  in a 100 MHz carrier at 30 kHz subcarrier spacing in 5G NR.
- *Why does the O-DU need a matrix inverse every slot?* For zero-forcing or
  regularised zero-forcing (RZF) precoding and detection, it computes
  W = Hᴴ(HHᴴ + αI)⁻¹ for each resource block, and the channel H changes as
  users move.
- *Isn't 3.2 ms just slow Python?* It is numpy calling LAPACK, which is
  compiled and optimised. The problem is that LAPACK is tuned for one large
  matrix, while the O-DU has 273 small ones per slot. Part A's library,
  libcmat, does the same job in 0.226 ms.
- *Why is the link deliberately smaller than the sum of peaks?* Because that
  is how operators save money. Sizing for the sum of peaks wastes capacity
  most of the time. 2.44 times was chosen so the link is stressed but usable.
- *Where does the 7.4 Gbit/s figure come from?* 273 resource blocks × 4
  layers × 3,387 bits per resource-block layer per slot, every 0.5 ms. The
  3,387 bits is the BFP-9 cost including about 8 % overhead.

---

## Slide 5 — Problem statement and our two levers  *[0:25]*

So we pull two levers.

*[Left box.]* **Part A** makes the data smaller and the O-DU faster. We
compress the per-slot IQ using its structure, low rank and delay sparsity,
with error bounds, and we make the complex RZF precoder fit inside the
0.5 millisecond slot on a CPU.

*[Right box.]* **Part B** shares one link well. Every 10 milliseconds, before
the traffic is known, we set per-cell budgets on the shared link so that the
priority-weighted fraction of bits that miss their deadline is as small as
possible.

*[Bottom box.]* And they connect. **Compression sets how much load reaches the
link; the allocation rule decides who loses data when bursts coincide.**

**Likely questions**

- *Why not just buy a bigger link?* Fronthaul fibre and switch ports are a
  major part of deployment cost, especially for many small cells. Both levers
  let the same link carry more cells.
- *Which lever matters more?* It depends on load. Our A × B experiment
  (slide 28) shows that at low load nothing is lost whatever you do, between
  about 0.5 and 0.8 load the allocation rule makes a big difference, and near
  full load only compression or more capacity helps.
- *Why is the target metric "priority-weighted"?* Because losing a
  low-latency bit is worse than losing a broadband bit. We weight a
  low-latency bit 3 times. We also report the unweighted ratio so this choice
  can be checked.

---

## Slide 6 — Headline results at a glance  *[0:30]*

Here are the results up front, so you know where we are heading.

*[Walk the four cards left to right.]* 8.1 times compression of channel IQ
against 16-bit, at minus 20 dB error, where the O-RAN standard gives 2 times.
A precoder from our own C library that is 14 times faster than numpy and
LAPACK: 0.226 milliseconds per slot. 72 percent less fronthaul by precoding in
the radio unit, at 99.7 percent of the sum-rate. And our final Part B
controller, BPN, beats the strongest baselines in all 10 scenarios of three
traffic families, by 3 to 25 percent.

*[Bottom bullets.]* Our inversion method RMT-WS needs 6 matrix multiplies
where Neumann-type methods need more than 10. And our first Part B rule, the
KKT newsvendor rule, is the best of 12 controllers on two families, 11 to 43
percent better than a point forecast, on all 20 test seeds.

**Each of these numbers is on a later slide, with how it was measured.**

**Likely questions**

- *8.1× at −20 dB: is −20 dB good enough?* At our 20 dB operating SNR, the
  channel estimate already has noise at about −20 dB. So the compression
  error is comparable to the estimation noise that is already there.
- *Is the 14× fair? Same hardware, same precision?* Yes: same 4-core AVX-512
  Xeon, complex64, median of 40 runs, whole precoder (Gram, inverse, weights,
  scaling) for 273 resource blocks. Accuracy against float64 is a sum-rate
  loss below 10⁻⁶ percent. Even on one core libcmat is 2.5 to 4 times faster.
- *10/10 against which baselines?* Against the better of predictive
  MaxWeight and a policy learned with the cross-entropy method, in each
  scenario, each re-tuned with the same search budget as ours. Paired over 20
  test seeds, all p ≤ 0.024 after Holm correction.
- *Is everything simulated?* Yes. All data are generated from models,
  including standard 3GPP channel and traffic models. Replaying operator or
  testbed traces is future work. We know of no public per-slot, per-cell PRB
  traces.

*[Part A, slides 7–17, is presented here. Then the handover.]*

---

# Part 2 — Part B: share one link well

## Slide 18 — Part B setting: decide budgets before the traffic is seen  *[0:45]*

Thank you. Part B asks a different question from Part A: when several cells
share one link that is too small for all their peaks, who gets to send how
much?

*[Left bullets.]* Eight cells share one 25-gigabit Ethernet link. Three are
**low-latency** cells, LL, with a 2 millisecond deadline and priority weight
3. Five are **eMBB**, ordinary broadband, with a 10 millisecond deadline and
weight 1. After reserving 3 percent for control, management and
synchronisation traffic, the link carries 12.125 megabits per half-millisecond
slot, and the sum of the peaks is 2.44 times that.

*[Point to the timeline.]* Every 20 slots, 10 milliseconds, a coordinator
sets a budget for each cell, and that budget is **held for the whole
interval**. It sees telemetry that is 1 millisecond old. So when it decides,
the traffic it is deciding for has not arrived yet.

*[Blue box.]* Why decide in advance and not every slot? Because the near-real-
time RIC control loop runs at 10 milliseconds or slower, switch shaping is not
reconfigured every slot, and the schedulers of different cells cannot consult
each other inside the sub-millisecond pipeline.

*[Red box.]* So the question is: **if each cell's need is available as a
forecast distribution, how should one shared link be split between cells with
different deadlines and priorities?**

**Likely questions**

- *What is the near-real-time RIC?* The RAN Intelligent Controller defined by
  O-RAN. Its "near-real-time" loop runs between 10 ms and 1 s and controls
  the RAN through the E2 interface, using apps called xApps. Our controller
  is designed to run there.
- *Why can't you decide every slot?* With per-slot decisions and fresh
  telemetry there would be nothing to predict. But no deployed control loop
  across cells runs at 0.5 ms. We do sweep the interval from 2 to 20 ms
  (slide 28) to show what changes.
- *Why exactly 8 cells, 3 LL and 5 eMBB?* It is a representative mixed
  deployment that fills a 25GE link at realistic loads. The method itself
  works for any number of cells; the rule's cost grows linearly with the
  number of cells.
- *Where do the 2 ms and 10 ms deadlines come from?* They are typical
  targets for low-latency services (such as XR) and for broadband traffic.
  They are DU queueing deadlines, not end-to-end latency.
- *Couldn't the DU simply export its schedule in advance?* Where such an
  interface exists (for example, the Cooperative Transport Interface for PON
  fronthaul), you would not need to forecast. Our setting is the common case
  where budgets must be committed before the schedule is known.
- *What enforces the budget?* The DU scheduler of each cell, which may send
  at most ⌊rᵢ/β⌋ resource-block layers per slot, or a policer in the switch.

---

## Slide 19 — System model and metric  *[0:45]*

*[Top-left formula.]* First, the cost of one resource-block layer per slot.
With b-bit block floating point, it is 12 subcarriers times 2 for I and Q
times b bits, plus 8 bits of exponent, times 14 symbols, times an overhead
factor. At 9 bits that is 3,387 bits.

*[Green tag.]* **This is exactly where Part A enters.** The compression width
sets this cost, and so the load: 6-bit BFP gives 0.68 times the load, 12-bit
gives 1.32 times.

*[Middle-left formula.]* The fronthaul demand of a cell is its user bits
divided by its spectral efficiency, rounded up to whole resource blocks, times
that cost. So two cells with the same user traffic can differ by 2 to 3 times
in fronthaul load, depending on their radio conditions.

*[Right side.]* Every 20 slots we choose budgets that add up to at most the
link capacity, and each is capped at the cell's full 273 resource blocks.
Each cell has a first-in, first-out queue at the DU, and any bit older than
its deadline is dropped. That is a deadline violation. Because the budgets
enforce capacity, the link itself never queues.

*[Bottom box.]* Our main score, fixed before any tuning, is the
**priority-weighted violation ratio**, V_w: weighted bits dropped over
weighted bits arrived. A dropped low-latency bit counts 3 times. Lower is
better.

**Fronthaul load follows resource blocks, not user bits, and we score the
priority-weighted share of bits that miss their deadline.**

**Likely questions**

- *What is κ in the cost formula?* An overhead factor of about 1.08 for
  eCPRI and Ethernet headers, so that the cost per resource-block layer at
  BFP-9 is 3,387 bits.
- *Why divide by spectral efficiency?* A cell with good radio conditions
  packs more user bits into each resource block. The fronthaul carries
  resource blocks, so a cell-edge user costs more fronthaul per user bit.
- *Isn't the weighted metric chosen to make your method look good?* It is a
  fair concern. The weights express a real operator choice: an LL bit matters
  more. We fixed them before tuning, and we report the unweighted ratio and a
  weight sweep. In Family S, plain proportional control loses fewer total bits
  at high load; our rule ties at weight 1 and leads from weight 3. On the 3GPP
  family our rule also wins unweighted. So the claim is scoped to operators who
  weight LL 2–3 times or more.
- *Why drop late bits instead of sending them late?* A radio sample that
  misses its slot is useless; the receiver has already moved on. Dropping
  models that and keeps queues bounded.
- *Does the signal-quality cost of fewer BFP bits appear here?* No. Part B
  models only the load. The quality side of narrower mantissas is what Part
  A's error curves cover.
- *What else do you measure besides V_w?* The unweighted violation ratio,
  per-class violations, link utilisation, delay and Jain's fairness index.

---

## Slide 20 — Part B in three steps: two initial experiments, one final design  *[0:30]*

*[Walk left to right.]* Part B was built in three steps, and each step
answers the question the previous one raised.

*[B1.]* **B1** is the KKT newsvendor rule. We forecast each cell's
deadline-feasible rate, r-star, as a range, and split the link with a
closed-form rule that has four proven properties. It is the best of 12
controllers on two traffic families, and we submitted it to NCC 2027.

*[B2.]* **B2** asks whether a much better forecaster helps. It is a
link-aware quantile Transformer with a Bayesian mixture layer: uncertainty-
aware and explainable. It is our best-calibrated forecaster and improves B1
on every seed.

*[B3, green.]* **B3**, the back-pressure newsvendor, is our final design. It
is a learned two-stage policy that beats the strongest baselines in 10 out of
10 scenarios of three families.

*[Bottom box.]* Between B2 and B3 we implemented all three classic ways of
solving the underlying control problem.

**B3 combines the strengths of all three solution families in one policy
class.**

**Likely questions**

- *Why present B1 if B3 is better?* B1 has nothing to tune, a closed form
  and provable properties, and it is the building block of B3: B3's second
  stage is exactly the B1 rule. B1 also explains why the margins look the way
  they do.
- *Which one is your contribution?* All three, as a sequence. B1 is the
  conference paper. B2 is the forecasting contribution. B3 is the final
  controller and the strongest result.
- *What is the "underlying POMDP"?* A partially observed Markov decision
  process: the true state (every queue's age profile, the hidden traffic
  state, spectral efficiency) is only seen with a delay, and actions are held
  for 20 slots. It is intractable exactly, so we approximate it (slide 31).

---

## Slide 21 — B1, key idea 1: forecast the deadline-feasible rate r*, not the volume  *[0:50]*

The first idea is to forecast the **right quantity**.

*[Blue box.]* We call it r-star: the smallest constant rate at which **no bit
misses its deadline**. For every window of slots, take the bits that arrive
in that window and divide by the window length plus the deadline. The worst
window gives r-star.

*[Point to the small plot.]* An example. One burst of 8 units. With a
deadline of 1 slot, you have 2 slots to send it, so you need a rate of 4. With
a deadline of 7 slots you have 8 slots, so a rate of 1 is enough. A long
deadline lets you smooth the burst out, so r-star approaches the mean rate; a
short deadline does not, so it approaches the peak burst rate.

*[Bullets.]* For our 2 millisecond cells, r-star is typically 2 to 3 times the
mean rate, and strongly skewed to the right.

*[Right box.]* Every deadline-aware controller asks for the same thing: the
backlog already queued, plus r-star for what is still to come. Controllers
differ only in **how they estimate r-star** and **how they split a shortage**.

**A single predicted number is a poor basis for reserving a skewed quantity,
so we forecast a range.**

**Likely questions**

- *Why "+ D" in the denominator?* Bits that arrive in a window of length L
  can be sent during that window and for D more slots before they expire. So
  the available time is L + D slots.
- *Where does this formula come from?* Network calculus: it is the
  service-curve condition for a constant-rate server to meet a delay bound.
  We verified in unit tests that it is tight to one resource-block layer.
- *Why not just forecast the traffic volume?* Because the deadline is what
  matters. For a 2 ms cell, the average hides the burst, and the burst is what
  causes the violation.
- *How expensive is it to compute?* Trivial. The horizon is H = T + τ = 22
  slots, so there are only a few hundred windows per cell per interval.
- *What is "the backlog" Bᵢ?* The rate needed to drain the bits already
  queued before their remaining slack runs out.

---

## Slide 22 — B1, key idea 2: quantile forecast + closed-form KKT newsvendor split  *[1:00]*

The second idea is to forecast a **range**, and the third is how to **split**
the link.

*[Forecaster line.]* The forecaster is gradient-boosted trees: one model per
quantile level, 5, 25, 50, 75, 90 and 95 percent. It uses 28 features, all
from the past, trains in 12 seconds on a CPU, and its quantiles are
calibrated to within about 1 percentage point.

*[Surrogate formula.]* For one interval we maximise the priority-weighted
amount of need that is actually served, on average under the forecast,
subject to the budgets fitting in the link. This is the classic constrained
**newsvendor** problem: decide stock before you know demand. It is separable
and concave, so the KKT conditions give the **global** optimum.

*[Red box.]* And the solution is simple. Each cell gets its backlog plus the
quantile of its forecast at level one minus lambda over its weight. Lambda is
**one price for the whole link**, the same for every cell. We find it by
bisection so the budgets add up exactly to the capacity. That takes under a
tenth of a millisecond for eight cells.

*[Right picture.]* A toy example. If lambda comes out at 0.6, a low-latency
cell, weight 3, is funded to its 80 percent quantile, and a broadband cell,
weight 1, to its 40 percent quantile.

*[Green box.]* So every cell is cut at the same priority-weighted risk. A cell
with a wide forecast or a high priority automatically gets more margin.

**The margins come from the maths, not from tuning.**

**Likely questions**

- *What is the newsvendor problem?* A newspaper seller must decide in the
  morning how many papers to stock without knowing demand. Too few loses
  sales, too many is waste. With many products and one shared budget, the
  optimum stocks each product up to the point where one more unit is worth
  the same for all of them. Here products are cells, stock is budget, and the
  shared budget is the link.
- *Why is the objective concave?* The expected served amount E[min(need, r)]
  has slope w·P(need > r), which falls as r grows: each extra bit of budget
  is less likely to be used.
- *What is λ intuitively?* The shadow price of link capacity: the weighted
  probability that one more bit of budget would be used. If the link is not
  full, λ = 0 and every cell gets its full predicted range.
- *What happens if λ is larger than a cell's weight?* Its quantile level
  drops to zero or below, so it gets only its backlog. This "saturation" is
  important later: at high load it happens for eMBB in about half the
  intervals (slide 31).
- *How do you get a full distribution from only six quantiles?* By
  straight-line interpolation through the six forecast quantiles.
- *Why gradient boosting and not a neural network?* Six models train in
  12 seconds on a CPU, are well calibrated, and run inside the 10 ms budget.
  B2 tests a Transformer and finds it helps, but only modestly.
- *What are the 28 features?* The last 6 horizon means with their mean, std
  and max, two moving averages, the last 4 slot demands, r* of the last 3
  horizons, relative spectral efficiency, D/H and a one-hot cell code. All
  from past slots only.
- *Is 60 bisection steps necessary?* It is a safe fixed number; 60 halvings
  reach machine precision. The cost is negligible next to evaluating the
  trees.

---

## Slide 23 — B1, four proven properties and the closed control loop  *[0:30]*

*[Left blocks, top to bottom.]* The rule has four properties, all proved and
all checked by unit tests.

**One, feasibility**: whatever the forecast, caps hold and budgets never
exceed the link. **Two, equal weighted tail probability**: at the optimum,
every cell has the same weighted probability of running short. **Three,
backlog first**: bits already waiting are funded before uncertain future
demand of an equal- or lower-weight cell. **Four, robustness**: if the
forecast is off by epsilon, the loss grows at most linearly in epsilon.

*[Right diagram, walk the loop.]* The loop every 10 milliseconds: delayed
state, forecaster, allocation rule, budgets held for the interval, DU
schedulers, queues, and back to the state.

**These are properties of one interval; we do not claim closed-loop
optimality.**

**Likely questions**

- *What does "off by ε" mean in property 4?* Kolmogorov distance: the
  forecast CDF is never more than ε away from the true CDF. Then the loss is
  at most 2·ε·w_max·C.
- *Do you have a stability or closed-loop optimality proof?* No. The
  properties are for the one-interval problem. Queue carry-over between
  intervals is not covered, and we say so.
- *Why is property 2 interesting?* With a single-number forecast the rule
  collapses to filling cells in priority order. So the point-forecast
  controller is exactly the right comparison for "does the range matter?".
- *How do you handle edge cases?* A non-finite forecast falls back to window
  quantiles; zero demand gets zero budget plus a share of headroom; a link
  that is not full gives every cell its full predicted range.
- *Where are the proofs?* In `docs/fhlm/method.md` and the report, Chapter 5.

---

## Slide 24 — A fair evaluation by construction  *[0:35]*

We were careful that the comparison is fair.

*[Three boxes.]* We test on three independent traffic families. **Family S**
is synthetic and bursty, with heavy-tailed on/off bursts, slow regime changes
and spectral-efficiency drift, in five scenarios from low load to flash crowds
and a held-out distribution shift. **Family G** is built only from 3GPP
models, with nothing hand-designed. **Family M** is Markov-modulated traffic
with a semi-Markov held-out shift.

*[Bottom left.]* We compare 12 reference controllers in B1, and more than 19
in the extended study: static, reactive, MaxWeight, deadline-aware, a point
forecast from the same model, a fixed global quantile, a no-ML version, and
oracles as references.

*[Bottom right.]* Every controller sees **identical traffic traces** and the
same stale observations, over 20 test seeds of 20,000 slots each. Training,
validation and test seeds never overlap, and the forecasters are frozen
before testing. And we compare **seed by seed**, with paired bootstrap
confidence intervals and Holm-corrected Wilcoxon tests.

**Same traffic, same information, separate seeds, paired statistics.**

**Likely questions**

- *Why paired tests?* Most of the variation between seeds comes from when the
  bursts happen, which every controller shares. Comparing on the same seed
  removes that, so a real difference is not hidden by burst timing.
- *What is Holm correction?* We test many controller pairs at once, so some
  would look significant by chance. Holm's method adjusts the p-values for
  multiple comparisons.
- *Is there any train/test leakage?* No. Training seeds 1000–1015, validation
  2000–2003, test 3000–3019 never overlap. Features use past slots only,
  checked by a unit test. Normalisation uses fixed configuration constants.
  The shift scenario is never seen in training or tuning.
- *How were the baselines tuned?* On validation seeds, over margins and
  window lengths. Margin zero was best for all of them, and every baseline
  redistributes unused capacity.
- *Is the oracle an upper bound?* No. It is the same water-fill rule fed the
  true next-interval r*. It removes forecast error but is not the optimal
  policy; at a 2 ms interval our rule actually beats it. We call it a
  reference.
- *Why synthetic traffic?* No public per-slot, per-cell PRB-level fronthaul
  traces exist that we know of; public O-RAN datasets are at 250 ms or
  coarser. That is why Family G is built purely from 3GPP models.
- *Why Pareto sojourns in Family S?* Heavy-tailed on/off periods are the
  classic model for self-similar network traffic (Willinger et al., 1997).

---

## Slide 25 — B1, main result: best implementable controller everywhere  *[0:50]*

This is the main B1 result. Each number is the weighted violation
percentage on Family S, averaged over 20 test seeds; lower is better.

*[Point to the green row.]* Our rule, GBM plus KKT, is the best implementable
controller in all five scenarios. At high load it is 8.0 percent, against 9.7
for the point forecast from the same model, and 11.0 for the deadline-aware
reactive controller. Under the held-out shift it is 10.04.

*[Point to the grey row.]* The oracle row is a reference only; it sees the
future.

*[Green box.]* Seed by seed, on all 20 seeds and every scenario, with p below
0.01, we reduce violations by 11 to 43 percent against the point forecast,
22 to 54 percent against a fixed global quantile, 19 to 70 percent against the
deadline-aware controller, and 18 to 83 percent against MaxWeight.

*[Red box.]* And the weakest case, which I want to say myself: against
reactive proportional under flash crowds, the gain is only 4 percent, on 16 of
20 seeds. Proportional control starves the low-latency cells there but serves
broadband better.

**Best implementable controller in all five scenarios, and we show where it is
weakest.**

**Likely questions**

- *Why are the violation ratios so high, 8 to 15 percent?* The traffic is
  deliberately stressful: heavy-tailed bursts at 80 % mean load with budgets
  held for 10 ms. Even the oracle loses about 13 % of eMBB bits. The paired
  differences between controllers are the result, not the absolute level.
- *Why is the point forecast the key comparison?* It uses the same model and
  only drops the range. So the gap between them is exactly the value of
  forecasting a distribution.
- *Why does reactive proportional do so well in flash crowds?* In a flash
  crowd every cell's demand jumps together; there is no "quiet" cell to borrow
  from. Proportional sharing then serves eMBB well, at the cost of LL cells,
  and the weighted gap shrinks.
- *What does "implementable" mean?* It uses only information available at
  decision time. The oracles see the true future, so they are not
  implementable.
- *Why does static equal share do so badly?* It ignores demand completely;
  idle cells keep capacity that bursting cells need.

---

## Slide 26 — B1, where the gain comes from  *[0:40]*

*[Point to the plot.]* This shows one low-latency cell. Grey is the demand;
the steps are the budgets, each held for 10 milliseconds. The reactive
controller is always **one interval late**: it raises the budget after the
burst has already hit. Our rule raises the budget at the start of the burst,
because that is when the forecast range becomes wide.

*[Right table.]* Among the deadline-aware controllers at high load, ours has
the lowest broadband loss, 12.3 percent, the highest link utilisation, 72.2
percent, and the best fairness. That is because it adds margin **only where
the forecast is wide**. A single global quantile over-protects the
low-latency cells and wastes about a third of their allocation.

*[Bottom box.]* The ablations, changing one thing at a time, confirm it. A
range instead of one number: 11 to 43 percent better. A per-cell level instead
of one global level: 22 to 54 percent better. And even quantiles taken from a
window of recent history, with no machine learning at all, beat the point
forecast.

**The rule carries the gain; machine learning adds on top.**

**Likely questions**

- *If no-ML quantiles already work, why use ML?* It is useful but not
  necessary. The GBM adds 7 to 37 % on normal traffic, but only about 2 %
  under the held-out shift.
- *What is Jain's index?* A fairness measure between 0 and 1 of the per-cell
  service ratio; 1 means perfectly equal. All controllers are above 0.98;
  ours is 0.997.
- *Did you try online calibration of the quantiles?* Yes, adaptive conformal
  inference. It hurt. In a shared link an LL miss is partly caused by how the
  shortage was split, not by forecast bias. Raising LL levels after a miss
  over-reserves LL and starves eMBB. A coupled calibration is future work.
- *Why is utilisation only 72 %, not 100 %?* Budgets are caps held for
  10 ms. Capacity given to a cell that then does not use it is lost for that
  interval. This turns out to be exactly the weakness B3 fixes.

---

## Slide 27 — Tested on realistic traffic: the 3GPP evaluation models  *[0:40]*

Synthetic traffic can be tuned to suit a method, so we built a second,
independent family from standard models only.

*[Left table.]* **Family G** uses the 3GPP urban-macro channel from TR 38.901,
with path loss, shadowing, six interfering sites and fading. Link quality maps
to the TS 38.214 CQI table. Broadband users follow the FTP Model 3 traffic
model; low-latency users follow the 3GPP XR video model at 60 frames per
second. Fronthaul demand is the output of a per-cell resource-block scheduler.
Nothing is hand-designed or fitted to our results; only the number of users
is set to reach the target load.

*[Right table.]* The ranking is the same as on our own traffic. B1 beats every
baseline on all 20 seeds: at high load, minus 31 percent against
deadline-aware reactive control and minus 50 percent against reactive
proportional. B3, our final controller, adds a further 3 to 6 percent. And a
forecaster trained only on synthetic traffic, applied unchanged here, still
beats every reactive controller.

**On standards-based traffic, the same ranking holds.**

**Likely questions**

- *Why does the S-trained forecaster lose to the in-family point forecast?*
  Because 3GPP traffic has different burst shapes. Without retraining, the
  forecast is miscalibrated. It still beats all reactive controllers, which
  matches property 4: graceful degradation.
- *How much of the remaining loss is forecast error?* The oracle + KKT row
  (same rule, perfect forecast) shows that 24–40 % of the remaining loss at
  high load is forecast error; the rest is the cost of committing budgets in
  advance.
- *Does our rule also win unweighted on Family G?* Yes. Unlike Family S,
  on Family G it is also best under the unweighted violation ratio.
- *Is this real data?* No: it is generated from the 3GPP evaluation models,
  which are what the industry uses to compare proposals. Real operator traces
  are future work.
- *What is FTP Model 3?* A 3GPP traffic model where files of 0.5 MB arrive
  as a Poisson process; it is the standard model for bursty broadband
  downloads.

---

## Slide 28 — B1, robustness, operating range and the A × B experiment  *[0:45]*

Three robustness checks.

*[Left figure.]* **Miscalibration.** We shift every quantile level of the
forecast by epsilon on purpose. Under-reserving is absorbed by lambda, and
even at plus 0.3 the rule, 9.45 percent, still matches the point forecast,
9.46. That is property 4 in practice.

*[Middle table.]* **Interval and delay.** At a 2, 5 and 10 millisecond
interval we beat both reactive and point-forecast control, and at 2
milliseconds we even beat the oracle. With older telemetry the margin over
reactive control shrinks: minus 16 percent at zero delay, down to minus 2
percent at 5 milliseconds.

*[Right table.]* And here **Part A meets Part B**. Same user traffic; only the
BFP width changes, and with it the load. At 6 bits the load is 0.44, and
almost nothing is lost whatever you do. At 9 bits the load is 0.65, and our
rule **halves** the loss of reactive control.

**Compression sets the regime; allocation decides the loss inside it. Near
full load no split helps, and Part A must bring the load down.**

**Likely questions**

- *Where does the rule fail?* At a 20 ms interval (five times the LL
  deadline) reserving the LL peak for the whole interval over-reserves and
  proportional control wins. With 5 ms old telemetry it is a near tie. At
  loads of about 0.86 and above, proportional is slightly better, and at
  about 1.0 nothing helps.
- *How can you beat the oracle at T = 2 ms?* The oracle is a perfect
  single-number forecast fed to water-filling, not the optimal policy. Our
  rule's backlog-first, risk-equalising split is better than water-filling
  when intervals are short.
- *What happens at 12 and 14 bits?* The load becomes 0.86 and 0.99. At 0.86
  the proportional controller is slightly better; at 0.99 no allocation rule
  helps.
- *Why not adapt the compression width per cell dynamically?* That is the
  natural joint knob, and it is in our future work: choose BFP width and
  capacity share together every interval, trading signal quality for load.
- *Why do the sweep numbers differ from slide 25 (7.71 vs 8.00)?* The
  sweeps used 10 seeds instead of 20, so the averages differ slightly. Within
  each sweep every controller uses the same seeds.

---

## Slide 29 — B2, LCQT: a Bayesian, link-aware quantile Transformer  *[0:45]*

B2 asks: can a much better forecaster help? We built **LCQT**, a link-aware
quantile Transformer, as a drop-in replacement for the trees, with the same
target, quantile levels and seeds.

*[Walk the blocks left to right.]* Each cell's last 352 slots are cut into 16
patches, and each patch carries its own r-star, mean and maximum. A
two-layer Transformer encodes them. A FiLM layer conditions the network on
deadline and priority, so one network serves both classes. Cross-cell
attention lets each cell look at the other seven on the same link. The head
outputs six quantiles that are guaranteed not to cross. A Bayesian mixture of
3 trained seeds times 8 dropout samples gives the final distribution. And a
differentiable KKT layer lets us train through the allocation itself.

*[Left bullets.]* One detail matters: we pass the rule the **mixture** of the
24 distributions, not the average of their quantiles. So when the samples
disagree, the cell gets a wider margin. It has 63 thousand parameters and
trains in about 6 minutes on a CPU.

*[Right table.]* Pinball loss improves 4.5 percent over the trees, with a
90 percent interval that is 8 percent narrower at higher coverage. It is the
best-calibrated model under the held-out shift. And with the B1 rule it
improves on the trees on all 20 test seeds at low, moderate and high load.

**Our best-calibrated forecaster; combined with B3 it gives the best results
of the project.**

**Likely questions**

- *What is new in LCQT?* Each block is prior art: PatchTST patches,
  iTransformer-style attention across variables, TFT-style multi-quantile
  output, FiLM, deep ensembles, MC dropout. The six modifications for the
  shared link are ours: deadline-aware patch tokens, deadline/priority FiLM,
  cross-cell attention over the cells on one link, a non-crossing quantile
  head, the Bayesian mixture fed to the rule, and the differentiable KKT
  layer. We found no paper that combines them for a shared,
  deadline-constrained link; that is "none found in our search", not a proof.
- *How big are the closed-loop gains?* With the B1 rule: −20.8 % at low,
  −6.1 % at moderate and −1.4 % at high load, each on 20/20 seeds. Under flash
  crowds and the shift the difference is not significant.
- *Did the cross-cell attention help?* No. Removing it changed neither
  forecast quality nor closed-loop results beyond noise. The patch Transformer
  carries the main gain; the Bayesian mixture adds a small but consistent
  amount.
- *How does the differentiable KKT layer work?* Forward: bisection finds λ*.
  Backward: the implicit function theorem on the binding constraint
  Σrᵢ = C gives ∂λ*/∂q, implemented as one Newton step. It matches the numpy
  allocator to 10⁻⁶.
- *Did decision-focused training help?* Not on test. It helped under flash
  crowds (−1.2 %) but hurt at low load (+14 %), because its one-horizon loss
  ignores how queues carry over between intervals.
- *What is pinball loss?* The loss for training a model to predict a chosen
  quantile; it penalises under- and over-prediction asymmetrically.
- *Was B2 run on all three families?* Only on Family S. That is a stated
  limitation.

---

## Slide 30 — B2, uncertainty-aware and explainable by design  *[0:35]*

Two properties make this forecaster more than a black box.

*[Left block, panels a and b.]* It is **uncertainty-aware**. The 24 posterior
samples let us separate **epistemic** uncertainty, where the model itself is
unsure, from **aleatoric** uncertainty, the randomness of the traffic. Under
the held-out shift, the model's own uncertainty on low-latency cells rises 30
percent, from 0.086 to 0.112. So the model knows when traffic is unfamiliar,
the mixture widens, and the link reserves more where it is less sure.

*[Right block, panel c.]* It is **explainable**. A counterfactual: relabel a
low-latency cell as broadband, and its 95 percent quantile drops 18 percent;
relabel a broadband cell as low-latency, and it rises 26 percent. So it
reserves for deadline and priority, as intended.

*[Panel d.]* Attribution: the newest 4 of the 16 history patches carry 41
percent of the low-latency upper quantile, and the summary features 19
percent.

**And every budget still reads as backlog plus a quantile at risk one minus
lambda over w.**

**Likely questions**

- *What is the difference between epistemic and aleatoric uncertainty?*
  Aleatoric is randomness in the traffic itself; more data will not remove
  it. Epistemic is the model not knowing, for example on traffic it has never
  seen; more data or a better model reduces it.
- *What is MC dropout?* Run the network several times with random neurons
  switched off; the spread of the outputs estimates epistemic uncertainty.
  Ensembles do the same with independently trained copies. We use both:
  3 seeds × 8 passes.
- *How is the attribution computed?* Gradient × input on the LL 95 %
  quantile, summed over each patch.
- *Is it fast enough for a 10 ms loop?* LCQT alone takes 2.7 ms per
  decision, faster than the trees. With the Bayesian layer, 24 forward passes,
  it takes 17–21 ms in Python, so it needs batching or a compiled
  implementation; that is in our future work.
- *Does more uncertainty under shift actually fix the shift?* Partly. It
  moves coverage towards nominal (LL 95 % quantile coverage 0.855 → 0.873)
  but cannot remove the under-coverage completely, because the shift is
  outside the training data.

---

## Slide 31 — Towards B3: we implemented all three POMDP solution families  *[0:45]*

*[Left side.]* Formally, the real problem is a POMDP: hundreds of continuous
state dimensions, an unknown traffic law, and actions held for 20 slots. It
cannot be solved exactly. There are three classic ways to approximate it,
and we implemented all three on the same simulator and forecaster. One, a
one-step **stochastic program**: our KKT rule. Two, **Lyapunov drift**:
predictive MaxWeight, which serves cells in order of queue pressure. Three,
**policy search**: a three-parameter policy learned from reward with the
cross-entropy method, CEM.

We also derived theory for r-star under Markov traffic, including a pathwise
"shortfall sandwich" that bounds the dropped volume from both sides. The
bounds are valid but 25 to 100 times too conservative, which argues for
learning the distribution rather than computing it.

*[Right table.]* And the honest result: each family wins in a different
regime. Policy search is best in 6 of 10 scenarios, Lyapunov drift in 3.
Re-tuning the weight inside our rule barely helps.

*[Green box.]* The lambda diagnostic shows why. At high load, lambda is at or
above the broadband weight in 50 to 58 percent of intervals, so every
broadband cell already sits at its lowest quantile; per-cell reservation
leaves capacity idle that back-pressure would use.

**The gap is structural, not a constant we forgot to tune. So B3 puts all
three families into one learned policy class.**

**Likely questions**

- *What is MaxWeight / back-pressure?* A classic scheduler that serves the
  queues with the largest pressure, roughly priority times queue length. It
  is provably throughput-optimal in Lyapunov drift theory. Predictive
  MaxWeight (Huang et al., 2016) adds the forecast median for the next few
  horizons to the queue length.
- *What is the cross-entropy method?* A simple derivative-free policy-search
  method: sample parameters, keep the best fraction, refit the sampling
  distribution, repeat. It is a small analogue of a deep-RL xApp.
- *Why not deep reinforcement learning, e.g. PPO?* CEM over a small,
  interpretable policy class was enough to find the structural gap. A PPO
  xApp baseline is the first item of future work, with BPN as its structured
  policy and the KKT rule as a safe fallback.
- *What did the CEM policy learn?* Separate quantile levels per class, about
  0.8 for LL and 0.5 for eMBB, with weighted water-filling. In effect it
  decouples the two classes' levels instead of tying them through one λ.
- *What is the shortfall sandwich?* For any traffic and constant rate r:
  (D+1)(r* − r)⁺ ≤ dropped volume ≤ Σ(aₜ − r)⁺. So the newsvendor objective is
  a lower bound on what is actually dropped.
- *Doesn't this undermine B1?* It tells us where B1 is weak and why. B1
  still wins all 10 scenarios against the original comparison set, with
  nothing to tune, and it survives inside B3 as stage 2.

---

## Slide 32 — B3 (final): the back-pressure newsvendor (BPN)  *[0:50]*

*[Left table.]* First, the diagnosis at high load. The KKT rule over-protects
low-latency cells, starves broadband at 12.3 percent violations, and has the
lowest utilisation, 72.2 percent. The reason: **a budget is a per-cell cap**,
so capacity reserved for a low-latency cell's upper quantile and not used is
lost. Back-pressure wastes less, but it ignores deadlines and uncertainty.

So the idea: **fill a base in back-pressure order, then spend the leftover on
newsvendor margins.**

*[Stage 1.]* Stage one builds a base for each cell. Its base rate mixes
MaxWeight's "drain the queue" rate with our deadline-aware backlog rate; the
parameter a sets the mix. It adds a class-level forecast quantile. If there is
a shortage, it is shared in proportion to a pressure score raised to a power
eta. With eta equal to zero, that is reservation; with large eta, it is strict
back-pressure order.

*[Stage 2.]* Stage two spends whatever capacity is left with the KKT rule,
exactly as in B1, so margins go only where the forecast is wide.

*[Gold box.]* The key property: with the right parameters, BPN becomes
**exactly** predictive MaxWeight, or **exactly** the CEM policy; we verified
both in unit tests. Its 8 parameters are learned by CEM on training seeds,
starting from both baselines' optima, and we re-tuned the baselines with the
**same search** for equal effort.

**One policy class that contains both strongest baselines: the search can
only match or beat them.**

**Likely questions**

- *Isn't it unfair to compare 8 tuned parameters with baselines?* The
  baselines were re-tuned with the same CEM search, the same budget and the
  same training seeds, and both are exact special cases of BPN. Test seeds
  were never used for tuning.
- *What are the 8 parameters?* The base quantile levels for LL and eMBB, the
  class share weight for LL, the look-ahead ℓ, the stage-2 LL weight, the mix
  a, the sharing exponent η and the margin μ.
- *What is the difference between BPN v1 and v2?* v1 (6 parameters) always
  used strict back-pressure in stage 1, so it cannot express reservation and
  loses on the 3GPP family. v2 adds η and μ, so it also contains the
  reservation policy and wins everywhere. On Family S, v1 is marginally better
  (5.23 vs 5.32 % at high load), but v2 is the one that generalises.
- *Is BPN optimal?* There is no optimality proof. Only stage 2 inherits the
  one-interval optimality of the KKT rule.
- *"Can only match or beat them": on test too?* On the training cost, by
  construction. On test it is an empirical result, which is why we report
  paired test statistics on the next slide.
- *What utilisation does BPN reach?* 76.1 % at high load, against 72.2 % for
  the KKT rule and 75.5 % for predictive MaxWeight.

---

## Slide 33 — B3 (final): BPN beats the best baseline in 10/10 scenarios  *[0:40]*

*[Left figure.]* Each bar is the violation ratio relative to the best
baseline in that scenario; below the line means better. Grey is the B1 KKT
rule, blue is BPN version 1, green is BPN version 2.

*[Right table.]* "Best baseline" means the better of predictive MaxWeight and
the CEM policy in each scenario, each in its best tuning with the same search
budget. BPN version 2 is better in **all ten scenarios**: from 3.4 percent at
3GPP high load up to 25 percent at synthetic moderate load. It wins on 20 of
20 seeds in eight scenarios, 19 at 3GPP high, and 15 at synthetic low load,
where violations are tiny. All p-values are at most 0.024 after Holm
correction.

**BPN wins every scenario by 3 to 25 percent, on synthetic, 3GPP and Markov
traffic, including held-out shifts.**

**Likely questions**

- *Why only 15/20 seeds at S low?* At low load violations are tiny (around
  0.1 %), so a few seeds are essentially ties. The mean difference is still
  significant.
- *How close is BPN to the oracle?* At S high, within 6–10 % of the
  oracle-informed KKT rule (5.23 vs 4.77 %).
- *Does BPN generalise to a family it was not trained on?* Its parameters are
  learned per family. Cross-family transfer is future work and a stated
  limitation.
- *Which forecaster is used here?* The same GBM forecaster for BPN and the
  baselines, so the comparison isolates the decision rule. With the Bayesian
  LCQT from B2, BPN improves further (5.05 % at S high).

---

## Slide 34 — B3 (final): what the BPN policy learned  *[0:30]*

*[Left table.]* The learned parameters are interpretable. On bursty Family S
the search chooses eta equal to 6, strict back-pressure. On 3GPP and Markov
traffic, with long FTP files and XR frames, it chooses eta equal to zero,
reservation.

*[Right bullets.]* So the search **recovered the regime map by itself**:
back-pressure for short bursts, reservation for long ones. With the Bayesian
Transformer it reaches 5.05 percent at synthetic high load, within 6 to 10
percent of the oracle-informed rule, and it takes 2.2 to 3.5 milliseconds per
decision, well inside the 10 millisecond interval.

*[Figure.]* The figure shows the same map from the sweep: back-pressure wins
at 10 to 20 millisecond intervals, reservation at short ones.

**BPN learns when to reserve and when to back-pressure, and that choice is
readable from its parameters.**

**Likely questions**

- *Why does back-pressure win for short bursts and reservation for long
  ones?* A short burst may be over before the interval ends, so capacity
  reserved for it is often wasted; serving queues as they build is better. A
  long burst (a whole FTP file, an XR frame) persists through the interval, so
  reserving for it in advance pays off.
- *Is 2.2–3.5 ms fast enough on a real O-DU?* It is Python on a CPU and fits
  the 10 ms interval. A compiled implementation would be much faster; the
  allocation itself is microseconds, most of the time is the forecaster.
- *What would deployment look like?* BPN as an xApp in the near-RT RIC,
  setting per-cell budgets every 10 ms over E2, with the KKT rule as a safe
  fallback, and later as the structured policy inside a PPO agent.
- *What is still missing?* Real per-cell traces, a deep-RL (PPO) baseline,
  sweeps of BPN over interval, delay and load (so far only 10 ms and 1 ms),
  cross-family transfer, and an optimality proof.

---

# Cross-cutting questions (can come at any time)

- **What is the single most important idea of Part B?** Forecast the
  deadline-feasible rate r* as a range, and split the link so every cell
  carries the same priority-weighted risk. B3 then adds back-pressure for the
  capacity that reservation would waste.
- **How do Part A and Part B connect?** The cost of one resource-block layer,
  β, is set by the compression width. Compression moves the system along the
  load axis; the allocation rule decides the loss at that load.
- **What is new, honestly?** None of the ingredients alone. The
  contributions are: using r* as the forecast target in shared fronthaul,
  the risk-equalising KKT split with its four properties, the shared-link
  Transformer with a Bayesian mixture and differentiable KKT layer, and BPN as
  one policy class that contains the strongest baselines, all with a fair,
  paired evaluation on three traffic families.
- **Closest prior work?** Lagén et al. (2022): shared 7-2x links with
  reactive per-slot compression control, no forecast. Bega et al., DeepCog and
  AZTEC: forecast-driven capacity allocation with single-number forecasts and
  no per-cell deadlines. Huang et al. (2016): predictive back-pressure, our
  strongest baseline.
- **What are the main limitations?** Simulation only (three families);
  simplified link (no switch queue, no HARQ, downlink only); no closed-loop
  optimality or stability proof; the B1 rule loses at T = 20 ms and very high
  load; B2 run on Family S only and too slow in Python with the Bayesian
  layer; BPN learned per family at one interval and delay.
- **Where is it published?** The B1 paper is submitted to NCC 2027. An
  11-page extended manuscript with the theory, three families and 19
  controllers is in `paper/extended/`.

## Numbers to have ready

| What | Number |
|---|---|
| Link | 25GE, C = 12.125 Mbit per 0.5 ms slot, sum of peaks = 2.44 C |
| Cells | 3 LL (D = 2 ms, w = 3), 5 eMBB (D = 10 ms, w = 1) |
| Decision | every T = 10 ms (20 slots), telemetry τ = 1 ms old |
| Cost per PRB-layer, BFP-9 | 3,387 bits; cell peak ≈ 7.4 Gbit/s |
| B1 vs point forecast (S) | −11 to −43 %, 20/20 seeds, p < 0.01 |
| B1 at S high | 8.00 % (point forecast 9.70, oracle 6.89) |
| B1 on 3GPP high load | 8.01 %, −31 % vs deadline-aware, −50 % vs reactive |
| A × B at load 0.65 | 1.96 % vs 3.90 % reactive (halved) |
| B2 forecast | pinball −4.5 %, 90 % interval −8 % narrower |
| B2 closed loop vs GBM | −20.8 / −6.1 / −1.4 % (low / mod / high), 20/20 seeds |
| B2 uncertainty under shift | LL epistemic spread +30 % (0.086 → 0.112) |
| CEM / pred. MaxWeight vs B1 | better in 6/10 and 3/10 scenarios |
| BPN at S high | 5.23 % (KKT 8.00, pred. MaxWeight 5.98, CEM 6.58, oracle 4.77) |
| BPN v2 vs best baseline | 10/10 scenarios, −3 to −25 %, all p ≤ 0.024 |
| Decision time (Python) | KKT + GBM 3.5 ms; BPN 2.2–3.5 ms |

For deeper answers, see Section 14 of `presentation/part_b_report.md` and
`presentation/PartB_study_guide.pdf`.
