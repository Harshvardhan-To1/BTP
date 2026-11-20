"""Capacity-constrained fronthaul bit allocation across cells.

Problem (per OFDM symbol, per scheduling interval)
--------------------------------------------------
``C`` cells (RUs) share one fronthaul link of capacity ``C_link`` bits per
OFDM symbol.  Each cell ``k`` picks one operating point ``a_k`` from a finite
menu (e.g. CSEE ``(K, bits)`` or BFP ``bits``).  Every operating point has an
exactly known rate ``R_k(a)`` (bit accounting) and a predicted linear NMSE
``D_k(a)`` obtained from the cell's own received matrix without running the
encoder (Proposition 1 for CSEE, the BFP noise model for BFP).

    minimise   sum_k D_k(a_k)          (or  max_k D_k(a_k))
    subject to sum_k R_k(a_k) <= C_link,   a_k in menu.

This is a multiple-choice knapsack.  ``greedy_allocate`` is the standard
marginal-gain heuristic: start every cell at its cheapest point and repeatedly
apply the upgrade with the largest distortion reduction per extra bit that
still fits.  With the per-cell (rate, distortion) points reduced to their
lower convex hull the greedy is the Lagrangian-relaxation optimum up to one
fractional upgrade, which is the usual guarantee for this class of problem.

Overload
--------
If even the cheapest operating point of every cell does not fit, cells are
dropped (not transported this interval, distortion counted as 1.0 = 0 dB)
starting with the cells whose cheapest point is predicted to be *least*
useful (largest predicted distortion), until the rest fit.

Baselines
---------
``uniform_allocate`` gives all cells the same operating point (the best one
that fits) -- the static configuration an operator would set today.  Running
``greedy_allocate`` with *measured* instead of predicted distortions gives an
oracle that isolates the cost of prediction error (ablation).

Units: rates in bits per OFDM symbol; ``bits_per_symbol_to_gbps`` converts with
14 symbols per 1 ms slot (15 kHz numerology).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from ..encoder.bfp import bfp_quantization_noise_energy
from ..encoder.csee import CSEEEncoder

SYMBOLS_PER_SECOND = 14_000          # 14 OFDM symbols per 1 ms slot (mu = 0, normal CP)


def bits_per_symbol_to_gbps(bits: float) -> float:
    return float(bits) * SYMBOLS_PER_SECOND / 1e9


@dataclass
class Menu:
    """A family of operating points with rates and per-cell predicted distortions."""
    name: str
    labels: list[str]
    params: list[dict]
    rates: np.ndarray                  # (n_options,) bits per symbol (same for every cell)
    predicted: np.ndarray              # (n_cells, n_options) linear NMSE predictions
    prediction_time_s: float = 0.0

    @property
    def n_cells(self) -> int:
        return self.predicted.shape[0]


def build_csee_menu(Y_batch: np.ndarray, Ks, bits_list, block_size: int = 12,
                    noise_var=None) -> Menu:
    """CSEE operating points; predictions use Proposition 1 from one IFFT per cell.

    ``noise_var`` (scalar or per-cell array of sigma^2) switches the predicted
    distortion to the noise-aware, signal-referenced form (see
    :meth:`CSEEEncoder.predict_menu`); the controller then stops spending bits
    on representing noise in low-SNR cells.
    """
    t0 = time.perf_counter()
    n_cells, M, N = Y_batch.shape
    params, labels, rates = [], [], []
    for K in Ks:
        for b in bits_list:
            params.append({"K": int(K), "bits": int(b)})
            labels.append(f"CSEE K={K} b={b}")
            rates.append(CSEEEncoder.predicted_bits(M, N, K, b, block_size))
    nv = None if noise_var is None else np.broadcast_to(np.asarray(noise_var, dtype=float), (n_cells,))
    pred = np.empty((n_cells, len(params)))
    for c in range(n_cells):
        Yd = CSEEEncoder.delay_domain(Y_batch[c])
        pred[c] = CSEEEncoder.predict_menu(Yd, Ks, bits_list, block_size,
                                           None if nv is None else float(nv[c])).reshape(-1)   # K-major
    name = "CSEE" if noise_var is None else "CSEE-noise-aware"
    return Menu(name, labels, params, np.array(rates, dtype=float), pred, time.perf_counter() - t0)


def build_bfp_menu(Y_batch: np.ndarray, bits_list, block_size: int = 12) -> Menu:
    t0 = time.perf_counter()
    n_cells, M, N = Y_batch.shape
    n_blocks = -(-N // block_size)
    params = [{"bits": int(b)} for b in bits_list]
    labels = [f"BFP b={b}" for b in bits_list]
    rates = np.array([2 * b * M * N + 4 * M * n_blocks for b in bits_list], dtype=float)
    pred = np.empty((n_cells, len(params)))
    for c in range(n_cells):
        e = float(np.linalg.norm(Y_batch[c], "fro") ** 2)
        for j, b in enumerate(bits_list):
            pred[c, j] = 0.0 if e == 0 else bfp_quantization_noise_energy(Y_batch[c], b, block_size) / e
    return Menu("BFP", labels, params, rates, pred, time.perf_counter() - t0)


@dataclass
class AllocationResult:
    choice: np.ndarray                 # (n_cells,) option index, -1 = dropped
    dropped: np.ndarray                # (n_cells,) bool
    total_rate: float                  # bits per symbol actually used
    capacity: float
    predicted: np.ndarray              # (n_cells,) predicted linear NMSE (1.0 for dropped)
    decision_time_s: float
    policy: str
    upgrades: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def utilization(self) -> float:
        return float(self.total_rate / self.capacity) if self.capacity > 0 else float("inf")

    @property
    def feasible(self) -> bool:
        return bool(self.total_rate <= self.capacity + 1e-9)


def _lower_hull(rates: np.ndarray, dist: np.ndarray) -> list[int]:
    """Indices of options on the lower-left convex hull of (rate, distortion), rate ascending."""
    order = np.argsort(rates, kind="stable")
    hull: list[int] = []
    for j in order:
        # Drop dominated points (not strictly better than the last kept one).
        if hull and dist[j] >= dist[hull[-1]]:
            continue
        # Keep convexity: slopes must become less negative.
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            s1 = (dist[b] - dist[a]) / max(rates[b] - rates[a], 1e-12)
            s2 = (dist[j] - dist[b]) / max(rates[j] - rates[b], 1e-12)
            if s2 < s1:        # b lies above the chord a->j
                hull.pop()
            else:
                break
        hull.append(int(j))
    return hull


def _validate(rates: np.ndarray, dist: np.ndarray, capacity: float) -> None:
    if rates.ndim != 1 or dist.ndim != 2 or dist.shape[1] != rates.shape[0]:
        raise ValueError("rates must be (n_options,) and dist (n_cells, n_options)")
    if capacity < 0:
        raise ValueError("capacity must be non-negative")
    if np.any(rates <= 0):
        raise ValueError("all rates must be positive")
    if np.any(~np.isfinite(dist)) or np.any(dist < 0):
        raise ValueError("distortions must be finite and non-negative")


def greedy_allocate(rates: np.ndarray, dist: np.ndarray, capacity: float,
                    objective: str = "sum", use_hull: bool = True) -> AllocationResult:
    """Marginal-gain allocation (see module docstring).

    ``objective="sum"`` minimises total distortion; ``"max"`` always upgrades
    the currently worst cell (min-max fairness).
    """
    t0 = time.perf_counter()
    rates = np.asarray(rates, dtype=float); dist = np.asarray(dist, dtype=float)
    _validate(rates, dist, capacity)
    if objective not in ("sum", "max"):
        raise ValueError("objective must be 'sum' or 'max'")
    n_cells = dist.shape[0]
    notes: list[str] = []
    hulls = [_lower_hull(rates, dist[c]) if use_hull else list(np.argsort(rates)) for c in range(n_cells)]
    pos = np.zeros(n_cells, dtype=int)                      # index into each cell's hull
    choice = np.array([h[0] for h in hulls], dtype=int)
    dropped = np.zeros(n_cells, dtype=bool)

    # Overload: drop least-useful cells until the cheapest points fit.
    used = float(rates[choice].sum())
    if used > capacity:
        order = np.argsort(-dist[np.arange(n_cells), choice], kind="stable")
        for c in order:
            if used <= capacity:
                break
            dropped[c] = True
            used -= rates[choice[c]]
        notes.append(f"overload: dropped {int(dropped.sum())} of {n_cells} cells")
    remaining = capacity - used
    upgrades = 0
    while True:
        best, best_gain = -1, 0.0
        cur = np.where(dropped, np.inf, dist[np.arange(n_cells), choice])
        for c in range(n_cells):
            if dropped[c] or pos[c] + 1 >= len(hulls[c]):
                continue
            nxt = hulls[c][pos[c] + 1]
            dr = rates[nxt] - rates[choice[c]]
            if dr > remaining + 1e-9:
                continue
            dd = dist[c, choice[c]] - dist[c, nxt]
            gain = dd / dr if objective == "sum" else cur[c]
            if gain > best_gain or (objective == "max" and best < 0):
                best, best_gain = c, gain
        if best < 0:
            break
        nxt = hulls[best][pos[best] + 1]
        remaining -= rates[nxt] - rates[choice[best]]
        pos[best] += 1
        choice[best] = nxt
        upgrades += 1
    total = float(rates[choice[~dropped]].sum()) if (~dropped).any() else 0.0
    pred = np.where(dropped, 1.0, dist[np.arange(n_cells), choice])
    choice_out = np.where(dropped, -1, choice)
    return AllocationResult(choice_out, dropped, total, float(capacity), pred,
                            time.perf_counter() - t0, f"greedy-{objective}", upgrades, notes)


def uniform_allocate(rates: np.ndarray, dist: np.ndarray, capacity: float) -> AllocationResult:
    """Same operating point for every cell: the lowest-mean-distortion one that fits."""
    t0 = time.perf_counter()
    rates = np.asarray(rates, dtype=float); dist = np.asarray(dist, dtype=float)
    _validate(rates, dist, capacity)
    n_cells = dist.shape[0]
    fits = np.where(n_cells * rates <= capacity + 1e-9)[0]
    notes: list[str] = []
    if fits.size == 0:
        # Overload: pick the cheapest point and drop least-useful cells until it fits.
        j = int(np.argmin(rates))
        choice = np.full(n_cells, j)
        dropped = np.zeros(n_cells, dtype=bool)
        used = n_cells * rates[j]
        for c in np.argsort(-dist[:, j], kind="stable"):
            if used <= capacity:
                break
            dropped[c] = True
            used -= rates[j]
        notes.append(f"overload: dropped {int(dropped.sum())} of {n_cells} cells")
    else:
        j = int(fits[np.argmin(dist[:, fits].mean(axis=0))])
        choice = np.full(n_cells, j)
        dropped = np.zeros(n_cells, dtype=bool)
    total = float(rates[choice[~dropped]].sum()) if (~dropped).any() else 0.0
    pred = np.where(dropped, 1.0, dist[np.arange(n_cells), choice])
    return AllocationResult(np.where(dropped, -1, choice), dropped, total, float(capacity), pred,
                            time.perf_counter() - t0, "uniform", 0, notes)
