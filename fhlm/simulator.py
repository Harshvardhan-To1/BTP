"""Slot-level simulator of N split 7-2x cells sharing one fronthaul link.

Model (downlink, O-DU -> O-RU U-plane):

  * Each cell i keeps a DU-side user-plane queue Q_i (bits) fed by exogenous
    arrivals A_i(t). Bits are tracked by age so that a bit older than the
    cell's deadline D_i (slots) is discarded and counted as a violation.
  * Once per control interval (T slots) a controller assigns fronthaul
    budgets r_i (bits/slot) with sum_i r_i <= C_usable and r_i <= r_i^max.
    The budgets are held fixed for the interval (reservation lead time).
  * Within a slot, cell i's DU scheduler can transmit at most
    floor(r_i / beta) PRB-layers (beta = fronthaul bits per PRB-layer) and at
    most PRB_max * L_i PRB-layers (air interface); each PRB-layer carries
    se_i(t) user bits. Bits are served FIFO (oldest first).
  * Because sum_i r_i <= C_usable is enforced at decision time and each cell
    never exceeds its own budget, the shared link is never overloaded and the
    fronthaul transport queue is trivially bounded; the congestion shows up
    as DU-side queueing delay and deadline violations instead.

Information model: controllers observe the state that is tau slots old
(telemetry delay) and never see future arrivals, except the explicit
oracle controller used as an upper bound.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import math
import time

import numpy as np

from .config import SimConfig, NetworkConfig, ControlConfig
from .traffic import TrafficTrace, generate_traffic


@dataclass
class Observation:
    """Everything a (non-oracle) controller may use at a decision epoch."""

    slot: int                          # decision slot t; budgets apply to [t, t+T)
    obs_slot: int                      # slot of the most recent observed state (t - tau)
    queue_bits: np.ndarray             # [N] DU backlog at obs_slot
    hol_age: np.ndarray                # [N] age (slots) of the oldest bits at obs_slot
    se: np.ndarray                     # [N] spectral efficiency at obs_slot (user bits / PRB-layer)
    history_fh_demand: np.ndarray      # [N, obs_slot] per-slot fronthaul-equivalent demand (bits)
    history_arrivals: np.ndarray       # [N, obs_slot] per-slot user-bit arrivals
    prev_budgets: np.ndarray           # [N] budgets used in the previous interval (bits/slot)
    net: NetworkConfig
    ctrl: ControlConfig

    @property
    def num_cells(self) -> int:
        return self.queue_bits.shape[0]

    @property
    def capacity(self) -> float:
        return self.net.usable_bits_per_slot

    @property
    def budget_caps(self) -> np.ndarray:
        return np.array(self.net.peak_bits_per_slot)

    @property
    def deadlines(self) -> np.ndarray:
        return np.array([c.deadline_slots for c in self.net.cells], dtype=float)

    @property
    def priorities(self) -> np.ndarray:
        return np.array([c.priority for c in self.net.cells], dtype=float)


class Controller:
    """Base class. Subclasses implement decide()."""

    name = "base"
    is_oracle = False

    def reset(self, net: NetworkConfig, ctrl: ControlConfig, rng: Optional[np.random.Generator] = None) -> None:
        pass

    def decide(self, obs: Observation) -> np.ndarray:  # bits per slot per cell
        raise NotImplementedError

    def decide_oracle(self, obs: Observation, future_fh_demand: np.ndarray) -> np.ndarray:
        raise NotImplementedError


def project_budgets(budgets: np.ndarray, capacity: float, caps: np.ndarray) -> np.ndarray:
    """Enforce 0 <= r_i <= cap_i and sum r_i <= capacity (scale down if violated)."""
    b = np.clip(np.nan_to_num(budgets, nan=0.0), 0.0, caps)
    total = b.sum()
    if total > capacity and total > 0:
        b = b * (capacity / total)
    return b


@dataclass
class SimResult:
    controller: str
    config: Dict[str, Any]
    metrics: Dict[str, Any]
    per_cell: Dict[str, List[float]]
    timeseries: Optional[Dict[str, np.ndarray]] = None
    decision_times_ms: List[float] = field(default_factory=list)


def jain_index(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    if np.all(x == 0):
        return 1.0
    return float(x.sum() ** 2 / (len(x) * (x ** 2).sum()))


def run_simulation(cfg: SimConfig, controller: Controller, trace: Optional[TrafficTrace] = None,
                   record_timeseries: bool = False) -> SimResult:
    net, ctrl = cfg.network, cfg.control
    n = net.num_cells
    S = cfg.num_slots
    T = ctrl.interval_slots
    tau = ctrl.telemetry_delay_slots
    beta = net.fh_bits_per_prb_layer
    cap = net.usable_bits_per_slot
    caps = np.array(net.peak_bits_per_slot)
    deadlines = np.array([c.deadline_slots for c in net.cells], dtype=int)
    max_prb_layers = np.array([net.prbs_per_cell * c.layers for c in net.cells], dtype=float)

    if trace is None:
        trace = generate_traffic(net, cfg.traffic, S, cfg.seed)
    assert trace.num_cells == n and trace.num_slots >= S

    rng = np.random.default_rng(cfg.seed + 12345)
    controller.reset(net, ctrl, rng)

    # age-indexed cohorts: cohort[i, a] = bits of cell i that have waited a slots
    Dmax = int(deadlines.max())
    cohort = np.zeros((n, Dmax + 1))

    # delayed-state ring buffers (tau + 1 entries)
    q_hist = np.zeros((tau + 1, n))
    hol_hist = np.zeros((tau + 1, n))

    budgets = np.full(n, cap / n)
    budgets = project_budgets(budgets, cap, caps)
    prev_budgets = budgets.copy()

    # accumulators (post warm-up)
    arrived = np.zeros(n)
    served = np.zeros(n)
    violated = np.zeros(n)
    delay_hist = np.zeros((n, Dmax + 1))       # served bits by delay (slots)
    fh_used_total = 0.0
    fh_alloc_total = 0.0
    fh_alloc_cell = np.zeros(n)
    fh_used_cell = np.zeros(n)
    queue_sum = np.zeros(n)
    slots_counted = 0
    decision_times: List[float] = []
    ts = None
    if record_timeseries:
        ts = {
            "fh_demand": np.zeros((n, S)), "budget": np.zeros((n, S)), "fh_used": np.zeros((n, S)),
            "queue": np.zeros((n, S)), "violated": np.zeros((n, S)),
        }

    for t in range(S):
        # --- control epoch --------------------------------------------------
        if t % T == 0:
            obs_slot = max(0, t - tau)
            k = min(tau, t)  # how far back the observed state is
            obs = Observation(
                slot=t, obs_slot=obs_slot,
                queue_bits=q_hist[k].copy(), hol_age=hol_hist[k].copy(),
                se=trace.se[:, obs_slot].copy(),
                history_fh_demand=trace.fh_demand_bits[:, :obs_slot],
                history_arrivals=trace.arrivals_bits[:, :obs_slot],
                prev_budgets=prev_budgets.copy(), net=net, ctrl=ctrl,
            )
            t0 = time.perf_counter()
            if controller.is_oracle:
                fut = trace.fh_demand_bits[:, obs_slot:min(S, t + T)]
                raw = controller.decide_oracle(obs, fut)
            else:
                raw = controller.decide(obs)
            decision_times.append((time.perf_counter() - t0) * 1e3)
            budgets = project_budgets(np.asarray(raw, dtype=float), cap, caps)
            prev_budgets = budgets.copy()

        # --- arrivals ---------------------------------------------------------
        a_t = trace.arrivals_bits[:, t]
        cohort[:, 0] += a_t
        se_t = trace.se[:, t]

        # --- service (FIFO, oldest first) ------------------------------------
        prb_layers_avail = np.minimum(max_prb_layers, np.floor(budgets / beta))
        servable = prb_layers_avail * se_t
        q_before = cohort.sum(1)
        to_serve = np.minimum(q_before, servable)
        served_t = to_serve.copy()
        fh_used_t = np.ceil(to_serve / se_t - 1e-9) * beta
        fh_used_t = np.minimum(fh_used_t, budgets)  # numerical guard; cannot exceed budget
        for i in range(n):
            rem = to_serve[i]
            if rem <= 0:
                continue
            for a in range(deadlines[i], -1, -1):
                if rem <= 0:
                    break
                x = min(cohort[i, a], rem)
                if x > 0:
                    cohort[i, a] -= x
                    rem -= x
                    if t >= cfg.warmup_slots:
                        delay_hist[i, a] += x

        # --- ageing and deadline drops ----------------------------------------
        viol_t = np.zeros(n)
        for i in range(n):
            d = deadlines[i]
            viol_t[i] = cohort[i, d]                  # would exceed deadline next slot
            cohort[i, 1:d + 1] = cohort[i, 0:d]
            cohort[i, 0] = 0.0
            if d < Dmax:
                cohort[i, d + 1:] = 0.0
        q_after = cohort.sum(1)
        hol = np.array([(np.nonzero(cohort[i] > 0)[0].max() if q_after[i] > 0 else 0) for i in range(n)], dtype=float)

        # delayed-state buffers
        q_hist = np.roll(q_hist, 1, axis=0)
        hol_hist = np.roll(hol_hist, 1, axis=0)
        q_hist[0] = q_after
        hol_hist[0] = hol

        # --- accounting ---------------------------------------------------------
        if t >= cfg.warmup_slots:
            arrived += a_t
            served += served_t
            violated += viol_t
            fh_used_total += fh_used_t.sum()
            fh_alloc_total += budgets.sum()
            fh_alloc_cell += budgets
            fh_used_cell += fh_used_t
            queue_sum += q_after
            slots_counted += 1
        if ts is not None:
            ts["fh_demand"][:, t] = trace.fh_demand_bits[:, t]
            ts["budget"][:, t] = budgets
            ts["fh_used"][:, t] = fh_used_t
            ts["queue"][:, t] = q_after
            ts["violated"][:, t] = viol_t

    # bits still queued at the end are neither served nor violated (small; reported)
    residual = cohort.sum(1)
    slot_ms = net.slot_duration_s * 1e3
    delays = np.arange(Dmax + 1) * slot_ms
    mean_delay = np.array([(delay_hist[i] * delays).sum() / delay_hist[i].sum() if delay_hist[i].sum() > 0 else 0.0
                           for i in range(n)])

    def pct_delay(i: int, p: float) -> float:
        h = delay_hist[i]
        if h.sum() == 0:
            return 0.0
        c = np.cumsum(h) / h.sum()
        return float(delays[int(np.searchsorted(c, p))])

    tot_arr = arrived.sum()
    prio = np.array([c.priority for c in net.cells])
    service_ratio = np.divide(served, arrived, out=np.ones(n), where=arrived > 0)
    all_hist = delay_hist.sum(0)
    all_c = np.cumsum(all_hist) / max(all_hist.sum(), 1e-9)
    metrics = {
        "violation_ratio": float(violated.sum() / tot_arr) if tot_arr > 0 else 0.0,
        "weighted_violation_ratio": float((prio * violated).sum() / max((prio * arrived).sum(), 1e-9)),
        "violation_ratio_ll": float(violated[deadlines <= 10].sum() / max(arrived[deadlines <= 10].sum(), 1e-9)),
        "violation_ratio_embb": float(violated[deadlines > 10].sum() / max(arrived[deadlines > 10].sum(), 1e-9)),
        "served_ratio": float(served.sum() / tot_arr) if tot_arr > 0 else 1.0,
        "fh_utilisation": float(fh_used_total / (cap * slots_counted)) if slots_counted else 0.0,
        "fh_allocated_fraction": float(fh_alloc_total / (cap * slots_counted)) if slots_counted else 0.0,
        "fh_unused_allocation_fraction": float((fh_alloc_total - fh_used_total) / max(fh_alloc_total, 1e-9)),
        "offered_fh_load": float(trace.fh_demand_bits[:, cfg.warmup_slots:S].sum() / (cap * slots_counted)) if slots_counted else 0.0,
        "mean_queueing_delay_ms": float((all_hist * delays).sum() / max(all_hist.sum(), 1e-9)),
        "p99_queueing_delay_ms": float(delays[int(np.searchsorted(all_c, 0.99))]) if all_hist.sum() > 0 else 0.0,
        "mean_backlog_bits": float(queue_sum.sum() / max(slots_counted, 1)),
        "jain_fairness_service_ratio": jain_index(service_ratio),
        "min_cell_service_ratio": float(service_ratio.min()),
        "residual_backlog_bits": float(residual.sum()),
        "decision_time_ms_mean": float(np.mean(decision_times)) if decision_times else 0.0,
        "decision_time_ms_p95": float(np.percentile(decision_times, 95)) if decision_times else 0.0,
        "num_decisions": len(decision_times),
        "slots_counted": slots_counted,
    }
    per_cell = {
        "name": [c.name for c in net.cells],
        "arrived_bits": arrived.tolist(), "served_bits": served.tolist(), "violated_bits": violated.tolist(),
        "violation_ratio": np.divide(violated, arrived, out=np.zeros(n), where=arrived > 0).tolist(),
        "mean_delay_ms": mean_delay.tolist(),
        "p99_delay_ms": [pct_delay(i, 0.99) for i in range(n)],
        "mean_budget_bits_per_slot": (fh_alloc_cell / max(slots_counted, 1)).tolist(),
        "mean_fh_used_bits_per_slot": (fh_used_cell / max(slots_counted, 1)).tolist(),
        "mean_fh_demand_bits_per_slot": trace.fh_demand_bits[:, cfg.warmup_slots:S].mean(1).tolist(),
        "mean_backlog_bits": (queue_sum / max(slots_counted, 1)).tolist(),
    }
    return SimResult(controller=controller.name, config=_cfg_dict(cfg), metrics=metrics,
                     per_cell=per_cell, timeseries=ts, decision_times_ms=decision_times)


def _cfg_dict(cfg: SimConfig) -> Dict[str, Any]:
    import json
    return json.loads(cfg.to_json())
