"""Markov-modulated fluid (MMF) traffic family ("Family M").

Third traffic family, built so that the theory in ``theory.py`` applies
exactly: every cell's fronthaul demand is a discrete-time Markov-modulated
process with Gamma-distributed per-slot increments,

    X_t  ~ Markov chain on {0, ..., K-1} with transition matrix P      (hidden phase)
    a_t | X_t = k  ~ Gamma(shape = 1 / cv_k^2, mean = mu_k)             (user bits in slot t)
    d_t  = a_t / eta * beta                                              (fronthaul bits)

with a constant spectral efficiency eta per cell, so that d_t is itself a
Markov-modulated Gamma process whose moment generating function, effective
bandwidth and Chernoff tail bound are available in closed form.

The phases are "idle / normal / burst" with geometric (memoryless) sojourns;
this is the discrete-time analogue of the Anick-Mitra-Sondhi / Kesidis-
Walrand-Chang Markov fluid source. The ``mm_shift`` scenario replaces the
geometric sojourns by Pareto ones with the same means (semi-Markov), so the
Markov model used by the model-based forecasters is misspecified there and the
cost of that misspecification can be measured.

Everything is scaled so that the stationary mean fronthaul demand equals the
scenario's target load, exactly as in the other two families.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

from .config import NetworkConfig, TrafficConfig
from .traffic import TrafficTrace


@dataclass(frozen=True)
class MarkovSource:
    """Parameters of one Markov-modulated Gamma source (per cell).

    P[k, l] transition probability per slot, mu[k] mean user bits per slot in
    phase k, cv[k] coefficient of variation of the Gamma increment in phase k.
    """
    P: np.ndarray
    mu: np.ndarray
    cv: np.ndarray

    @property
    def num_states(self) -> int:
        return len(self.mu)

    def stationary(self) -> np.ndarray:
        return stationary_distribution(self.P)

    def mean_rate(self) -> float:
        return float(self.stationary() @ self.mu)


def stationary_distribution(P: np.ndarray) -> np.ndarray:
    """Stationary distribution of an irreducible stochastic matrix (left eigenvector)."""
    P = np.asarray(P, dtype=float)
    K = P.shape[0]
    A = np.vstack([P.T - np.eye(K), np.ones((1, K))])
    b = np.concatenate([np.zeros(K), [1.0]])
    pi, *_ = np.linalg.lstsq(A, b, rcond=None)
    pi = np.clip(pi, 0.0, None)
    return pi / pi.sum()


def phase_matrix(mean_sojourn: np.ndarray, next_prob: np.ndarray) -> np.ndarray:
    """Transition matrix with geometric sojourns of the given means and jump distribution rows."""
    K = len(mean_sojourn)
    P = np.zeros((K, K))
    for k in range(K):
        stay = 1.0 - 1.0 / float(mean_sojourn[k])
        P[k, k] = stay
        row = np.asarray(next_prob[k], dtype=float).copy()
        row[k] = 0.0
        row = row / row.sum()
        P[k] += (1.0 - stay) * row
    return P


# Phase structure per class: (mean sojourn in slots, relative rate) for idle / normal / burst.
LL_PHASES = dict(sojourn=np.array([40.0, 30.0, 8.0]), rel_rate=np.array([0.15, 1.0, 3.0]), cv=np.array([0.5, 0.4, 0.35]))
EMBB_PHASES = dict(sojourn=np.array([80.0, 60.0, 20.0]), rel_rate=np.array([0.3, 1.0, 1.8]), cv=np.array([0.4, 0.3, 0.3]))
# jumps: idle -> normal mostly, normal -> idle or burst, burst -> normal mostly
JUMPS = np.array([[0.0, 0.85, 0.15],
                  [0.5, 0.0, 0.5],
                  [0.15, 0.85, 0.0]])


def cell_source(cell, target_fh_mean: float, beta: float) -> MarkovSource:
    """Markov source of one cell whose stationary mean fronthaul demand equals target_fh_mean."""
    ph = LL_PHASES if cell.deadline_slots <= 10 else EMBB_PHASES
    P = phase_matrix(ph["sojourn"], JUMPS)
    pi = stationary_distribution(P)
    eta = cell.se_bits_per_prb_layer
    mu_user_target = target_fh_mean * eta / beta           # mean user bits/slot
    rel = ph["rel_rate"]
    mu = rel * (mu_user_target / float(pi @ rel))
    return MarkovSource(P=P, mu=mu, cv=ph["cv"].copy())


def _pareto_sojourn(rng: np.random.Generator, mean: float, alpha: float) -> int:
    xm = mean * (alpha - 1.0) / alpha
    return int(np.clip(np.ceil(xm * rng.random() ** (-1.0 / alpha)), 1, 50 * mean))


def simulate_phases(rng: np.random.Generator, src: MarkovSource, num_slots: int, x0: int | None = None,
                    tail_alpha: float | None = None) -> np.ndarray:
    """Phase path X_0..X_{S-1}; geometric sojourns (Markov) or Pareto sojourns (semi-Markov shift)."""
    K = src.num_states
    x = np.empty(num_slots, dtype=np.int8)
    state = int(rng.choice(K, p=src.stationary())) if x0 is None else int(x0)
    if tail_alpha is None:
        cum = np.cumsum(src.P, axis=1)
        u = rng.random(num_slots)
        for t in range(num_slots):
            x[t] = state
            state = int(np.searchsorted(cum[state], u[t]))
            state = min(state, K - 1)
        return x
    # semi-Markov: same embedded jump chain and same mean sojourns, heavy-tailed sojourn law
    mean_soj = 1.0 / np.clip(1.0 - np.diag(src.P), 1e-9, None)
    jump = src.P.copy()
    np.fill_diagonal(jump, 0.0)
    jump = jump / jump.sum(1, keepdims=True)
    t = 0
    while t < num_slots:
        d = _pareto_sojourn(rng, mean_soj[state], tail_alpha)
        x[t:t + d] = state
        t += d
        state = int(rng.choice(K, p=jump[state]))
    return x


def sample_increments(rng: np.random.Generator, src: MarkovSource, phases: np.ndarray) -> np.ndarray:
    """Gamma increments given the phase path."""
    mu = src.mu[phases]
    cv = src.cv[phases]
    shape = 1.0 / cv ** 2
    return rng.gamma(shape=shape, scale=mu / shape)


def build_sources(net: NetworkConfig, tcfg: TrafficConfig) -> List[MarkovSource]:
    beta = net.fh_bits_per_prb_layer
    cap = net.usable_bits_per_slot
    if tcfg.load_share:
        shares = np.array(tcfg.load_share, dtype=float)
    else:
        shares = np.array([0.6 if c.deadline_slots <= 10 else 1.0 for c in net.cells])
    shares = shares / shares.sum()
    target = tcfg.load * cap * shares
    return [cell_source(c, target[i], beta) for i, c in enumerate(net.cells)]


def generate_traffic_markov(net: NetworkConfig, tcfg: TrafficConfig, num_slots: int, seed: int) -> TrafficTrace:
    rng = np.random.default_rng(seed + 9_000_000)   # separate stream from the other families
    n = net.num_cells
    beta = net.fh_bits_per_prb_layer
    cap = net.usable_bits_per_slot
    sources = build_sources(net, tcfg)
    arrivals = np.zeros((n, num_slots))
    se = np.zeros((n, num_slots))
    regimes = np.zeros((n, num_slots))
    for i, cell in enumerate(net.cells):
        src = sources[i]
        x = simulate_phases(rng, src, num_slots, tail_alpha=tcfg.mm_tail_alpha)
        arrivals[i] = sample_increments(rng, src, x)
        se[i] = cell.se_bits_per_prb_layer
        regimes[i] = x
    fh = arrivals / se * beta
    return TrafficTrace(arrivals_bits=arrivals, se=se, fh_demand_bits=fh, regime_mult=regimes,
                        mean_fh_load=float(fh.sum(0).mean() / cap))
