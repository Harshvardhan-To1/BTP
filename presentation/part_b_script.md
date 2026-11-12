# Part B — Presentation Script

Word-for-word script for `presentation/part_b_final.pptx` (30 slides).
Every number matches the slides. Speaking at about 150 words a minute, the
full script runs about **25 minutes**. Timings per slide are in brackets.

How to use it:

- Text in normal type is what you say. Text in *[square brackets and italics]*
  is a stage direction: what to point at or when to click.
- **Bold** marks the one sentence per slide that must survive if you run short.
- A 15-minute cut is given at the end.

---

## Slide 1 — Title  *[0:30]*

Good morning. I am presenting Part B of our project, "Sharing One Fronthaul
Link Well".

In Part A we made the fronthaul data smaller by compressing it. Part B asks a
different question: when several cells share one link, and the link is too
small for all of their peaks at once, who gets to send how much?

**Part A makes the data smaller; Part B decides who may send how much when the
link is too small for everyone.**

---

## Slide 2 — Part B at a glance  *[1:00]*

Here is the map of the talk. Part B was built in three steps, and each step
answers the question the previous one raised.

*[Point to B1.]* B1 is our main method, the KKT newsvendor rule. We forecast
each cell's need as a range, not a single number, and split the link so that
every cell carries the same weighted risk. It was the best of twelve
controllers on two traffic families, and it is our NCC 2027 submission.

*[Point to Extended study.]* After the submission we went further. We added
theory, a third traffic family, and two stronger controllers. Honestly, those
two controllers beat our rule in nine out of ten scenarios.

*[Point to B2.]* So in B2 we asked: is that because our forecast is not good
enough? We built a Bayesian Transformer forecaster. It is the best version of
our rule, but the gain is small. That told us the gap is in the structure of
the decision, not in the forecast.

*[Point to B3.]* So in B3 we changed the structure. The back-pressure
newsvendor contains both of the strongest baselines as special cases, and it
beats them in all ten scenarios across three traffic families.

**Keep the structure, learn only what is uncertain — then fix the structure
where it is wrong.**

---

## Slide 3 — The problem  *[1:00]*

The setting. Eight cells share one link. Three are low-latency cells — "LL" —
with a 2 millisecond deadline and priority weight 3. Five are eMBB, ordinary
broadband, with a 10 millisecond deadline and weight 1.

They share one 25-gigabit Ethernet link. After 3 percent for control traffic,
that is about 12 megabits per half-millisecond slot. The sum of the cells'
peaks is 2.44 times the link. That is deliberate: operators rely on cells not
peaking at the same time — statistical multiplexing.

Every 10 milliseconds a coordinator gives each cell a budget, and that budget
is held for the whole interval. The coordinator only sees telemetry that is 1
millisecond old. It never sees the future. Any bit that waits longer than its
deadline is dropped, and that is a violation.

*[Point to the right box.]* Why decide in advance instead of every slot?
Because the near-real-time RIC control loop is at least 10 milliseconds,
switch shaping is not reconfigured every slot, and the DU schedulers of
different cells cannot coordinate inside the sub-millisecond pipeline.

So the question is: given a forecast range of each cell's need, how should we
split the link?

**When bursts coincide, someone must lose data. The controller decides who.**

---

## Slide 4 — System model  *[1:00]*

Fronthaul load follows the scheduled resource blocks, not the user bits.

*[Top-left box.]* This is the cost of one resource block on one antenna layer
for one slot. This is exactly where Part A enters: b is the mantissa width of
the block floating-point compression. At 9 bits it is about 3,400 bits. A
full cell — 273 resource blocks, 4 layers — peaks at about 7.4 gigabits per
second.

*[Bottom-left box.]* The demand of a cell is the user bits divided by the
spectral efficiency, times that cost. That is why two cells with the same user
traffic can differ two to three times in fronthaul load. The budgets always
add up to at most the link capacity, so the link itself never queues.
Congestion shows up as queues at the DU, and bits are dropped after their
deadline.

*[Right box.]* Our main score is the priority-weighted violation ratio, V_w.
A dropped LL bit counts three times; an eMBB bit counts once. Lower is better.
We fixed this metric before doing any tuning, and we also report the
unweighted ratio, utilisation, delay and fairness.

**Two cells with the same user traffic can differ two to three times in
fronthaul load.**

---

## Slide 5 — Section: B1, the KKT newsvendor rule  *[0:10]*

The first part: the KKT newsvendor rule. Three key ideas: forecast the right
quantity, forecast it as a range, and split at equal risk.

---

## Slide 6 — Key idea 1: the deadline-feasible rate r*  *[1:00]*

The first idea is to forecast the right quantity. We call it r-star: the
smallest constant rate at which no bit misses its deadline.

With a long deadline, r-star is close to the average rate, because you can
smooth bursts out. With a short deadline, it is close to the peak burst rate.

A small example. One burst of 8 units, average 1 per slot. If the deadline is
1 slot, you need a rate of 8 divided by 2, which is 4. If the deadline is 7
slots, 8 divided by 8 — a rate of 1 is enough.

*[Right box.]* Every deadline-aware controller asks for the same thing: the
queued backlog divided by the remaining slack, plus r-star for what has not
arrived yet. Controllers differ only in how they estimate r-star and how they
split a shortage.

For our 2 millisecond cells, r-star is often two to three times the mean, and
it is skewed to the right.

**A single number is a poor basis for reserving a skewed quantity, so we
forecast a range.**

---

## Slide 7 — Key idea 2: a quantile forecaster  *[0:50]*

The second idea: forecast a range. We train six gradient-boosted tree models,
one for each quantile level — 5, 25, 50, 75, 90 and 95 percent.

The target is r-star of the next interval, divided by the cell's peak. The 28
features come only from the past: averages, recent slots, recent r-star values,
spectral efficiency and the deadline. Training takes 12 seconds on a CPU. The
training, validation and test seeds never overlap.

*[Point to the table.]* It is well calibrated: the 5, 50 and 95 percent
quantiles cover 5.6, 50.7 and 94.9 percent of the data. Its median error is
37 percent, against 52 percent for simply repeating the last value.

**Well calibrated, cheap, and CPU-only.**

---

## Slide 8 — Key idea 3: the KKT rule  *[1:30]*

The third idea is how to split the link. This is the heart of B1.

*[Top box.]* For one interval we maximise the expected weighted amount of need
that is served, under the forecast, subject to the budgets fitting in the
link. This is a constrained newsvendor problem. It is concave and separable,
so the KKT conditions give the global optimum in closed form.

*[Middle box.]* The solution: each cell gets its backlog plus a quantile of
its forecast. The quantile level is 1 minus lambda over its weight. Lambda is a
single price of capacity, the same for all cells. We find it by bisection so
the budgets add up to the link. If the link is not full, lambda is zero and
everyone gets what they ask for. For eight cells this takes tens of
microseconds.

*[Right box.]* A toy example. Suppose lambda comes out at 0.6. An LL cell,
weight 3, is funded to 1 minus 0.6 over 3 — its 80 percent quantile. An eMBB
cell, weight 1, is funded to its 40 percent quantile.

So a cell with a wide forecast or high priority gets more margin, and a cell
with a confident forecast gets about its median.

**Every cell is cut at the same weighted risk: the margins are derived, not
tuned.**

---

## Slide 9 — Properties and the control loop  *[1:00]*

The rule has four properties, all proved and checked by unit tests.

One, feasibility: whatever the forecast says, the link is never overloaded.
Two, equal weighted risk: every cell ends up with the same weighted
probability of running short. With a point forecast this collapses to a simple
priority fill. Three, backlog first: bits already queued are funded before
uncertain future demand of equal or lower weight. Four, if the forecast is
miscalibrated by some amount epsilon, the loss grows only linearly in epsilon —
so it degrades gently.

*[Walk the loop left to right.]* The loop every 10 milliseconds: take the
1-millisecond-old state, build 28 features per cell, predict six quantiles,
run the KKT rule, hold the budgets for 10 milliseconds, and the DU queues
drain or drop.

**These are properties of one interval. We do not claim closed-loop
optimality.**

---

## Slide 10 — Baselines and protocol  *[1:00]*

We compare against seven implementable baselines plus oracles that see the
true future.

*[Point down the table.]* Static equal split; reactive proportional;
MaxWeight; a deadline-aware reactive controller; and two important ablations.
The point forecast uses the same GBM model but only its median — so it tests
whether the range matters. The fixed global quantile uses one quantile level
for all cells — so it tests whether "just use a high quantile" is the trick.
We also have a no-ML version that takes quantiles from a window of recent
intervals. Every baseline was tuned on validation seeds.

*[Bottom boxes.]* Two independent traffic families. Family S is synthetic and
bursty, with five scenarios from low load to flash crowds and a held-out
distribution shift. Family G is built only from 3GPP models: the standard
channel model, FTP traffic for eMBB and XR video for low latency.

**Twenty test seeds of 10 seconds each, paired bootstrap confidence intervals,
and Holm-corrected Wilcoxon tests.**

---

## Slide 11 — B1 result, Family S  *[1:00]*

The main B1 result. Each number is the weighted violation percentage, averaged
over 20 test seeds. Lower is better.

*[Point to the "Proposed" row.]* Our rule is the best implementable controller
in all five scenarios. At high load it is 8.0 percent, against 9.7 for the
point forecast and 9.2 for reactive proportional.

*[Right box.]* The spread across seeds is mostly shared burst timing, so the
fair comparison is seed by seed. Against the point forecast we reduce
violations by 11 to 43 percent, and against the fixed quantile by 22 to 54
percent — on all 20 out of 20 seeds, p below 0.01.

One weak spot, and I want to say it myself: against reactive proportional
under flash crowds, the gain is only 4 percent, 16 out of 20 seeds.

**Best implementable controller in all five scenarios.**

---

## Slide 12 — Where the gain comes from  *[0:40]*

Where does the gain come from? *[Point to the figure.]* Controllers that ignore
deadlines starve the LL cells — 14.7 and 20.6 percent LL violations. Every
deadline-aware controller protects LL, but pays for it with eMBB.

Among the deadline-aware controllers, ours loses the least eMBB traffic, 12.3
percent, and uses the link the most, 72.2 percent. That is because it adds
margin only where the forecast is wide. One global quantile level wastes about
a third of the allocation.

**Margin only where the forecast is wide.**

---

## Slide 13 — Ablations  *[0:50]*

Which piece carries the gain?

*[Row by row.]* A range instead of a single number: 11 to 43 percent better.
A per-cell level set by the link instead of one global level: 22 to 54 percent
better. GBM instead of the no-ML window quantiles: 7 to 37 percent better, but
only 2 percent under shift — so most of the gain is the rule itself. And
online conformal calibration actually hurt, because in a shared link an LL
miss is caused by how the shortage was split, not by forecast bias.

*[Bottom box.]* Family G, the 3GPP traffic, reproduces the result: 8.01
percent at high load, 11 percent better than the point forecast on every seed.

**Machine learning is useful but not necessary: the r-star target and the KKT
split do most of the work.**

---

## Slide 14 — Honest caveats and operating regime  *[1:00]*

I want to state the caveats before you ask.

*[Top table.]* First, the gain is a priority trade. With LL weight 1 — every
bit equal — reactive proportional is as good or slightly better. Our rule
needs an LL weight of about 2 to 3 to pay off.

*[Second table.]* Second, the control interval. At 2, 5 and 10 milliseconds we
win. At 20 milliseconds we lose — the rule works for intervals up to a few
times the shortest deadline, with fresh telemetry. These sweeps used 10 seeds,
which is why you see 7.71 here instead of 8.00.

*[Bottom box.]* Third, the link to Part A. Compression with 6, 9, 12 and 14
bits gives loads of 0.44, 0.65, 0.86 and 0.99. Allocation matters between
about 0.5 and 0.8. At a load of 1, nothing helps.

**Compression sets the regime; allocation decides the loss inside it.**

---

## Slide 15 — Section: Extended study  *[0:10]*

After the NCC submission we extended the work for the full manuscript: theory,
a third traffic family, and stronger controllers.

---

## Slide 16 — Stronger controllers exist  *[1:10]*

The real problem is a partially observed Markov decision process — and it is
intractable. So we implemented three families of approximations. One, a
one-step stochastic program — that is our KKT rule. Two, Lyapunov drift —
predictive MaxWeight, which serves cells in order of queue pressure. Three,
direct policy search — a three-parameter policy tuned with the cross-entropy
method, CEM.

We added Family M, Markov-modulated traffic, and we linked r-star to the
classical effective bandwidth. Those bounds are valid but 25 to 100 times
loose, which argues for learning rather than formulas.

*[Point to table.]* And here is the honest result. CEM and predictive
MaxWeight beat our rule in nine of ten scenarios. At S high: 8.00 for us,
6.15 for predictive MaxWeight.

We checked whether re-tuning our weights would close the gap. The link is full
almost every interval, and eMBB is already at its lowest quantile, so
re-tuning gains only 1 to 4 percent.

**The gap is structural, not a constant we forgot to tune.**

---

## Slide 17 — Section: B2, a Bayesian Transformer forecaster  *[0:15]*

So B2 asks: can a better forecaster close that gap? The short answer is:
mostly not — and that answer is useful.

---

## Slide 18 — LCQT  *[1:10]*

We built LCQT, a link-aware cross-cell quantile Transformer. It is a drop-in
replacement for the GBM forecaster.

*[Walk the blocks left to right.]* The recent traffic is cut into 16 patches,
each carrying its own r-star, mean and max. A two-layer Transformer encodes
them. A FiLM layer conditions on deadline and priority, so one network serves
both classes. Cross-cell attention lets each cell look at the other seven on
the same link. The output head produces six quantiles that cannot cross. And a
Bayesian mixture — three trained seeds times eight dropout samples — gives the
final predictive distribution.

*[Bottom box.]* We also built a decision-focused version, DF-LCQT. We made the
KKT rule differentiable, using the implicit-function gradient for lambda, so
the network can be trained directly on the violations it causes, not only on
forecast error.

63 thousand parameters, about 6 minutes of training on a CPU, same seeds and
target as the GBM.

**Each block is prior art; we found no paper that combines them for a shared
link.**

---

## Slide 19 — B2 forecast quality  *[0:50]*

Is it a better forecaster? Yes — modestly.

*[Point to LCQT row.]* Pinball loss improves by 4.5 percent over GBM, and the
90 percent interval is 8 percent narrower while covering more. The cross-cell
layer and the priority-weighted loss gave no measurable forecast gain.

*[Right columns.]* Under distribution shift the Bayesian layer helps
calibration: the LL 95 percent quantile coverage rises from 0.855 to 0.873.
But it cannot remove the under-coverage completely. The decision-focused model
gives up some accuracy on purpose.

**A better forecast — but only modestly better.**

---

## Slide 20 — B2 closed loop  *[1:00]*

What happens in the closed loop?

*[Point to "Bayesian LCQT + KKT".]* The Bayesian Transformer with the KKT rule
is the best version of our rule. Seed by seed, it beats GBM on every one of 20
seeds at low, moderate and high load: 21, 6 and 1.4 percent better. Under
flash crowds and shift, the difference is not significant.

*[Point to CEM and predictive MaxWeight rows.]* But CEM and predictive
MaxWeight are still 14 to 28 percent better. A better forecast moved us only
a little, so forecasting is not what separates us from them.

**Best KKT variant, but the strongest baselines stay 14 to 28 percent better:
the gap is structural.**

---

## Slide 21 — B2 honest assessment  *[0:40]*

What improved: the Bayesian Transformer beats GBM on every seed at low to high
load and never loses significantly; it has the best calibration under shift;
without the Bayesian layer it is even cheaper per decision than GBM; and the
differentiable KKT layer works and matches the reference to one in a million.

What did not: the gain at high load is small; the decision-focused gain on
validation did not transfer to test; the Bayesian layer takes 17 to 21
milliseconds in Python, longer than the 10 millisecond interval, so it needs
a compiled implementation; and we ran it on Family S only.

**Next: keep the forecaster, change the decision structure. That is B3.**

---

## Slide 22 — Section: B3, the back-pressure newsvendor  *[0:10]*

B3 changes the decision rule, not the forecaster. We build one policy class
that contains both of the strongest baselines.

---

## Slide 23 — Why the KKT rule loses  *[1:00]*

First, why does our rule lose to back-pressure?

*[Point to the KKT row.]* A budget is a per-cell cap. If we reserve capacity
for a 2 millisecond cell's upper quantile and the burst doesn't come, that
capacity is simply lost. So the KKT rule over-protects LL — 3.4 percent LL
violations — starves eMBB at 12.3 percent, and has the lowest utilisation,
72.2 percent.

*[Point to Pred. MaxWeight row.]* Back-pressure fills the link in queue order
using median demands. It wastes less, so violations are balanced at about 6
percent each. But it ignores deadlines and uncertainty.

*[Point to BPN rows.]* Combining the two gives our new controller — 5.2 to 5.3
percent, close to the oracle's 4.77.

**The idea: fill a base in back-pressure order, then spend the leftover on
newsvendor margins.**

---

## Slide 24 — BPN: how it works  *[1:30]*

The back-pressure newsvendor decides in two stages every 10 milliseconds.

*[Stage 1.]* Stage one builds a base. Each cell's base demand mixes
MaxWeight's drain rate with our deadline-aware backlog rate — the parameter
"a" sets the mix — plus a base quantile per class. If there is a shortage, it
is shared according to a pressure score raised to a power eta. With eta equal
to zero, it is a class-weighted water-fill — that is reservation. With large
eta, it is strict back-pressure order.

*[Stage 2.]* Stage two spends whatever capacity is left using the KKT rule,
exactly as in B1.

The important point: with the right parameters this policy becomes exactly
predictive MaxWeight, or exactly the CEM policy. We verified that with unit
tests. So the search can only match or beat them. And to be fair, we re-tuned
both baselines with the same CEM search and the same budget, on training
seeds only.

*[Point to table.]* And the learned parameters make sense. On bursty Family S
the search picks eta equal to 6 — back-pressure. On 3GPP and Markov traffic,
with long FTP files and XR frames, it picks eta equal to 0 — reservation. The
search recovered the regime map by itself.

**One policy class with both strongest baselines inside it: the search can
only match or beat them.**

---

## Slide 25 — B3 result, Family S  *[1:00]*

The results on Family S.

*[Compare the GBM rows.]* With the same GBM forecaster, BPN beats both
strongest baselines in every scenario. At high load: 5.23 for BPN, against 5.98
for tuned predictive MaxWeight and 6.58 for CEM. That is within 6 to 10
percent of the oracle-informed KKT rule.

*[Point to the LCQT rows.]* And now the Transformer from B2 pays off more.
With the Bayesian LCQT forecaster, BPN reaches 5.05 at high load and 1.11 at
moderate load.

One detail: on Family S, version 1 is slightly better than version 2 at high
load. Version 2 is the one that also works on the 3GPP family — next slide.

**Same forecaster: BPN beats both baselines everywhere.**

---

## Slide 26 — B3 generalisation  *[0:50]*

Does it generalise to the other two families?

*[Point to BPN v1 on G.]* Version 1 lost on Family G. Its first stage is
always strict back-pressure, so it cannot represent reservation — and
reservation is what wins on long 3GPP bursts.

*[Point to BPN v2.]* Version 2 adds the sharing exponent, so it contains the
reservation policy, and that fixes it: 6.81 at G high against 7.05 for CEM,
and 3.62 at M high against 3.94.

**Version 2 is the one that generalises across all three families.**

---

## Slide 27 — BPN v2 vs the best baseline  *[0:50]*

Here is the head-to-head. "Best baseline" means the better of predictive
MaxWeight and CEM in each scenario, each in its best tuning.

*[Run down the column.]* BPN version 2 is better in all ten scenarios: from 3.4
percent at G high up to 25 percent at S moderate. It wins on 20 of 20 seeds in
eight scenarios, 19 of 20 at G high, and 15 of 20 at S low where violations are
tiny.

**Ten out of ten scenarios, three families, all p at most 0.024 after Holm
correction.**

---

## Slide 28 — What is claimable, what is still needed  *[0:50]*

What can we claim? BPN beats both strongest baselines, each in its best
tuning, in ten out of ten scenarios, with equal search effort on training
seeds only — and the baselines are special cases of our policy. The learned
eta is interpretable: it tells you when to reserve and when to back-pressure.
It takes 2 to 3.5 milliseconds per decision in Python.

What is still needed: real per-cell traces; a deep reinforcement learning
baseline, for example a PPO xApp; sweeps over interval, delay and load —
so far only 10 milliseconds and 1 millisecond; transfer of the learned policy
between families; and we have no optimality proof for the hybrid.

**A controller that beats the strongest baselines — with its limits stated.**

---

## Slide 29 — Part B summary  *[0:50]*

To summarise, reading the table top to bottom is the story of Part B.

B1, the KKT newsvendor rule, was the best of twelve controllers on two
families. The ablations showed that most of the gain is the r-star target and
the KKT split. It needs a real priority difference and a short interval. The
extended study found stronger controllers and showed the gap was structural.
B2's Bayesian Transformer is the best version of the KKT rule and confirmed
that. And B3, the back-pressure newsvendor, beats both strongest baselines in
all ten scenarios of three families, by 3 to 25 percent.

**Keep the structure, learn only what is uncertain — and let the search pick
the structure.**

---

## Slide 30 — Limitations and future work  *[0:50]*

Finally, what we do not claim. Everything is simulated, on three traffic
families. The link model is simplified: no switch queue, no HARQ, downlink
only. There is no closed-loop optimality or stability proof. The KKT rule's
flash-crowd gain over proportional is small. B2 was run on Family S only, and
the Bayesian layer is too slow in Python. And BPN is learned per family at one
interval and one delay.

Next steps: measured PRB traces, a PPO baseline and sweeps for BPN, transfer
across families, a compiled O-DU implementation, and — joining Part A and
Part B — using the compression width as a per-cell knob inside the allocation
rule.

Thank you. We are happy to take questions.

---

## 15-minute version

If time is short, keep the bold sentence only on these slides and skip the
rest of their text: 4, 7, 9, 12, 13, 18, 19, 21, 26, 28. Say the full text on
slides 2, 3, 6, 8, 11, 14, 16, 20, 23, 24, 27, 29 and 30 — they carry the
story and the numbers examiners ask about.

## Five numbers to have ready

| What | Number |
|---|---|
| Link oversubscription | peaks = 2.44 × capacity |
| B1 vs point forecast (Family S) | −11 to −43 %, 20/20 seeds |
| Stronger baselines vs KKT rule | better in 9/10 scenarios |
| Bayesian LCQT vs GBM (low / mod / high) | −21 / −6 / −1.4 % |
| BPN v2 vs best baseline | better in 10/10 scenarios, −3 to −25 %, p ≤ 0.024 |

For likely questions and answers, see Section 14 of
`presentation/part_b_report.md`.
