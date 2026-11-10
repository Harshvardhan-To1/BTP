"""Additional comparators added for the extended study.

  * PredictiveMaxWeight  - drift-plus-penalty / MaxWeight whose queue weights include the forecast arrivals of
                           the coming horizon ("predictive scheduling" in the sense of Huang et al.: the
                           back-pressure weight is the queue the cell WILL have, not the one it has). It uses
                           the same forecaster as the proposed rule but only its median, and no deadlines.
  * ClassLevelPolicy     - a parametric policy: every cell reserves B_i + F_i^{-1}(p_class(i)) and the shortage
                           is shared by weighted water-filling with a learned low-latency weight. The three
                           parameters (p_LL, p_eMBB, log w_LL) are learned by direct policy search (cross-
                           entropy method) on TRAINING seeds against the simulator, i.e. a model-free,
                           reward-driven controller with the same observation as the proposed rule. It is the
                           policy-search analogue of the DRL xApps in the O-RAN literature, restricted to a
                           parametrisation small enough to be learned reliably from a few hundred episodes.
"""
from __future__ import annotations

from typing import Dict, Any, Optional
import json
import os

import numpy as np

from .simulator import Controller, Observation
from .controllers import waterfill, deadline_weights, backlog_rate_obs, backlog_fh_bits, ewma_rate
from .proposed import interp_quantile


class PredictiveMaxWeight(Controller):
    name = "pred_maxweight"

    def __init__(self, forecaster, margin: float = 0.0, lookahead: float = 1.0):
        self.forecaster = forecaster
        self.margin = margin
        self.lookahead = lookahead     # weight of the forecast arrivals in the back-pressure term

    def decide(self, obs: Observation) -> np.ndarray:
        T = obs.ctrl.interval_slots
        H = T + obs.ctrl.telemetry_delay_slots
        q = np.asarray(self.forecaster.predict_quantiles(obs), dtype=float)
        med = q[:, self.forecaster.median_index]                       # forecast r* median (bits/slot)
        Q = backlog_fh_bits(obs)
        predicted_queue = Q + self.lookahead * H * med
        demand = np.minimum(Q / T + (1 + self.margin) * med, obs.budget_caps)
        prio = obs.priorities * predicted_queue
        order = np.argsort(-prio)
        alloc = np.zeros(obs.num_cells)
        remaining = obs.capacity
        for i in order:
            give = min(demand[i], remaining)
            alloc[i] = give
            remaining -= give
            if remaining <= 0:
                break
        return waterfill(alloc, np.ones(obs.num_cells), obs.capacity, obs.budget_caps)


class ClassLevelPolicy(Controller):
    """Per-class forecast quantile levels and a learned LL weight (parameters from policy search)."""

    name = "cem_policy"

    def __init__(self, forecaster, p_ll: float = 0.9, p_embb: float = 0.5, w_ll: float = 3.0, w_min: float = 0.25):
        self.forecaster = forecaster
        self.p_ll, self.p_embb, self.w_ll, self.w_min = float(p_ll), float(p_embb), float(w_ll), w_min

    @classmethod
    def from_file(cls, forecaster, path: str, **kw):
        with open(path) as f:
            th = json.load(f)["selected"]
        return cls(forecaster, p_ll=th["p_ll"], p_embb=th["p_embb"], w_ll=th["w_ll"], **kw)

    def decide(self, obs: Observation) -> np.ndarray:
        q = np.asarray(self.forecaster.predict_quantiles(obs), dtype=float)
        levels = np.asarray(self.forecaster.quantiles, dtype=float)
        is_ll = obs.deadlines <= 10
        p = np.where(is_ll, self.p_ll, self.p_embb)
        demand = backlog_rate_obs(obs) + interp_quantile(levels, q, p)
        w = deadline_weights(obs, self.w_min) / obs.priorities * np.where(is_ll, self.w_ll, 1.0)
        return waterfill(demand, w, obs.capacity, obs.budget_caps)


def cem_search(evaluate, mean0: np.ndarray, std0: np.ndarray, lo: np.ndarray, hi: np.ndarray, iters: int = 8,
               pop: int = 16, elite: int = 4, seed: int = 0, log=print):
    """Cross-entropy method over a box; `evaluate(thetas [pop, d]) -> costs [pop]` (lower is better)."""
    rng = np.random.default_rng(seed)
    mean, std = mean0.astype(float).copy(), std0.astype(float).copy()
    history = []
    best = (np.inf, mean.copy())
    for it in range(iters):
        thetas = np.clip(rng.normal(mean, std, size=(pop, len(mean))), lo, hi)
        thetas[0] = mean                          # always re-evaluate the current mean
        costs = np.asarray(evaluate(thetas), dtype=float)
        idx = np.argsort(costs)[:elite]
        mean = 0.7 * thetas[idx].mean(0) + 0.3 * mean                       # smoothed update
        std = np.maximum(thetas[idx].std(0), std0 * max(0.1, 0.75 ** it))  # slow floor against premature collapse
        if costs[idx[0]] < best[0]:
            best = (float(costs[idx[0]]), thetas[idx[0]].copy())
        history.append({"iter": it, "best_cost": float(costs[idx[0]]), "mean": mean.tolist(), "std": std.tolist()})
        log(f"[cem] iter {it}: best {costs[idx[0]]:.5f} mean {np.round(mean, 3).tolist()} std {np.round(std, 3).tolist()}")
    return best[1], history
