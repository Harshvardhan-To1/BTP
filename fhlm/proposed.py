"""Proposed method: uncertainty-aware, deadline-weighted fronthaul budget allocation.

Decision problem solved at every control epoch
---------------------------------------------
Given for each cell i
  * the known backlog rate B_i (bits/slot needed to clear the observed DU
    backlog within its remaining deadline slack, demand.backlog_rate),
  * a predictive distribution F_i of the deadline-feasible rate r*_i of the
    unseen horizon arrivals (demand.required_rate),
  * a weight w_i (priority x deadline urgency, controllers.deadline_weights),
choose per-slot budgets r_i to

    maximise   sum_i  w_i * E[ min(B_i + r*_i, r_i) ]
    subject to sum_i r_i <= C_usable,   0 <= r_i <= cap_i.

E[min(D, r)] is concave in r with derivative w_i (1 - F_i(r - B_i)) =
w_i * P(the marginal unit of budget is needed). The problem is a separable
concave resource allocation, so the KKT conditions give

    r_i(lambda) = B_i + F_i^{-1}(1 - lambda / w_i)    clipped to [0, cap_i],

with lambda >= 0 found by bisection such that sum_i r_i(lambda) = C_usable
(lambda = 0 if the budget is not binding; the surplus is then redistributed
as headroom exactly like the baselines). At the optimum every cell has the
same weighted tail probability w_i P(D_i > r_i) = lambda: cells with wider
predictive distributions or tighter deadlines receive larger margins. With
degenerate (point) forecasts the rule collapses to a priority-ordered fill.

Uncertainty representation
--------------------------
The forecaster returns quantiles q_i(alpha) at levels alpha_1 < ... < alpha_K.
F_i^{-1} is the piecewise-linear interpolation through the knots, linearly
extrapolated above alpha_K (needed when the calibration asks for a level the
model did not emit).

Online calibration (fallback under distribution shift)
------------------------------------------------------
For each cell a scalar offset delta_i shifts the probability level actually
used: F_i^{-1}(p) := Q_i(p + delta_i). After each horizon is fully observed,
delta_i is updated from the realised miscoverage of the alpha_c = 0.9 quantile
in the spirit of adaptive conformal inference (Gibbs & Candes, 2021):

    delta_i <- clip(delta_i + gamma * (1[y_i > q_i(alpha_c)] - (1 - alpha_c)), lo, hi).

If the model under-covers (traffic burstier than in training) delta grows and
the allocation becomes more conservative; if it over-covers, delta shrinks.
With gamma = 0 the method uses the raw model quantiles (ablation "raw").

Complexity: O(N K + N n_iter) per decision (K quantile knots, n_iter = 60
bisection steps); the forecaster inference dominates the measured time.
"""
from __future__ import annotations

from collections import deque
from typing import Optional, Deque, Tuple
import numpy as np

from .simulator import Controller, Observation
from .controllers import deadline_weights, backlog_rate_obs, waterfill
from .forecast import WindowQuantileForecaster
from .demand import required_rates, critical_window_lengths


def interp_quantile(levels: np.ndarray, q: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Per-row piecewise-linear inverse CDF with linear extrapolation beyond the last knot."""
    n, K = q.shape
    out = np.empty(n)
    for i in range(n):
        pi = p[i]
        if pi <= levels[-1]:
            out[i] = np.interp(pi, levels, q[i])
        else:
            slope = (q[i, -1] - q[i, -2]) / max(levels[-1] - levels[-2], 1e-6)
            out[i] = q[i, -1] + slope * (pi - levels[-1])
    return np.maximum(out, 0.0)


class UncertaintyAwareAllocator(Controller):
    name = "proposed"

    def __init__(self, forecaster=None, w_min: float = 0.25, calibrate: bool = False,
                 gamma: float = 0.02, target_level: float = 0.9, delta_bounds: Tuple[float, float] = (-0.3, 0.3),
                 name: Optional[str] = None, volume_weights: bool = False, volume_window: int = 30,
                 queue_weights: float = 0.0, ll_weight: Optional[float] = None):
        self.forecaster = forecaster if forecaster is not None else WindowQuantileForecaster()
        self.w_min = w_min
        self.calibrate = calibrate
        self.gamma = gamma if calibrate else 0.0
        self.target_level = target_level
        self.delta_bounds = delta_bounds
        if name:
            self.name = name
        # Volume-corrected weights (extended study): the shortfall sandwich shows that a rate shortfall of
        # delta on a horizon drops at least (l* + D_i) * delta bits, l* the length of the critical window.
        # With volume_weights=True the newsvendor weight becomes w_i * (mean l*_i + D_i) estimated from the
        # last `volume_window` horizons, so that the objective is measured in weighted BITS, like V_w.
        self.volume_weights = volume_weights
        self.volume_window = volume_window
        # Drift (MaxWeight-type) weights: w_i <- w_i * (kappa + Q_i / (H * median_i)); the observed backlog measured
        # in horizons of forecast demand multiplies the priority, so a cell that is already behind is funded
        # first. kappa = 0 disables the term; this is the one-step drift-plus-penalty view of the KKT rule.
        self.queue_weights = queue_weights
        # Tuned internal LL weight (extended study): the rule's weight for cells with D_i <= 10 slots is
        # ll_weight instead of the operator priority. The metric still uses the operator priority; this
        # separates "is the KKT structure right" from "is the operator weight the right newsvendor weight".
        self.ll_weight = ll_weight
        self._pending: Deque[Tuple[int, int, np.ndarray]] = deque()
        self._delta = np.zeros(0)
        self.stats = {"decisions": 0, "scored_horizons": 0, "delta_mean_abs": 0.0}

    def reset(self, net, ctrl, rng=None) -> None:
        self._pending.clear()
        self._delta = np.zeros(net.num_cells)
        self.stats = {"decisions": 0, "scored_horizons": 0, "delta_mean_abs": 0.0}

    # ------------------------------------------------------------------
    def _update_calibration(self, obs: Observation) -> None:
        """Adaptive-conformal update of the per-cell level offsets."""
        L = obs.history_fh_demand.shape[1]
        while self._pending and self._pending[0][1] <= L:
            start, end, q_target = self._pending.popleft()
            if self.gamma > 0:
                y = required_rates(obs.history_fh_demand[:, start:end], obs.deadlines)
                miss = (y > q_target).astype(float)
                self._delta = np.clip(self._delta + self.gamma * (miss - (1.0 - self.target_level)),
                                      self.delta_bounds[0], self.delta_bounds[1])
            self.stats["scored_horizons"] += 1

    # ------------------------------------------------------------------
    def _volume_factor(self, obs: Observation) -> np.ndarray:
        """min(mean critical-window length + D_i, T): bits saved per unit of budget rate when it is needed.

        A budget unit held for T slots can serve at most T extra bits, so the volume factor is capped at T.
        """
        H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
        T = obs.ctrl.interval_slots
        hist = obs.history_fh_demand
        n, L = hist.shape
        k = min(self.volume_window, L // H)
        D = obs.deadlines
        if k == 0:
            return np.minimum(D + 1.0, T)
        chunks = hist[:, L - k * H:].reshape(n, k, H)
        ls = np.stack([critical_window_lengths(chunks[:, j, :], D) for j in range(k)], axis=1)   # [N, k]
        return np.minimum(D + ls.mean(1), T)

    def decide(self, obs: Observation) -> np.ndarray:
        T = obs.ctrl.interval_slots
        n = obs.num_cells
        if self._delta.shape[0] != n:
            self._delta = np.zeros(n)
        self._update_calibration(obs)
        self.stats["decisions"] += 1
        self.stats["delta_mean_abs"] = float(np.mean(np.abs(self._delta)))

        q = np.asarray(self.forecaster.predict_quantiles(obs), dtype=float)   # [N, K] bits/slot
        levels = np.asarray(self.forecaster.quantiles, dtype=float)
        if not np.all(np.isfinite(q)):  # forecaster failure -> robust empirical fallback
            q = WindowQuantileForecaster(quantiles=levels).predict_quantiles(obs)
        k_target = int(np.argmin(np.abs(levels - self.target_level)))
        self._pending.append((obs.obs_slot, obs.slot + T, q[:, k_target].copy()))

        B = backlog_rate_obs(obs)
        w = deadline_weights(obs, self.w_min)
        if self.ll_weight is not None:
            w = np.where(obs.deadlines <= 10, self.ll_weight, 1.0) * np.clip(
                (T + obs.ctrl.telemetry_delay_slots) / obs.deadlines, self.w_min, 1.0)
        if self.volume_weights:
            w = obs.priorities * self._volume_factor(obs)
        if self.queue_weights > 0:
            H = T + obs.ctrl.telemetry_delay_slots
            med = np.maximum(q[:, self.forecaster.median_index], 1e-6)
            from .controllers import backlog_fh_bits
            w = w * (self.queue_weights + backlog_fh_bits(obs) / (H * med))
        cap = obs.capacity
        caps = obs.budget_caps
        delta = self._delta

        def alloc_for(lam: float) -> np.ndarray:
            p = 1.0 - lam / w
            p_eff = np.clip(p + delta, 0.0, 1.0)
            r = np.where(p <= 0.0, 0.0, B + interp_quantile(levels, q, p_eff))
            return np.clip(r, 0.0, caps)

        r0 = alloc_for(0.0)
        if r0.sum() <= cap:
            self.last_lambda = 0.0
            return waterfill(r0, np.ones(n), cap, caps)
        lo, hi = 0.0, float(w.max())
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if alloc_for(mid).sum() > cap:
                lo = mid
            else:
                hi = mid
        self.last_lambda = hi            # the common weighted tail probability of this epoch (diagnostics)
        r = alloc_for(hi)
        slack = cap - r.sum()
        if slack > 0:
            room = np.clip(alloc_for(lo) - r, 0.0, None)
            if room.sum() > 0:
                r = r + room * min(1.0, slack / room.sum())
        return r
