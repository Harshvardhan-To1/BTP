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
paper must say so plainly, must not claim real-world validation, and should
not rest on a single self-designed generator.
*Response (second revision).* A second, independent traffic family was added
that contains nothing hand-designed: 3GPP TR 38.901 UMa channel (LOS
probability, path loss, shadowing, best server of 7 sites, Jakes-correlated
Rayleigh fading), TR 36.942 / TS 38.214 link adaptation, FTP Model 3
(TR 36.814) for eMBB cells, XR video (TR 38.838) for low-latency cells, a
per-cell round-robin PRB scheduler; fronthaul demand is the scheduler's
PRB-layers times the BFP cost. It has its own forecaster and its own tuning,
and the main result reproduces on it (Sec. VII-B of the paper). A
cross-family transfer test (forecaster trained on one family, applied to the
other) is also reported. The paper now says "we know of no public per-slot
per-cell traces (public O-RAN datasets such as ColO-RAN are 250 ms or
coarser)" instead of "no traces exist". **Partly addressed**: still
simulated; the scheduler and fronthaul model are ours.

### R8. Link model is a budget-enforced pipe
*Review.* No switch queue, no O-RU receive window, one class per cell, no
HARQ, downlink only.
*Response.* Stated as limitations. A switch-level model is future work.
**Open**, labelled.

### R9. Decision time measured in Python
*Response.* Reported honestly (3.2-3.5 ms per 10-ms epoch); profiled: ~2 ms
is a vectorised NumPy traversal of 1800 trees for 8 rows, 0.2 ms feature
construction, the rest Python overhead in the 60-step bisection. The paper
states the work (about 2e5 node visits and 480 interpolations) and that it is
well under 1 ms when compiled, without claiming a measured compiled number.
**Open**, labelled.

### R10. Oracle described inconsistently / wrong reference
*Review.* Early text called the oracle water-fill an upper bound; the sweep
shows the proposed rule beating it. The reference that isolates forecast
error is the proposed *rule* with a perfect forecast, not water-filling.
*Response.* Added `oracle_kkt` (the KKT rule with the true r*, i.e. the
priority-ordered fill of Proposition 2). The gap proposed -> oracle_kkt is
reported as the cost of forecast error (24-70 % of the proposed rule's
remaining loss depending on scenario); the oracle water-fill is kept only as
"perfect point forecast under the baseline rule". **Addressed.**

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

### R13. The primary metric favours the method by construction
*Review.* A priority-weighted ratio with w_LL = 3 rewards exactly what the
rule does (protect LL). Show the unweighted ratio and a weight sweep.
*Response.* Both added (Sec. VII-C, `weights` command). Honest outcome: under
the unweighted ratio the proportional controller loses fewer total bits at
moderate/high load in the synthetic family; told w_LL = 1 the rule matches it
and pulls ahead from w_LL = 3. In the 3GPP family at w_LL = 1 the rule is
clearly worse than the point-forecast water-fill (zero-inflated demand makes
the equal-fractile cut all-or-nothing); it ties at 2 and leads from 3. The
paper states that the method is for operators who weight the LL class at
least 2-3x. **Addressed by disclosure, not removed.**

### R14. Proposition 2 wording, urgency weight, length
*Review.* "Reduces to water-filling" for a degenerate forecast is loose (it is
a priority-ordered fill); the urgency factor min(1, H/D) is 1 for both default
classes and should not be presented as active; 8 pages is over the 6-page
limit of the target venues.
*Response.* Prop. 2 now states the priority-ordered fill and `oracle_kkt`
implements exactly it; the weight is w_i = w_i^p with the H/D scaling
mentioned as inactive at the defaults; the paper is 6 pages including
references (Fig. 1, Fig. 2, the paired table and the algorithm box were
removed, the sensitivity tables merged into one, related work and discussion
shortened). Repository URL added (to be anonymised for review).
**Addressed.**

## What remains open after revision (to be said in the paper and to reviewers)

1. No measured traffic traces (R7); two simulated families instead of one.
2. Simplified link model (R8); the 3GPP family uses a round-robin scheduler
   and single-layer link adaptation.
3. Python timing (R9).
4. Theory does not cover closed-loop stability or multi-interval optimality.
5. The learned forecaster adds little under distribution shift; the paper
   presents the non-learned quantile variant as the robust fallback rather
   than hiding this.
6. The advantage is conditional on the operator weight (R13); with equal
   weights the simpler controllers are as good or better.
7. Author affiliations and e-mails in `paper/main.tex` are placeholders.

## Suggested venue

Full conference paper (IEEE WCNC / ICC / GLOBECOM main track, or IEEE NOMS /
CNSM for the management angle). A journal version would need measured traces
and a switch-level model.
