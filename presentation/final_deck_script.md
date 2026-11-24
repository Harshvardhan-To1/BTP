# Final Deck — 12-Minute Presentation Script

Script for `presentation/BTP_final_deck.pdf` (title slide, 34 numbered slides,
thank-you slide, backup). Slide numbers below are the numbers in the
bottom-right corner of each slide. Every number in the script matches the deck.

The spoken text is about 1,700 words. At a relaxed 140 words a minute that
is just under **12 minutes**; at a normal 150 words a minute it is about 11.
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
| Opening and background | Title, 1–6 | 2:20 | 2:20 |
| Part A | 7–16 | 3:40 | 6:00 |
| Part B | 17–31 | 4:45 | 10:45 |
| Wrap-up | 32–34, Thank you | 0:55 | 11:40 |

---

## Opening and background — Speaker 1

### Title — Fronthaul Load Management for B5G  *[0:10 · clock 0:10]*

Good morning. We are Harshvardhan Choudhary and Mayank Yadav, and our project,
guided by Dr. Sumit Gautam, is about managing the load on the fronthaul in
beyond-5G networks.

### Slide 1 — Roadmap  *[0:20 · clock 0:30]*

We'll first explain why the fronthaul is under pressure. Then Part A, where we
make the data smaller and the processing faster, and Part B, where we share
one link between many cells. At the end we show how the two fit together.

**One idea runs through everything: keep the maths of the problem, and only
learn the part that is truly uncertain.**

### Slide 2 — Fronthaul, midhaul, backhaul  *[0:25 · clock 0:55]*

*[Point left to right along the chain.]* A phone's signal goes from the
antenna unit to the distributed unit, then the central unit, then the core.
The first hop, the fronthaul, is the hard one. It carries raw radio samples,
called IQ, at tens of gigabits per second per cell, and they must arrive
within about 100 microseconds. The other links carry ordinary user data.

**The fronthaul decides how many cells an operator can afford, so that is our
focus.**

### Slide 3 — From D-RAN to Open RAN  *[0:20 · clock 1:15]*

Older centralised networks sent samples at a fixed rate, even for an empty
cell. Open RAN's 7-2x split only sends samples for the resource blocks that
are actually scheduled. So the load now follows the traffic, and many cells
can share one link.

**Fronthaul load is scheduled resource blocks times bits per block. Both parts
of our project build on that.**

### Slide 4 — Why the fronthaul is the bottleneck  *[0:25 · clock 1:40]*

*[Point to the red boxes.]* That creates two problems. First, the data is big
and time is short. Standard compression only halves it, and every
half-millisecond slot the DU must invert matrices for 273 resource blocks.
Standard code takes 3.2 milliseconds, six times the slot.

Second, eight cells share a link far smaller than their combined peak. When
bursts coincide, someone loses data.

### Slide 5 — Problem statement and our two levers  *[0:15 · clock 1:55]*

So we pull two levers. *[Left box.]* Part A makes the data smaller and the DU
fast enough. *[Right box.]* Part B decides how to split the link before the
traffic arrives.

**Compression sets how much load reaches the link; allocation decides who
loses when it overflows.**

### Slide 6 — Headline results  *[0:25 · clock 2:20]*

Results up front. *[Walk the four cards.]* Channel data compressed 8.1 times,
against 2 for the standard. A precoder 14 times faster that fits inside the
slot. Precoding at the radio unit cuts fronthaul traffic by 72 percent. And
our link-sharing controller beats the strongest baselines in all ten
scenarios.

---

## Part A — Speaker 1

### Slide 7 — Which IQ do we compress?  *[0:20 · clock 2:40]*

Each slot gives us a 64 by 1200 matrix: 64 antennas, 1200 subcarriers. The
channel inside it is low rank, because the antennas are correlated, and sparse
in delay, because only a few paths are strong. User data destroys this
structure, so we compress channel-carrying samples like reference signals,
and leave data samples on the standard scheme.

### Slide 8 — Two encoders with error bounds  *[0:25 · clock 3:05]*

We built two encoders. *[Left.]* CSEE moves the data into the delay domain and
keeps only the strongest taps. *[Right.]* RAS-BFP uses a random sketch to find
the low-rank part quickly, without a full SVD.

**Both encoders come with a proven error bound, so the operator knows the
worst-case quality before sending anything.**

### Slide 9 — Compression results  *[0:20 · clock 3:25]*

*[Point to the green rows.]* At the same error level, CSEE compresses 6.4
times and RAS-BFP 8.1 times, against 2 times for the O-RAN standard. RAS-BFP
matches SVD's ratio but encodes three to four times faster. *[Point to the
plot.]* SVD's cost grows fastest as the antenna array grows.

### Slide 10 — Inversion screening  *[0:15 · clock 3:40]*

Next, speed. Equalisation and precoding both need a matrix inverse every slot.
We tried learned inverters, and the lesson was clear. The best approach was to
keep the classic Newton–Schulz iteration and learn only a good starting guess.

### Slide 11 — RMT-WS  *[0:30 · clock 4:10]*

That led to RMT-WS, our warm-start inversion method. *[Follow the flowchart.]*
First we balance the matrix so near and far users look alike. Random matrix
theory cheaply tells us where its eigenvalues lie, which gives a good first
guess. Or, if users barely moved, we reuse last slot's inverse. A cheap
certificate checks the start is safe, and otherwise falls back to a cold
start.

**Every step is a plain matrix multiply, so the method maps directly onto
fast hardware.**

### Slide 12 — Interval coverage and cost  *[0:20 · clock 4:30]*

*[Left table.]* Our estimate of where the eigenvalues lie covers the top edge
in 100 percent of cases, on every channel type. *[Right table.]* To stay
within 1 percent of the ideal data rate, we need only 6 matrix multiplies.
Neumann-type methods from the literature need more than 10.

### Slide 13 — Tracking at every speed  *[0:25 · clock 4:55]*

At walking speed we need only 2.25 multiplies per slot. At 120 kilometres per
hour, fixed warm starts break down, but our certificate switches to a cold
start, giving 24 times lower loss than warm Gauss–Seidel. In 480 audited
cases it never accepted a bad step. *[Point to the plot.]* A simple law
predicts when warm starts stop paying off: about 39 kilometres per hour for
16 users.

### Slide 14 — Where should precoding run?  *[0:25 · clock 5:20]*

*[Point to arrow a.]* If the DU precodes, it sends 64 antenna streams: 118
gigabits per second. *[Point to arrow b.]* If the radio unit precodes, we send
just 16 user layers plus weights: 33 gigabits per second. That is 72 percent
less traffic, at 99.7 percent of the data rate.

**The catch: with moving users, the weights must be refreshed every slot, so
we need a precoder fast enough to do that.**

### Slide 15 — Fused C/AVX-512 kernel  *[0:15 · clock 5:35]*

So we wrote one in C with AVX-512 vector instructions. Each resource block is
handled in a single pass that stays inside the fastest cache. We tuned it by
profiling the CPU cycles spent in each stage, and that halved the time spent
forming the weights.

### Slide 16 — Kernel results  *[0:25 · clock 6:00]*

*[Point to the highlighted row.]* For 16 users and 64 antennas, numpy needs
3.2 milliseconds. Our kernel needs 0.23 milliseconds, 14 times faster.

**For the first time, the whole precoder fits inside the half-millisecond
slot, with essentially no loss of accuracy.**

With that, I'll hand over to Mayank for Part B.

---

## Part B — Speaker 2

### Slide 17 — Decide budgets before traffic is seen  *[0:20 · clock 6:20]*

Thank you. In Part B, eight cells share one link: three low-latency cells
with a 2 millisecond deadline, and five broadband cells with 10. Their peaks
add up to 2.44 times the link. Every 10 milliseconds, a coordinator sets each
cell's budget from slightly old data, before seeing the traffic.

### Slide 18 — System model and metric  *[0:20 · clock 6:40]*

A cell's fronthaul load depends on its resource blocks, and Part A's
compression sets the cost of each block. So two cells with the same user
traffic can differ two to three times in load. *[Point to the bottom box.]*
We score a controller by the share of bits that miss their deadline. A lost
low-latency bit counts three times.

### Slide 19 — Key idea 1: forecast r-star  *[0:25 · clock 7:05]*

Our first idea is to forecast the right quantity. We call it r-star: the
smallest steady rate at which no bit misses its deadline. *[Point to the
sketch.]* With a long deadline, the average rate is enough. With a short one,
you need close to the burst rate. For our 2 millisecond cells, r-star is often
two to three times the average, and very uneven.

**A single predicted number is a poor guide for something that uneven, so we
forecast a range.**

### Slide 20 — Key idea 2: KKT newsvendor split  *[0:30 · clock 7:35]*

Our forecaster predicts six quantiles per cell, and one formula splits the
link. *[Point to the red box.]* Each cell gets its backlog plus a quantile of
its forecast, set by one shared price, lambda. *[Point to the bars.]* So a
high-priority cell, or one with an uncertain forecast, automatically gets more
safety margin.

**Every cell is cut at the same priority-weighted risk. The margins come out
of the maths, not out of tuning.**

### Slide 21 — Four proven properties  *[0:15 · clock 7:50]*

We proved four properties. The link is never overloaded. Every cell carries
equal weighted risk. Queued bits are served first. And if the forecast is off,
performance degrades gently.

### Slide 22 — A fair evaluation  *[0:15 · clock 8:05]*

We tested on three traffic families: synthetic bursty traffic, traffic built
only from 3GPP standard models, and Markov traffic. Every controller saw the
same traces, over 20 test seeds, with paired statistical tests.

### Slide 23 — B1 main result  *[0:25 · clock 8:30]*

*[Point to the green row.]* Our rule is the best implementable controller in
all five scenarios: at high load, 8.0 percent against 9.7 for a point
forecast. Seed by seed, it cuts violations by 11 to 43 percent, on all 20
seeds. *[Point to the red box.]* Its weakest case is flash crowds: only
4 percent better than reactive proportional.

### Slide 24 — Where the gain comes from  *[0:15 · clock 8:45]*

*[Point to the plot.]* The reactive controller is always one interval late.
Our rule raises the budget as soon as a burst starts, because that is exactly
when the forecast range widens.

### Slide 25 — Ablations and 3GPP traffic  *[0:15 · clock 9:00]*

Most of the gain comes from the rule itself, not from the machine learning.
Even without ML, it beats the point forecast. *[Right table.]* And on 3GPP
traffic that we did not design, it is again the best.

### Slide 26 — Robustness and A × B  *[0:20 · clock 9:20]*

It stays solid when the forecast is miscalibrated or when the decision
interval changes. *[Point to the right table.]* This is where Part A and
Part B meet. Changing only the compression width moves the link load. At 0.65
load, our rule halves the loss of reactive control.

**Compression sets the regime; allocation decides the loss inside it.**

### Slide 27 — Extended study  *[0:15 · clock 9:35]*

Then we built stronger baselines, predictive MaxWeight and a search-tuned
policy called CEM, and they beat our rule in nine of ten scenarios. Retuning
didn't help: the gap was structural.

### Slide 28 — B2: Bayesian Transformer  *[0:15 · clock 9:50]*

Would a better forecaster help? Our Bayesian Transformer is the best
calibrated and beats the tree model on every seed, but at high load by only
1.4 percent. So the problem was the decision structure, not the forecast.

### Slide 29 — B3: back-pressure newsvendor  *[0:25 · clock 10:15]*

So we changed it. Reserved capacity that goes unused is lost, so BPN works in
two stages. *[Stage 1.]* First, it fills a base budget
in order of queue pressure, like back-pressure. *[Stage 2.]* Then it spends
whatever is left on our risk-based margins.

**Both strongest baselines are special cases of BPN, so a fair search can only
match or beat them.**

### Slide 30 — BPN wins 10 out of 10  *[0:20 · clock 10:35]*

*[Point to the table.]* And it does. BPN wins every scenario in all three
families, by 3 to 25 percent, including held-out shifts, against baselines
given the same tuning effort.

### Slide 31 — What BPN learned  *[0:10 · clock 10:45]*

The learned settings also make sense. They pick back-pressure for short
bursts and reservation for long ones. Each decision takes about 3
milliseconds.

---

## Wrap-up — Speaker 2 (or both)

### Slide 32 — Implementation and reproducibility  *[0:10 · clock 10:55]*

Everything is open and tested, with 46 unit tests, and every number comes
straight from the logged results. The first Part B paper has been submitted
to NCC 2027.

### Slide 33 — Conclusions  *[0:25 · clock 11:20]*

To conclude: Part A gives 6 to 8 times compression with error bounds, a
certified fast inverse, a precoder that fits the slot, and 72 percent less
traffic. Part B shares what remains, and the back-pressure newsvendor wins
all ten scenarios.

**Part A lowers the load; Part B serves what remains, at the right time.**

### Slide 34 — Limitations and future work  *[0:15 · clock 11:35]*

Limits: this is all simulation, and our compression covers channel samples
only. Next: real traces, a GPU kernel, and the controller as an xApp on an
O-RAN testbed.

### Thank you  *[0:05 · clock 11:40]*

Thank you. We're happy to take questions.

---

## If you are running late

- At the 6:00 handover, you should be on slide 17. If you are more than
  30 seconds behind, say only the bold line on slides 10, 12, 15, 21, 22, 24,
  25 and 31.
- Never skip slides 4, 14, 16, 19, 20, 23, 29 and 30. They carry the story and
  the numbers examiners ask about.

## Numbers to have ready

| What | Number |
|---|---|
| Compression (CSEE / RAS-BFP vs 16-bit IQ) | 6.4× / 8.1×, standard BFP 2× |
| Precoder, 16 users, 64 antennas | 0.226 ms vs 3.21 ms numpy (14×) |
| RU-side precoding | −72 % fronthaul, 99.7 % of sum-rate |
| RMT-WS cost | 6 multiplies vs more than 10 for Neumann-type methods |
| Link oversubscription | sum of peaks = 2.44 × capacity |
| KKT rule vs point forecast | −11 to −43 %, 20/20 seeds |
| BPN vs best baseline | 10/10 scenarios, −3 to −25 %, p ≤ 0.024 |

For questions, use the backup slides (paired reductions, BPN on Families G
and M, likely questions, references) and `presentation/PartB_study_guide.pdf`.
