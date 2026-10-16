# Reviewer-style assessment of the manuscript and what was changed in response

This file records an honest review of the work as it stood after the
mid-evaluation (5 test seeds, 8 controllers, feasibility-level theory) and
the changes made to address each point before writing `paper/main.tex`.
Items marked **open** could not be addressed with the material available and
are stated as limitations in the paper.

## Summary judgement before revision

Solid engineering prototype with a candidate contribution (deadline-feasible
rate as forecast target + KKT allocation on forecast quantiles + fair
evaluation). Not yet a paper: too few seeds for any significance claim, a
comparator set without a queue-based or global-quantile baseline, theory
limited to feasibility, no robustness analysis, and a compression part whose
source is not reproducible. Recommendation would have been *major revision*
for a conference, *reject* for a journal.

## Point-by-point

### R1. Statistical evidence is insufficient (5 seeds, "win counts")
*Review.* Five seeds cannot support a significance claim, and "3/5 seeds" under
flash crowds is indistinguishable from noise. The paired design is good but
unused statistically.
*Response.* Test seeds extended to 20 (3000-3019), still disjoint from
training and validation. `paired_analysis` now reports a two-sided Wilcoxon
signed-rank test per (scenario, baseline), Holm-corrected within scenario, and
a 95 % percentile-bootstrap CI on the relative reduction. Result: every
comparison against every baseline is significant at p < 0.05 after
correction, in every scenario; the flash-crowd case against reactive
proportional, a tie at 5 seeds, is 16/20 wins with Holm p = 0.033.
**Addressed.**

### R2. The comparator set is weak / incomplete
*Review.* "Beats the oracle water-fill" invites the question why water-fill is
the baseline family. There is no queue-based (Lyapunov / MaxWeight) controller,
which is the standard non-forecast allocation in stochastic network
optimisation, and no "use a high quantile for everybody" controller, which is
what the probabilistic-forecast literature actually does. Without the latter
the paper cannot distinguish "quantiles help" from "the per-cell KKT level
selection helps".
*Response.* Added `MaxWeightReactive` (greedy fill by priority x queue, optional
head-of-line-age urgency, tuned on validation; selected the HOL-age variant)
and `FixedQuantileWaterfill` (same GBM forecaster, one global level tuned on
validation from {0.75, 0.9, 0.95}; selected 0.75). Both are beaten in every
scenario on every seed (p < 0.001). The fixed-quantile result is the key one:
a global percentile over-reserves for confident cells and under-reserves for
uncertain ones. **Addressed.**

### R3. Theory is thin (feasibility, equal risk, backlog-first only)
*Review.* These are restatements of KKT. A reviewer expects at least one
statement about what happens when the forecast is wrong, since the whole
method rests on the forecast distribution.
*Response.* Proposition 4 (robustness to miscalibration): if the forecast CDFs
are within Kolmogorov distance eps of the truth, the loss in weighted expected
served demand from allocating on the forecast is at most
eps * sum_i w_i[(r_i^G - B_i)^+ + (r_i^F - B_i)^+] <= 2 eps w_max C. Proof in
`method.md` and in the paper. Verified empirically with the new
`miscalibration` experiment (all quantile levels shifted by eps in
[-0.3, 0.3]); the response is asymmetric: under-reserving is almost free
(absorbed by the multiplier), over-reserving degrades gradually to +23 % at
eps = +0.3 (high load), where the rule only falls back to the level of the
point-forecast controller and stays below the deadline-aware reactive
controller. **Addressed (modest result, clearly labelled as such).**

### R4. No sensitivity analysis beyond the control interval
*Review.* The telemetry delay is a central modelling assumption (it is why one
must forecast) yet only one value is used.
*Response.* New `delay` experiment: tau in {0, 2, 5, 10} slots with forecasters
retrained per tau, 10 seeds. Reported as a table in the paper. The finding is
not uniformly favourable and is stated: the ordering is preserved at every
tau, but the margin over the deadline-unaware proportional controller shrinks
from 16 % (fresh state) to 2 % at tau = 5 ms, so timely telemetry is part of
the operating regime. **Addressed.**

### R5. Interval sweep and compression experiment use only 3 seeds
*Response.* Both re-run with 10 seeds. **Addressed.**

### R6. Compression part (Part A) is not reproducible
*Review.* The CSEE / RAS-BFP / ACAFS results import a `src/` package that is
not in the repository; the "Theorems 1-5" cannot be checked. Publishing
unverifiable theorems is not acceptable.
*Response.* The paper does **not** claim any Part A compression result or
theorem. It keeps only what is reproducible: the BFP mantissa width as a load
lever in the simulator (the `compression` experiment), and cites the
decomposition literature (Eckart-Young, Halko-Martinsson-Tropp) as background
in the introduction. The matrix-inversion benchmark is not in the paper
because it does not bear on the allocation claim. **Addressed by scoping.**
Restoring `src/` remains **open** for a separate compression paper.

### R7. Synthetic traffic only
*Review.* Public per-cell PRB-level fronthaul traces do not exist, but the
paper must say so plainly and must not claim real-world validation.
*Response.* Stated in the methodology, limitations and abstract. The held-out
"shift" family (burstier than training) and the miscalibration sweep are the
available substitutes for out-of-sample validation. **Open** (requires data
the authors do not have); clearly labelled.

### R8. Link model is a budget-enforced pipe
*Review.* No switch queue, no O-RU receive window, one class per cell, no
HARQ, downlink only.
*Response.* Stated as limitations. A switch-level model is future work.
**Open**, labelled.

### R9. Decision time measured in Python
*Response.* Reported honestly (3.5 ms per 10-ms epoch, dominated by tree
evaluation; rule itself microseconds); a compiled implementation is listed as
required for deployment. **Open**, labelled.

### R10. Oracle described inconsistently
*Review.* Early text called it an upper bound; the sweep shows the proposed rule
beating it.
*Response.* Consistently "oracle-informed reference for a perfect point
forecast under the water-fill rule, not a bound". **Addressed.**

### R11. Reproducibility of numbers in the text
*Review.* Numbers typed by hand into a manuscript drift from the data.
*Response.* `fhlm/make_paper_tables.py` generates every table and every number
macro (`paper/generated/`) from the CSVs; the manuscript contains no
hand-typed result. **Addressed.**

### R12. Claims of novelty
*Review.* The ingredients (quantile boosting, constrained newsvendor,
water-filling, ACI, network-calculus rate) are all known.
*Response.* The paper claims the combination and its evaluation, states which
ingredients are borrowed, and positions the closest prior work (Lagen 2022;
Bega 2019/2020; Kasuluru 2024; Cohen 2023) explicitly. **Addressed by framing.**

## What remains open after revision (to be said in the paper and to reviewers)

1. No measured traffic traces (R7).
2. Simplified link model (R8).
3. Python timing (R9).
4. Theory does not cover closed-loop stability or multi-interval optimality.
5. The learned forecaster adds little under distribution shift; the paper
   presents the non-learned quantile variant as the robust fallback rather
   than hiding this.

## Suggested venue

Full conference paper (IEEE WCNC / ICC / GLOBECOM main track, or IEEE NOMS /
CNSM for the management angle). A journal version would need measured traces
and a switch-level model.
