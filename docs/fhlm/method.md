# Uncertainty-aware, deadline-feasible budget allocation for a shared O-RAN 7-2x fronthaul link

Project title: **Fronthaul Load Management for Shared Packet Fronthaul: Deadline-Feasible,
Uncertainty-Aware Budget Coordination across O-RAN 7-2x Cells**

This document is the technical companion of the code in `fhlm/`. Everything
described here is implemented; numbers quoted come from `results/fhlm/`.

## 1. Problem and system model

### 1.1 Topology and the shared resource

* N = 8 cells, each an O-RU served by an O-DU (DU pool). All DL U-plane traffic
  (O-DU -> O-RU, split 7-2x, eCPRI over Ethernet) crosses **one aggregation
  link** of C = 25 Gbit/s (25GE). 3% is reserved for C/M/S-plane, so the usable
  U-plane capacity is C_u = 24.25 Gbit/s = **12.125 Mbit per 0.5 ms slot**.
* Slot = 0.5 ms (NR numerology 1, 30 kHz SCS), 14 symbols, 273 PRBs (100 MHz),
  L = 4 spatial layers per cell.
* Fronthaul cost of one PRB-layer for one slot with BFP-9 compression:
  (12 subcarriers x 2 x 9 bit + 8 bit exponent) x 14 symbols x 1.08 (eCPRI/Ethernet
  overhead) = **beta = 3387 bit**. Cell peak = 273 x 4 x beta = 3.70 Mbit/slot =
  7.4 Gbit/s. Aggregate peak of 8 cells = 59 Gbit/s, i.e. **2.44x** the usable
  link: a statistical-multiplexing design (Sec. A of the literature review).

### 1.2 Traffic abstraction and how demand maps to fronthaul load

User-plane bits a_i(t) arrive at the DU queue of cell i in slot t (synthetic
model, Sec. 3). With spectral efficiency eta_i(t) user bits per PRB-layer, the
fronthaul-equivalent demand is

    d_i(t) = a_i(t) / eta_i(t) * beta        [fronthaul bits / slot].

Cells with poor radio conditions (low eta) load the fronthaul more per user bit
(eta ranges from 2.0 to 5.5 bit/RE across cells in the default configuration).
Application volume and fronthaul demand are therefore related through a
time-varying, cell-specific factor, never treated as equal.

### 1.3 Queues, deadlines, accounting

Each cell has one DU-side FIFO queue tracked by bit age. Bits older than the
cell's deadline D_i are discarded and counted as **deadline violations** (a late
7-2x U-plane packet is useless once the O-RU receive window has passed; we
model the DU-side scheduling deadline that protects that window). Low-latency
(LL) cells: D = 4 slots (2 ms), priority 3. eMBB cells: D = 20 slots (10 ms),
priority 1. Metrics count bits, not packets. "Queueing delay" is DU-side
queueing only; the fronthaul link itself never queues because of the
constraint below.

### 1.4 What is decided, when, and with what information

Every **T = 20 slots (10 ms)** a coordinator sets per-cell budgets r_i
(bits/slot) that hold for the next interval:

    sum_i r_i <= C_u,     0 <= r_i <= cap_i = 273 * L_i * beta.

Within the interval, cell i's DU scheduler transmits at most floor(r_i/beta)
PRB-layers per slot. Because the constraint is enforced at decision time and
each cell stays within its budget, the shared link is never overloaded (tested
in `tests/test_fhlm.py::test_capacity_compliance_every_slot`); congestion
appears as DU queueing and violations instead.

The coordinator observes state that is **tau = 2 slots (1 ms) old**: per-cell
queue length and head-of-line age, the per-slot demand history up to t - tau,
and the current spectral efficiency. It never sees the future.

**Why decide in advance at all?** The coordination loop is slower than a slot
for operational reasons: cross-DU/cross-cell telemetry and control run over
E2/O1-type interfaces at >= 10 ms in O-RAN (near-RT RIC loop), switch shaping
configuration is not changed per slot, and multiple DU schedulers cannot
consult each other within the sub-millisecond scheduling pipeline. The
consequence is a reservation lead time of T + tau slots during which the
budgets cannot react. We do **not** assume anything else that would favour
forecasting; and we quantify the effect of T directly (interval sweep, T in
{4, 10, 20, 40} slots, `results/fhlm/sweep_summary.csv`). Two findings bound
the regime of validity: at T = 4 slots the proposed rule is far ahead of the
reactive controllers *and* of the oracle-informed water-fill (so the
allocation rule, not only the forecast, matters), while at T = 40 slots
(5x the LL deadline) every deadline-aware controller over-reserves the LL
peak rate and the deadline-unaware proportional controller is better on the
weighted metric. Reserving a deadline-feasible rate is appropriate when the
interval is at most a few multiples of the shortest deadline.

## 2. Deadline-feasible demand r*

For arrivals a_0..a_{H-1} over the horizon and deadline D, the minimum constant
service rate that serves every bit within D slots (FIFO, empty start) is

    r*(a, D) = max_{0<=s<=e<H}  sum_{k=s}^{e} a_k / (e - s + 1 + D).

Necessity: the bits arriving in [s, e] must be served by e + D and a constant
rate r can serve at most r (e - s + 1 + D) bits in slots s..e+D. Sufficiency is
the standard arrival/service-curve argument (Le Boudec & Thiran 2001). For
D -> infinity this tends to (sum a_k)/(H + D), i.e. the interval-mean notion;
for D = 4 it is often 2-3x the mean rate. The simulator is PRB-granular, so r*
is tight up to one PRB-layer (verified numerically in
`test_required_rate_is_deadline_feasible_and_tight`).

Every deadline-aware controller uses the same demand composition

    demand_i = B_i + r*_i,     B_i = backlog_i / slack_i,

where slack_i = clip(D_i - hol_age_i - tau + 1, ceil(D_i/2), T) converts the
observed backlog into a per-slot rate. Only the estimate of r*_i differs.

## 3. Traffic model (synthetic, labelled as such)

Per cell: smooth Gamma background + ON/OFF bursty component with
**heavy-tailed (Pareto) sojourns** (alpha_on = 1.5, alpha_off = 1.8; Willinger
et al. 1997), slow piecewise-constant regime multipliers (mean 1 s), slow
spectral-efficiency drift, and optional flash-crowd regimes. The scale is set
so that the mean fronthaul demand equals a target load rho x C_u. The traffic
is exogenous (does not depend on the controller). Real fronthaul traces were
not available; no real-world validation is claimed.

## 4. Controllers

| name | forecast of r* | allocation |
|---|---|---|
| `static_equal` | none | C_u / N, redistributing shares above caps |
| `reactive_prop` | mean-rate EWMA (deadline-unaware) | proportional water-filling |
| `queue_aware` | persistence: r* of the last observed horizon (x (1+margin)) | deadline-weighted water-filling |
| `point_forecast` | GBM **median** of r* (x (1+margin)) | deadline-weighted water-filling |
| `proposed_window` | empirical quantiles of r* over the last 30 horizons (no ML) | KKT quantile rule |
| `proposed` | GBM **quantiles** of r* | KKT quantile rule |
| `proposed_cal` | GBM quantiles + adaptive-conformal level offset | KKT quantile rule |
| `oracle` | true r* of the horizon (not implementable) | deadline-weighted water-filling |

Water-filling: demand met if feasible, leftover redistributed as headroom;
under shortage, capacity split in proportion to weight x demand with caps.
Margins (0 / 0.25 / 0.5) of the reactive and point-forecast controllers are
tuned on validation seeds (`results/fhlm/tuning.json`), so the baselines are
not handicapped.

Deadline weights: w_i = priority_i x clip(H / D_i, 0.25, 1), H = T + tau. With
the default T both classes have H >= D so the weights reduce to the operator
priorities (3 for LL, 1 for eMBB); the deadline enters through r* and slack.

## 5. Proposed method

**Inputs**: quantiles q_i(alpha_k) of r*_i (alpha in {0.05, 0.25, 0.5, 0.75,
0.9, 0.95}) from the forecaster; backlog rate B_i; weights w_i; C_u; caps.
**Output**: budgets r_i. **State**: none (raw) or per-cell level offsets
delta_i (calibrated variant).

Surrogate objective

    max  sum_i w_i E[ min(B_i + r*_i, r_i) ]   s.t.  sum_i r_i <= C_u,  0 <= r_i <= cap_i.

E[min(D, r)] is concave in r with derivative w_i (1 - F_i(r - B_i)) =
w_i P(marginal budget unit is needed). The KKT conditions of this separable
concave program give

    r_i(lambda) = clip( B_i + F_i^{-1}(1 - lambda / w_i), 0, cap_i ),

and lambda >= 0 is the unique multiplier with sum_i r_i(lambda) = C_u, found by
60 bisection steps (lambda = 0 if the constraint is slack; the surplus is then
spread as headroom exactly as in the baselines). F_i^{-1} is piecewise-linear
through the forecast quantiles, linearly extrapolated above 0.95.

**Proposition 1 (feasibility).** For any forecasts and any lambda the output
satisfies the caps, and the returned budgets satisfy sum_i r_i <= C_u
(bisection returns the largest feasible sum; the simulator additionally projects).

**Proposition 2 (equal weighted tail probability).** At an interior optimum every
cell satisfies w_i (1 - F_i(r_i - B_i)) = lambda. Hence for equal weights all
cells are cut at the same forecast quantile; a cell with a wider predictive
distribution or a higher weight receives a larger margin above its median.
Point forecasts (degenerate F_i) reduce the rule to a priority-ordered fill,
which is why water-filling on the median is the natural point-forecast
comparator.

**Proposition 3 (backlog first).** Since F_i(x) = 0 for x < 0, the marginal
value of budget below B_i is w_i; any cell with lambda < w_i is allocated at
least min(B_i, cap_i) before any uncertain demand of a cell of equal or lower
weight is funded.

**Complexity.** O(N K) to build the inverse CDFs and O(N n_iter) for the
bisection (K = 6, n_iter = 60): a few tens of microseconds for N = 8. The
measured decision time (~3.4 ms per control epoch of 10 ms, pure Python on a
4-core CPU, `results/fhlm/main_summary.csv`) is dominated by feature
construction and by evaluating 6 x 300 trees; the trees are traversed with a
vectorised numpy routine (`forecast.CompiledGBM`, ~1.8 ms for 8 cells) because
scikit-learn's `predict` loops over trees in Python (~12 ms). The rule itself
is negligible; the deadline-aware reactive baseline needs ~0.08 ms.

**Calibrated variant (`proposed_cal`).** After each horizon is fully observed,
per-cell offsets are updated as delta_i <- clip(delta_i + gamma (1[y_i > q_i(0.9)] - 0.1),
-0.3, 0.3) (Gibbs & Candes 2021) and the rule uses F_i^{-1}(p + delta_i). This
is the fallback for forecast degradation; its effect is reported as an
ablation (it did not help under the weighted objective).

**Edge cases.** Non-finite forecasts -> empirical window quantiles; zero
demand -> zero budget plus redistributed headroom; capacity not binding ->
every cell gets its full predictive support.

## 6. Forecasting pipeline

* Target: y_i = r*(d_i[t - tau : t + T], D_i) / cap_i.
* Features (28): last 6 horizon means, their mean/std/max, two EWMAs, the last 4
  slot demands, r* of the last 3 horizons, relative spectral efficiency,
  D_i / H, cell one-hot. All normalised by configuration constants (cell peak),
  so no statistics are fitted on data.
* Model: one `HistGradientBoostingRegressor(loss="quantile")` per level,
  300 iterations, 15 leaves. Trained on 16 traces x 16,000 slots from
  TRAIN seeds (loads 0.5-0.95, nominal traffic); validated on VAL seeds
  (scenarios moderate/high); TEST seeds are used only for the final
  comparison. Training takes ~12 s on a 4-core CPU.
* Validation quality (`results/fhlm/forecast_training_T20_d2.json`):
  empirical coverage 5.6 / 25.6 / 50.7 / 75.3 / 89.9 / 94.9 % at nominal
  5 / 25 / 50 / 75 / 90 / 95 %; median relative MAE 37 % vs 52 % for
  persistence and 49 % for the window median; mean pinball loss 0.0224 vs
  0.0293 for window quantiles.

## 7. Evaluation protocol

Scenarios (offered load relative to C_u): low 0.50, moderate 0.65, high 0.80,
flash crowds (0.80 with 1.8x regimes 15% of the time), and a **held-out shift**
(0.80, ON intensity x1.5, ON duration x1.5, heavier tail alpha_on = 1.2) never
seen in training or tuning. Five test seeds per scenario, 20,000 slots (10 s)
each after a 1,000-slot warm-up; all controllers see the identical trace.

Primary metric (fixed before tuning): **priority-weighted deadline-violation
ratio** = sum_i p_i violated_i / sum_i p_i arrived_i. Supporting metrics:
per-class violation ratios, link utilisation, unused-allocation fraction, mean
and p99 DU queueing delay, Jain fairness of per-cell service ratio, minimum
cell service ratio, decision time. Ablations: point vs quantile forecast
(`point_forecast` vs `proposed`), ML vs window quantiles under the same rule
(`proposed` vs `proposed_window`), calibration on/off, and the control-interval
sweep T in {4, 10, 20, 40} slots.

See `results/fhlm/main_summary.csv` and the figures in `results/fhlm/figures/`
for the numbers; `docs/fhlm/results_summary.md` discusses them.
