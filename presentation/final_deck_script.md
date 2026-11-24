# Final Deck — 12-Minute Presentation Script

Script for `presentation/BTP_final_deck.pdf` (title slide, 37 numbered slides,
thank-you slide, backup). Slide numbers below are the numbers in the
bottom-right corner of each slide. Every number in the script matches the deck.

The spoken text is about 1,630 words. At a relaxed 140 words a minute it
runs about **11 minutes 35 seconds**, and at 150 words a minute about 10:50.
The per-slide targets add up to **11:40**, leaving 20 seconds of slack. Each
slide has a target time and a running clock, so you can check whether you
are on schedule.

How to use it:

- Normal text is what you say. Text in *[italics in brackets]* tells you where
  to point or what to do.
- **Bold** marks the one sentence per slide to keep if you are running late.
- The script suggests a handover between the two speakers at Part B. Move
  it if you split the talk differently.
- Backup slides are not in the 12 minutes. Use them only for questions.

| Section | Slides | Time | Clock at end |
|---|---|---|---|
| Opening and background | Title, 1–6 | 2:15 | 2:15 |
| Part A | 7–17 | 4:05 | 6:20 |
| Part B | 18–34 | 4:30 | 10:50 |
| Wrap-up | 35–37, Thank you | 0:50 | 11:40 |

---

## Opening and background — Speaker 1

### Title — Fronthaul Load Management for B5G  *[0:10 · clock 0:10]*

Good morning. We are Harshvardhan Choudhary and Mayank Yadav, and our project,
guided by Dr. Sumit Gautam, is about managing the load on the fronthaul in
beyond-5G networks.

### Slide 1 — Roadmap  *[0:15 · clock 0:25]*

We start with the background, then Part A, which makes the data smaller and
the processing faster, and Part B, which shares one link between many cells.

**One idea runs through everything: keep the maths of the problem, and learn
only the part that is truly uncertain.**

### Slide 2 — Fronthaul, midhaul, backhaul  *[0:40 · clock 1:05]*

*[Point to each row of the table.]* An Open RAN network has three transport
links. The **fronthaul** joins the radio unit at the mast to the distributed
unit. It carries digitised radio samples, called IQ, for every antenna: 7 to
over 100 gigabits per second per cell, within about 100 microseconds.

The **midhaul** joins the distributed unit to the central unit over F1, and
carries user packets within a few milliseconds. The **backhaul** joins the
central unit to the 5G core and carries many cells' traffic, within about
10 milliseconds.

**The fronthaul has by far the highest rate and the tightest deadline, so it
decides how many cells an operator can afford.**

### Slide 3 — From D-RAN to Open RAN  *[0:20 · clock 1:25]*

Older networks sent samples at a fixed rate, even for an empty cell. The
O-RAN 7-2x split keeps the FFT in the radio unit and sends only scheduled
resource blocks, so load follows traffic and cells can share one link.

**Fronthaul load is scheduled resource blocks times bits per block. Both parts
of our project build on that.**

### Slide 4 — Why the fronthaul is the bottleneck  *[0:20 · clock 1:45]*

*[Red boxes.]* Two problems follow. Standard compression only halves the
data, and every half-millisecond slot the DU must invert matrices for 273
resource blocks, which takes numpy and LAPACK 3.2 milliseconds. And eight
cells share a link far smaller than their combined peak.

### Slide 5 — Our two levers  *[0:10 · clock 1:55]*

So we pull two levers. Part A makes the data smaller and the DU faster. Part B
splits the link before the traffic arrives.

### Slide 6 — Headline results  *[0:20 · clock 2:15]*

*[Walk the four cards.]* Results up front: 8.1 times compression, against 2
for the standard; a precoder from our own C library, 14 times faster than
numpy and LAPACK; 72 percent less fronthaul; and a final controller that wins
all ten scenarios.

---

## Part A — Speaker 1

### Slide 7 — Which IQ do we compress?  *[0:20 · clock 2:35]*

Each slot gives Y equals H times X plus noise: 64 antennas by 1200
subcarriers. The channel H is low rank and sparse in delay, but data symbols
hide that structure. So we compress channel-carrying IQ, the de-rotated
reference symbols, to minus 20 dB, the noise floor.

### Slide 8 — Two encoders with error bounds  *[0:30 · clock 3:05]*

*[Left.]* CSEE takes an inverse FFT across subcarriers, keeps the K
strongest delay taps and quantises them. Its error is bounded by truncation
plus quantisation, at order M N log N cost.

*[Right.]* RAS-BFP uses a randomised Hadamard sketch and a thin QR. Its error
is within one plus epsilon of the best rank-r error, at order r M N cost
instead of a full SVD.

**Both encoders give the operator a guaranteed worst-case error before a
single bit is sent.**

### Slide 9 — Compression results  *[0:15 · clock 3:20]*

*[Green rows.]* CSEE compresses 6.4 times and RAS-BFP 8.1 times, against 2
for the O-RAN standard, and RAS-BFP encodes three to four times faster than
SVD.

### Slide 10 — Developing a new ML-based inversion method  *[0:35 · clock 3:55]*

Our second big challenge was matrix inversion. Precoding needs a fresh
inverse every slot, and that repeated cost adds up. *[Steps 1 and 2.]* We
first tried direct methods, such as LU, QR, SVD and LAPACK, and a neural
network that predicts the inverse directly. Direct methods stayed too
expensive, and the learned inverse was slow and inaccurate. *[Steps 3 to 5.]*
So we focused on Newton–Schulz, an iterative method built only from matrix
multiplies, and trained networks to give it a better initial guess.
*[Chart.]* InverseNet-Ultra has the lowest mean latency and half LAPACK's
tail latency.

**Newton–Schulz with a good initial guess gives the best performance.**

### Slide 11 — RMT-WS  *[0:30 · clock 4:25]*

That became RMT-WS. *[Follow the flowchart.]* We equilibrate the Gram
matrix to remove the near–far spread. A moment-matched Marchenko–Pastur law
gives its eigenvalue interval in order K-squared work, with no
eigen-decomposition. A Chebyshev start is minimax-optimal on that interval,
and Newton–Schulz converges quadratically using only multiplies. Between
slots we warm start, and a two-probe residual certificate picks the steps or
falls back to a cold start.

### Slide 12 — Interval coverage and cost  *[0:10 · clock 4:35]*

*[Right table.]* To stay within 1 percent of the exact sum-rate we need 6
complex multiplies, where Neumann-type methods need more than 10.

### Slide 13 — Tracking at every speed  *[0:15 · clock 4:50]*

At walking speed we need 2.25 multiplies per slot. At 120 kilometres per
hour the certificate falls back to a cold start, with 24 times lower loss than
warm Gauss–Seidel.

### Slide 14 — Where should precoding run?  *[0:20 · clock 5:10]*

*[Arrow a.]* If the DU precodes, it sends 64 antenna streams, 118 gigabits per
second. *[Arrow b.]* If the radio unit precodes, we send 16 layers plus 8-bit
weights, 33 gigabits per second: 72 percent less, at 99.7 percent of the
sum-rate.

**But the weights must be refreshed every slot, so the precoder has to be
fast.**

### Slide 15 — Fused kernel design  *[0:25 · clock 5:35]*

So we wrote it in C with AVX-512 and OpenMP. *[Walk the pipeline.]* Each
resource block is one fused pass in L1 cache: Gram, Gauss–Jordan inverse,
weights, power scaling. Real and imaginary planes are split so complex
arithmetic vectorises, and no pivoting is needed because the Gram is positive
definite. Weight formation runs at half the AVX-512 peak.

### Slide 16 — Kernel results  *[0:10 · clock 5:45]*

*[Highlighted row.]* For 16 users and 64 antennas: 0.226 milliseconds,
against 3.2 for numpy and LAPACK.

**For the first time, the whole precoder fits inside the half-millisecond
slot.**

### Slide 17 — libcmat: our library vs LAPACK  *[0:35 · clock 6:20]*

These kernels form our library, libcmat. *[Left.]* LAPACK is tuned for one
large matrix, but the O-DU solves 273 small complex systems per slot, where
call overhead and separate memory passes dominate. libcmat batches them in
one call, with a fused precoder, a certified Newton–Schulz step, a batched
inverse and an FP16 path.

*[Right tables.]* The inverse is 10 to 14 times faster than LAPACK. The whole
precoder is 2.5 to 4 times faster on one core and 10 to 15 times on four, at
float64 accuracy.

**libcmat beats numpy and LAPACK at every tested size, and we are preparing
it for open-source release and publication.**

With that, I'll hand over to Mayank for Part B.

---

## Part B — Speaker 2

### Slide 18 — Decide budgets before traffic is seen  *[0:15 · clock 6:35]*

Thank you. Eight cells share one link: three low-latency cells with a
2 millisecond deadline and five broadband cells with 10, peaking at 2.44 times
the link. Every 10 milliseconds a coordinator sets budgets before seeing the
traffic.

### Slide 19 — System model and metric  *[0:15 · clock 6:50]*

Part A's compression sets the cost per resource block. *[Bottom box.]* We
score the priority-weighted share of bits that miss their deadline.

### Slide 20 — Part B in three steps  *[0:20 · clock 7:10]*

*[Walk left to right.]* Part B has three steps. B1 and B2 were our initial
experiments: a closed-form allocation rule, and an uncertainty-aware Bayesian
Transformer forecaster.

**B3, the back-pressure newsvendor, is our final submission. It combines the
strengths of all three in one learned policy.**

### Slide 21 — B1: forecast r-star  *[0:20 · clock 7:30]*

B1 forecasts r-star, the smallest constant rate at which no bit misses its
deadline: the worst burst over any window, divided by the window plus the
deadline. For 2 millisecond cells it is two to three times the mean, and
skewed.

**So we forecast a range, not a single number.**

### Slide 22 — B1: KKT newsvendor split  *[0:25 · clock 7:55]*

Gradient-boosted models predict six quantiles. Maximising expected weighted
service under the link constraint is concave and separable, so KKT gives the
global optimum. *[Red box.]* Each cell gets its backlog plus the quantile at
one minus lambda over its weight, with one shared price lambda.

**Every cell is cut at the same weighted risk; the margins come from the
maths, not from tuning.**

### Slide 23 — B1: proven properties  *[0:10 · clock 8:05]*

We proved feasibility, equal weighted risk, backlog first, and a loss that
grows only linearly with forecast miscalibration.

### Slide 24 — A fair evaluation  *[0:10 · clock 8:15]*

We test on three traffic families, synthetic, 3GPP and Markov, with identical
traces for all controllers, 20 test seeds and paired statistical tests.

### Slide 25 — B1: main result  *[0:20 · clock 8:35]*

*[Green row.]* B1 is the best implementable controller in all five
scenarios, cutting violations by 11 to 43 percent against a point forecast on
all 20 seeds.

### Slide 26 — B1: where the gain comes from  *[0:10 · clock 8:45]*

*[Plot.]* Reactive control is always one interval late. Our rule raises the
budget as soon as a burst begins, because that is when the forecast widens.

### Slide 27 — B1: ablations and 3GPP traffic  *[0:10 · clock 8:55]*

The ablations show the rule itself carries the gain. On standards-based 3GPP
traffic it is again the best, on all 20 seeds.

### Slide 28 — B1: robustness and A × B  *[0:15 · clock 9:10]*

*[Right table.]* Here Part A meets Part B: compression width moves the load,
and at 0.65 load our rule halves the loss of reactive control.

**Compression sets the regime; allocation decides the loss inside it.**

### Slide 29 — B2: Bayesian Transformer  *[0:20 · clock 9:30]*

B2 replaces the trees with LCQT, a link-aware quantile Transformer. *[Walk
the blocks.]* It encodes patches of history, conditions on deadline and
priority with FiLM, attends across cells, and outputs non-crossing quantiles.
*[Right.]* It is our best-calibrated forecaster, and it improves on B1 on
every test seed.

### Slide 30 — B2: uncertainty-aware and explainable  *[0:30 · clock 10:00]*

*[Left block.]* It is uncertainty-aware: 24 posterior samples separate model
uncertainty from traffic randomness. *[Panel b.]* Under the held-out shift its
uncertainty on low-latency cells rises 30 percent, so it knows when traffic is
unfamiliar and reserves more.

*[Right block.]* And it is explainable. *[Panel c.]* Relabel a low-latency cell
as broadband and its upper forecast drops 18 percent; the reverse adds 26.
*[Panel d.]* The newest four patches carry 41 percent of the decision.

### Slide 31 — Towards B3  *[0:20 · clock 10:20]*

We then implemented all three POMDP solution families: the stochastic
program, which is B1, Lyapunov drift, and cross-entropy policy search.
*[Green block.]* Each wins in a different regime, because per-cell reservation
leaves capacity idle that back-pressure would use.

### Slide 32 — B3: the back-pressure newsvendor  *[0:15 · clock 10:35]*

So our final design, BPN, has two stages. *[Stage 1.]* Fill a base in order
of queue pressure. *[Stage 2.]* Spend the leftover on KKT risk margins. Both
strongest baselines are exact special cases.

### Slide 33 — B3: wins 10 out of 10  *[0:10 · clock 10:45]*

*[Table.]* And it beats them in all ten scenarios of the three families, by 3
to 25 percent, including held-out shifts.

### Slide 34 — B3: what BPN learned  *[0:05 · clock 10:50]*

Its learned settings choose back-pressure for short bursts and reservation for
long ones.

---

## Wrap-up — Speaker 2 (or both)

### Slide 35 — Implementation and reproducibility  *[0:10 · clock 11:00]*

Everything is covered by 46 unit tests, and every number comes from logged
results. B1 has been submitted to NCC 2027, and libcmat is being prepared for
release.

### Slide 36 — Conclusions  *[0:25 · clock 11:25]*

To conclude: Part A gives 6 to 8 times compression with error bounds, a
certified inverse, and libcmat, 14 times faster than numpy and LAPACK. Part B
gives an uncertainty-aware, explainable forecaster and BPN, which wins all ten
scenarios.

**Part A lowers the load; Part B serves what remains, at the right time.**

### Slide 37 — Scope and future work  *[0:10 · clock 11:35]*

Next, we will release and publish libcmat, port it to GPUs, and deploy BPN as
an xApp in the near-real-time RIC.

### Thank you  *[0:05 · clock 11:40]*

Thank you. We're happy to take questions.

---

## If you are running late

- At the 6:20 handover you should be on slide 18. If you are more than
  30 seconds behind, say only the bold line on slides 12, 23, 24, 26, 27
  and 34.
- Never skip slides 2, 8, 10, 11, 17, 20, 22, 30 and 32. They carry the story and
  the numbers examiners ask about.

## Numbers to have ready

| What | Number |
|---|---|
| Compression (CSEE / RAS-BFP vs 16-bit IQ) | 6.4× / 8.1×, standard BFP 2× |
| libcmat, whole precoder, 16 users, 64 antennas | 0.226 ms vs 3.21 ms numpy + LAPACK (14×) |
| libcmat, inverse only vs LAPACK | 9.8× / 13.9× / 13.8× at 8 / 16 / 32 users |
| libcmat, single core | 2.5–4× faster than numpy + LAPACK |
| RU-side precoding | −72 % fronthaul, 99.7 % of sum-rate |
| InverseNet-Ultra vs LAPACK (n = 100) | 0.47 / 0.57 ms vs 0.57 / 1.13 ms (mean / p95) |
| RMT-WS cost | 6 multiplies vs more than 10 for Neumann-type methods |
| Link oversubscription | sum of peaks = 2.44 × capacity |
| B1 vs point forecast | −11 to −43 %, 20/20 seeds |
| B2 uncertainty under shift | LL epistemic spread +30 %, best calibration |
| B3 (BPN) vs best baseline | 10/10 scenarios, −3 to −25 %, p ≤ 0.024 |

For questions, use the backup slides (paired reductions, BPN on Families G
and M, likely questions, references) and `presentation/PartB_study_guide.pdf`.
