"""Priced adaptive compression (PAC): per-cell, per-interval BFP bitwidth chosen jointly with the budget.

Physical model (split 7-2x, BFP, frequency-domain IQ)
-----------------------------------------------------
A cell whose radio link supports spectral efficiency se (user bits per PRB-layer per slot at the
reference BFP-9 compression) has an equivalent SNR given by se_RE = log2(1 + SNR), se_RE = se / 134.4
(134.4 data REs per PRB-layer per slot). Compressing the IQ with a b-bit BFP mantissa adds
quantisation noise with signal-to-quantisation-noise ratio SQNR(b) (measured once on complex Gaussian
OFDM samples with one shared exponent per PRB), so the link sees

    SINR_b = 1 / (1/SNR + 1/SQNR(b)),     g(b) = log2(1 + SINR_b) / log2(1 + SNR)   (<= 1).

Serving one user bit at bitwidth b costs kappa(b) = [beta(b) / beta(9)] / g(b) times the fronthaul
bits of BFP-9, and costs 1/g(b) - 1 extra air resources (PRB-layers): the quality loss.

Decision rule (PAC)
-------------------
1. Solve the KKT newsvendor allocation (B1) at BFP-9 and read the link price lambda.
2. Each cell picks b minimising   lambda * kappa_i(b) + mu * w_i * loss_i(b):
   bits are only worth saving when the link is priced (lambda > 0), and the cells whose SNR leaves
   room for quantisation noise (low se) are the ones that compress.
3. Re-solve the allocation with every cell's demand distribution scaled by kappa_i(b_i); repeat 2-3.

mu is the operator's exchange rate between deadline violations and air-resource loss; sweeping it
traces the violation / loss trade-off curve compared against the baselines in exp_adaptive_compression.py.
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Optional, Tuple

import numpy as np

from .config import SimConfig, fronthaul_bits_per_prb_layer_slot
from .controllers import deadline_weights, backlog_rate_obs, waterfill
from .forecast import WindowQuantileForecaster
from .proposed import interp_quantile
from .simulator import Observation, project_budgets
from .traffic import TrafficTrace, generate_traffic

BITWIDTHS = (9, 8, 7, 6, 5, 4)
DATA_RES = 168 * 0.8


@lru_cache(maxsize=None)
def sqnr_db(b: int, n_prb: int = 20000, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    x = (rng.standard_normal((n_prb, 12)) + 1j * rng.standard_normal((n_prb, 12))) / np.sqrt(2)
    peak = np.max(np.maximum(np.abs(x.real), np.abs(x.imag)), axis=1, keepdims=True)
    exp = np.ceil(np.log2(peak))                      # shared power-of-two exponent per PRB
    lv = 2 ** (b - 1) - 1
    scale = 2.0 ** exp / lv
    q = np.clip(np.round(x.real / scale), -lv, lv) * scale + 1j * np.clip(np.round(x.imag / scale), -lv, lv) * scale
    return float(10 * np.log10(np.mean(np.abs(x) ** 2) / np.mean(np.abs(x - q) ** 2)))


def beta(b: int) -> float:
    return fronthaul_bits_per_prb_layer_slot(b)


def rate_gain(b, se):
    snr = 2.0 ** (np.asarray(se, dtype=float) / DATA_RES) - 1.0
    sqnr = 10 ** (sqnr_db(int(b)) / 10)
    sinr = 1.0 / (1.0 / snr + 1.0 / sqnr)
    return np.log2(1 + sinr) / np.log2(1 + snr)


def kappa(b, se):
    return beta(b) / beta(9) / rate_gain(b, se)


def loss(b, se):
    return 1.0 / rate_gain(b, se) - 1.0


# ---------------------------------------------------------------------------
# controllers: decide(obs) -> (budgets [N] raw fronthaul bits/slot, bitwidths [N])
# ---------------------------------------------------------------------------
class _KKTCore:
    """B1 KKT newsvendor allocation with per-cell demand scaling (demand in BFP-9 units)."""

    def __init__(self, w_min: float = 0.25):
        self.fc = WindowQuantileForecaster()
        self.w_min = w_min

    def solve(self, obs: Observation, scale: np.ndarray) -> Tuple[np.ndarray, float]:
        q = np.asarray(self.fc.predict_quantiles(obs), dtype=float) * scale[:, None]
        levels = np.asarray(self.fc.quantiles, dtype=float)
        B = backlog_rate_obs(obs) * scale
        w = deadline_weights(obs, self.w_min)
        cap, n = obs.capacity, obs.num_cells
        caps = obs.budget_caps * scale

        def alloc(lam):
            p = np.clip(1.0 - lam / w, 0.0, 1.0)
            r = np.where(p <= 0.0, 0.0, B + interp_quantile(levels, q, p))
            return np.clip(r, 0.0, caps)

        r0 = alloc(0.0)
        if r0.sum() <= cap:
            return waterfill(r0, np.ones(n), cap, caps), 0.0
        lo, hi = 0.0, float(w.max())
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if alloc(mid).sum() > cap else (lo, mid)
        r = alloc(hi)
        room = np.clip(alloc(lo) - r, 0.0, None)
        if cap - r.sum() > 0 and room.sum() > 0:
            r = r + room * min(1.0, (cap - r.sum()) / room.sum())
        return r, hi


class FixedBitwidth:
    def __init__(self, b: int):
        self.b, self.core, self.name = b, _KKTCore(), f"fixed-{b}"

    def decide(self, obs):
        bits = np.full(obs.num_cells, self.b)
        r, _ = self.core.solve(obs, kappa(self.b, obs.se))
        return r, bits


class StaticSNRAware:
    """Per-cell fixed bitwidth: the lowest b whose air-resource loss at the cell's nominal se is <= eps."""

    def __init__(self, eps: float):
        self.eps, self.core, self.name = eps, _KKTCore(), f"static-snr-{eps:g}"

    def decide(self, obs):
        se_nom = np.array([c.se_bits_per_prb_layer for c in obs.net.cells])
        bits = np.array([min([b for b in BITWIDTHS if loss(b, s) <= self.eps] or [9]) for s in se_nom])
        return self.core.solve(obs, np.array([kappa(b, s) for b, s in zip(bits, obs.se)]))[0], bits


class LoadReactive:
    """Threshold load-adaptive compression: BFP-9 while the link is unpriced, all cells to b_low when congested."""

    def __init__(self, b_low: int):
        self.b_low, self.core, self.name = b_low, _KKTCore(), f"reactive-{b_low}"

    def decide(self, obs):
        r, lam = self.core.solve(obs, np.ones(obs.num_cells))
        if lam <= 0:
            return r, np.full(obs.num_cells, 9)
        bits = np.full(obs.num_cells, self.b_low)
        return self.core.solve(obs, kappa(self.b_low, obs.se))[0], bits


class LoadReactiveSNR:
    """Congestion trigger + per-cell SNR-aware bitwidth (lowest b with loss <= eps), no price grading."""

    def __init__(self, eps: float):
        self.eps, self.core, self.name = eps, _KKTCore(), f"reactive-snr-{eps:g}"

    def decide(self, obs):
        r, lam = self.core.solve(obs, np.ones(obs.num_cells))
        if lam <= 0:
            return r, np.full(obs.num_cells, 9)
        bits = np.array([min([b for b in BITWIDTHS if loss(b, s) <= self.eps] or [9]) for s in obs.se])
        return self.core.solve(obs, np.array([kappa(b, s) for b, s in zip(bits, obs.se)]))[0], bits


class PricedAdaptiveCompression:
    def __init__(self, mu: float, iters: int = 2):
        self.mu, self.iters, self.core, self.name = mu, iters, _KKTCore(), f"pac-{mu:g}"

    def decide(self, obs):
        n = obs.num_cells
        bits = np.full(n, 9)
        r, lam = self.core.solve(obs, np.ones(n))
        if lam <= 0:
            return r, bits
        w = deadline_weights(obs, self.core.w_min)
        K = np.array([kappa(b, obs.se) for b in BITWIDTHS])          # [nb, N]
        L = np.array([loss(b, obs.se) for b in BITWIDTHS])
        for _ in range(self.iters):
            bits = np.array(BITWIDTHS)[np.argmin(lam * K + self.mu * w * L, axis=0)]
            r, lam_new = self.core.solve(obs, np.array([kappa(b, s) for b, s in zip(bits, obs.se)]))
            if lam_new <= 0:
                break
            lam = lam_new
        return r, bits


class PACOnStatic(PricedAdaptiveCompression):
    """PAC whose bitwidths never exceed the static SNR-aware choice (static floor + priced extra compression)."""

    def __init__(self, mu: float, eps: float):
        super().__init__(mu)
        self.static = StaticSNRAware(eps)
        self.name = f"pac-static-{mu:g}-{eps:g}"

    def decide(self, obs):
        _, floor_bits = self.static.decide(obs)
        n = obs.num_cells
        r, lam = self.core.solve(obs, np.array([kappa(b, s) for b, s in zip(floor_bits, obs.se)]))
        if lam <= 0:
            return r, floor_bits
        w = deadline_weights(obs, self.core.w_min)
        K = np.array([kappa(b, obs.se) for b in BITWIDTHS])
        L = np.array([loss(b, obs.se) for b in BITWIDTHS])
        bits = np.minimum(floor_bits, np.array(BITWIDTHS)[np.argmin(lam * K + self.mu * w * L, axis=0)])
        return self.core.solve(obs, np.array([kappa(b, s) for b, s in zip(bits, obs.se)]))[0], bits


# ---------------------------------------------------------------------------
# simulator with per-cell bitwidth (same queue/deadline model as simulator.run_simulation)
# ---------------------------------------------------------------------------
def simulate(cfg: SimConfig, controller, trace: Optional[TrafficTrace] = None) -> dict:
    net, ctrl = cfg.network, cfg.control
    n, S, T, tau = net.num_cells, cfg.num_slots, ctrl.interval_slots, ctrl.telemetry_delay_slots
    cap = net.usable_bits_per_slot
    deadlines = np.array([c.deadline_slots for c in net.cells], dtype=int)
    prio = np.array([c.priority for c in net.cells])
    max_pl = np.array([net.prbs_per_cell * c.layers for c in net.cells], dtype=float)
    if trace is None:
        trace = generate_traffic(net, cfg.traffic, S, cfg.seed)
    Dmax = int(deadlines.max())
    cohort = np.zeros((n, Dmax + 1))
    q_hist, hol_hist = np.zeros((tau + 1, n)), np.zeros((tau + 1, n))
    budgets = np.full(n, cap / n)
    bits = np.full(n, 9)
    prev = budgets.copy()
    arrived, served, violated = np.zeros(n), np.zeros(n), np.zeros(n)
    air_used, air_ref, bits_served = 0.0, 0.0, 0.0
    fh_used = 0.0
    dts = []
    counted = 0
    for t in range(S):
        if t % T == 0:
            k = min(tau, t)
            obs_slot = max(0, t - tau)
            obs = Observation(slot=t, obs_slot=obs_slot, queue_bits=q_hist[k].copy(), hol_age=hol_hist[k].copy(),
                              se=trace.se[:, obs_slot].copy(), history_fh_demand=trace.fh_demand_bits[:, :obs_slot],
                              history_arrivals=trace.arrivals_bits[:, :obs_slot], prev_budgets=prev.copy(),
                              net=net, ctrl=ctrl)
            t0 = time.perf_counter()
            raw, bits = controller.decide(obs)
            dts.append((time.perf_counter() - t0) * 1e3)
            budgets = project_budgets(np.asarray(raw, dtype=float), cap, np.array(net.peak_bits_per_slot))
            prev = budgets.copy()
        a_t = trace.arrivals_bits[:, t]
        cohort[:, 0] += a_t
        se_ref = trace.se[:, t]
        g = np.array([rate_gain(b, s) for b, s in zip(bits, se_ref)])
        se_t = se_ref * g
        bt = np.array([beta(b) for b in bits])
        pl_avail = np.minimum(max_pl, np.floor(budgets / bt))
        to_serve = np.minimum(cohort.sum(1), pl_avail * se_t)
        pl_used = np.ceil(to_serve / se_t - 1e-9)
        for i in range(n):
            rem = to_serve[i]
            for a in range(deadlines[i], -1, -1):
                if rem <= 0:
                    break
                x = min(cohort[i, a], rem)
                cohort[i, a] -= x
                rem -= x
        viol = np.zeros(n)
        for i in range(n):
            d = deadlines[i]
            viol[i] = cohort[i, d]
            cohort[i, 1:d + 1] = cohort[i, 0:d]
            cohort[i, 0] = 0.0
            cohort[i, d + 1:] = 0.0
        q_after = cohort.sum(1)
        hol = np.array([(np.nonzero(cohort[i] > 0)[0].max() if q_after[i] > 0 else 0) for i in range(n)], float)
        q_hist, hol_hist = np.roll(q_hist, 1, 0), np.roll(hol_hist, 1, 0)
        q_hist[0], hol_hist[0] = q_after, hol
        if t >= cfg.warmup_slots:
            arrived += a_t
            served += to_serve
            violated += viol
            air_used += (to_serve / se_t).sum()
            air_ref += (to_serve / se_ref).sum()
            bits_served += (to_serve * bits).sum()
            fh_used += (pl_used * bt).sum()
            counted += 1
    dl = deadlines <= 10
    return {
        "controller": controller.name,
        "weighted_violation_ratio": float((prio * violated).sum() / max((prio * arrived).sum(), 1e-9)),
        "violation_ratio": float(violated.sum() / max(arrived.sum(), 1e-9)),
        "violation_ratio_ll": float(violated[dl].sum() / max(arrived[dl].sum(), 1e-9)),
        "violation_ratio_embb": float(violated[~dl].sum() / max(arrived[~dl].sum(), 1e-9)),
        "air_loss": float(air_used / max(air_ref, 1e-9) - 1.0),
        "mean_bitwidth": float(bits_served / max(served.sum(), 1e-9)),
        "fh_utilisation": float(fh_used / (cap * max(counted, 1))),
        "offered_load": float(trace.mean_fh_load),
        "decision_ms_mean": float(np.mean(dts)),
    }
