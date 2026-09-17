"""Baseline fronthaul budget controllers.

All controllers receive an Observation and return per-cell budgets in
bits/slot. The simulator projects the output onto the feasible set
{0 <= r_i <= cap_i, sum r_i <= C}, but every controller here already returns
feasible budgets.

Demand notion shared by all deadline-aware controllers (see demand.py):

    demand_i = backlog_rate_i + r*_i

where backlog_rate_i clears the observed backlog within its remaining slack
and r*_i is the (estimated or forecast) deadline-feasible rate of the unseen
horizon arrivals. The controllers differ only in HOW r*_i is estimated and
HOW the capacity is split when demand exceeds it.
"""
from __future__ import annotations

from typing import Optional
import numpy as np

from .simulator import Controller, Observation
from .demand import required_rates, backlog_rate


# ---------------------------------------------------------------------------
# allocation primitives
# ---------------------------------------------------------------------------
def waterfill(demand: np.ndarray, weights: np.ndarray, capacity: float, caps: np.ndarray,
              distribute_leftover: bool = True) -> np.ndarray:
    """Weighted proportional allocation with redistribution.

    If sum(min(demand, cap)) <= capacity every cell receives its demand and
    (optionally) the leftover is spread in proportion to remaining headroom
    (cap_i - demand_i); the leftover costs nothing because budgets are caps,
    and it gives burst headroom. Otherwise the shortage is shared: cells get
    capacity * w_i d_i / sum_j w_j d_j, iteratively respecting caps.
    """
    demand = np.clip(np.asarray(demand, dtype=float), 0.0, None)
    caps = np.asarray(caps, dtype=float)
    weights = np.clip(np.asarray(weights, dtype=float), 1e-9, None)
    n = len(demand)
    want = np.minimum(demand, caps)
    if want.sum() <= capacity:
        alloc = want.copy()
        if distribute_leftover:
            for _ in range(2):  # second pass mops up rounding at caps
                left = capacity - alloc.sum()
                room = caps - alloc
                if left > 1e-9 and room.sum() > 1e-9:
                    alloc += np.minimum(room, left * room / room.sum())
        return alloc
    # shortage: iterative weighted proportional sharing with caps
    alloc = np.zeros(n)
    active = np.ones(n, dtype=bool)
    remaining = capacity
    for _ in range(n + 1):
        wd = weights * want * active
        if wd.sum() <= 0 or remaining <= 1e-9:
            break
        share = remaining * wd / wd.sum()
        hit = active & (alloc + share >= caps)
        if not hit.any():
            alloc[active] += share[active]
            break
        alloc[hit] = caps[hit]
        active[hit] = False
        remaining = capacity - alloc.sum()
    return np.minimum(alloc, caps)


def deadline_weights(obs: Observation, w_min: float = 0.25) -> np.ndarray:
    """Heuristic cost weight of deferring one bit of cell i past this interval.

    A deferred bit surely violates when its deadline D_i <= horizon H; for
    D_i > H it may still be served later, so the weight is reduced to ~H/D_i
    (floored at w_min so that eMBB cells are never starved). Multiplied by
    the operator priority.
    """
    H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
    return obs.priorities * np.clip(H / obs.deadlines, w_min, 1.0)


def backlog_fh_bits(obs: Observation) -> np.ndarray:
    """DU backlog converted to fronthaul bits at the current spectral efficiency."""
    return obs.queue_bits / obs.se * obs.net.fh_bits_per_prb_layer


def backlog_rate_obs(obs: Observation) -> np.ndarray:
    return backlog_rate(backlog_fh_bits(obs), obs.deadlines, obs.hol_age, obs.ctrl.interval_slots,
                        obs.ctrl.telemetry_delay_slots)


def ewma_rate(history: np.ndarray, window: int) -> np.ndarray:
    """Exponentially weighted mean per-slot demand over roughly `window` slots."""
    if history.shape[1] == 0:
        return np.zeros(history.shape[0])
    alpha = 2.0 / (window + 1.0)
    h = history[:, -min(history.shape[1], 6 * window):]
    w = (1 - alpha) ** np.arange(h.shape[1])[::-1]
    return (h * w).sum(1) / w.sum()


def persistence_required_rate(obs: Observation, num_horizons: int = 1) -> np.ndarray:
    """Reactive estimate of r*: the deadline-feasible rate of the LAST observed horizon(s)."""
    H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
    hist = obs.history_fh_demand
    L = hist.shape[1]
    if L == 0:
        return np.zeros(obs.num_cells)
    k = max(1, min(num_horizons, L // H))
    window = hist[:, max(0, L - k * H):]
    return required_rates(window, obs.deadlines)


# ---------------------------------------------------------------------------
# controllers
# ---------------------------------------------------------------------------
class StaticEqualShare(Controller):
    """Fixed equal split of the link (redistributing shares above a cell's cap)."""

    name = "static_equal"

    def decide(self, obs: Observation) -> np.ndarray:
        n = obs.num_cells
        return waterfill(np.full(n, obs.capacity / n), np.ones(n), obs.capacity, obs.budget_caps)


class ReactiveProportional(Controller):
    """Demand-proportional allocation from backlog + recent average rate (deadline-unaware).

    demand_i = backlog_i / T + (1 + margin) * EWMA_i, water-filled with unit
    weights and leftover redistribution. `margin` is a safety factor tuned on
    validation scenarios.
    """

    name = "reactive_prop"

    def __init__(self, margin: float = 0.0, ewma_window: Optional[int] = None):
        self.margin = margin
        self.ewma_window = ewma_window

    def decide(self, obs: Observation) -> np.ndarray:
        T = obs.ctrl.interval_slots
        win = self.ewma_window or T
        rate = ewma_rate(obs.history_fh_demand, win)
        demand = backlog_fh_bits(obs) / T + (1 + self.margin) * rate
        return waterfill(demand, np.ones(obs.num_cells), obs.capacity, obs.budget_caps)


class QueueAwareReactive(Controller):
    """Strong reactive baseline: deadline-aware demand with persistence forecast.

    demand_i = backlog_rate_i + (1 + margin) * r*(last observed horizon, D_i),
    deadline-derived weights, water-filling with leftover redistribution.
    It has the same deadline knowledge and the same allocation rule family as
    the point-forecast controller; only the forecast is 'persistence'.
    """

    name = "queue_aware"

    def __init__(self, margin: float = 0.0, w_min: float = 0.25, num_horizons: int = 1):
        self.margin = margin
        self.w_min = w_min
        self.num_horizons = num_horizons

    def decide(self, obs: Observation) -> np.ndarray:
        rstar = persistence_required_rate(obs, self.num_horizons)
        demand = backlog_rate_obs(obs) + (1 + self.margin) * rstar
        return waterfill(demand, deadline_weights(obs, self.w_min), obs.capacity, obs.budget_caps)


class PointForecastWaterfill(Controller):
    """Same information as the proposed method but a point (median) forecast of r*.

    demand_i = backlog_rate_i + (1 + margin) * median forecast of r*_i;
    deadline-derived weights; water-fill. Isolates the effect of representing
    forecast uncertainty (margin is a tuned scalar, not a per-cell quantity).
    """

    name = "point_forecast"

    def __init__(self, forecaster, margin: float = 0.0, w_min: float = 0.25):
        self.forecaster = forecaster
        self.margin = margin
        self.w_min = w_min

    def decide(self, obs: Observation) -> np.ndarray:
        q = self.forecaster.predict_quantiles(obs)          # [N, K] bits/slot
        median = q[:, self.forecaster.median_index]
        demand = backlog_rate_obs(obs) + (1 + self.margin) * median
        return waterfill(demand, deadline_weights(obs, self.w_min), obs.capacity, obs.budget_caps)


class OracleWaterfill(Controller):
    """Upper-bound reference: knows the actual arrivals over the horizon.

    Not implementable in practice; it bounds what an interval-level
    point-forecast controller could achieve with the same allocation rule.
    """

    name = "oracle"
    is_oracle = True

    def __init__(self, w_min: float = 0.25):
        self.w_min = w_min

    def decide_oracle(self, obs: Observation, future_fh_demand: np.ndarray) -> np.ndarray:
        rstar = required_rates(future_fh_demand, obs.deadlines)
        demand = backlog_rate_obs(obs) + rstar
        return waterfill(demand, deadline_weights(obs, self.w_min), obs.capacity, obs.budget_caps)
