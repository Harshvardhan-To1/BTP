"""Model-based (Markov) probabilistic forecasters of the deadline-feasible rate.

These forecasters expose the same interface as ``forecast.QuantileGBMForecaster`` (``predict_quantiles(obs)
-> [N, K] bits/slot``, ``quantiles``, ``median_index``) so that they can drive the same KKT allocator. Instead
of learning a regression from training traces they fit (or are given) a Markov-modulated model of each
cell's fronthaul demand and obtain the predictive distribution of r* by Monte Carlo over the fitted chain.

  * MarkovChainForecaster   - fitted online from the cell's recent history only (no training data):
                              the demand is quantised into K phases by empirical thresholds, the phase
                              transition matrix is estimated from transition counts with a Dirichlet prior,
                              the per-phase mean and coefficient of variation from moments; the horizon is
                              simulated from the last observed phase.
  * MarkovOracleForecaster  - knows the true generator of Family M (traffic_markov.MarkovSource) and runs
                              the HMM forward filter over the recent history to obtain the posterior of the
                              current (hidden) phase, then simulates the horizon. This is the Bayes predictive
                              distribution of r* up to Monte Carlo error: the best any forecaster can do with
                              the same information on that family.
  * ChernoffBoundForecaster - replaces the Monte Carlo quantiles of the fitted chain by the conservative
                              quantiles obtained from the Chernoff-union tail bound (theory.py). Every
                              reported quantile is a guaranteed upper bound on the true quantile under the
                              fitted model, which makes the allocation provably safe and, as the experiments
                              show, far too conservative at millisecond deadlines.

All three use the same per-slot Gamma increment model, so the three differ only in where the phase model
comes from (fitted / true) and in how the distribution of r* is computed (Monte Carlo / bound).
"""
from __future__ import annotations

from typing import List, Optional, Sequence
import numpy as np

from .demand import required_rates
from .forecast import DEFAULT_QUANTILES
from .simulator import Observation
from .theory import bound_quantiles
from .traffic_markov import MarkovSource, stationary_distribution


# ---------------------------------------------------------------------------
# fitting a K-phase chain to one history
# ---------------------------------------------------------------------------
def fit_phase_chain(hist: np.ndarray, K: int = 3, prior: float = 0.5, thresholds: Sequence[float] = (0.45, 0.85)):
    """Quantise `hist` (one cell, [W]) into K phases and estimate (P, mean, cv, last_phase).

    Phase boundaries are the empirical quantiles of the window at `thresholds` (K-1 values); phases with no
    sample inherit the window mean and a cv of 0.5. Transition probabilities use a symmetric Dirichlet
    prior of strength `prior`.
    """
    h = np.asarray(hist, dtype=float)
    W = len(h)
    if W < 10:
        m = float(h.mean()) if W else 0.0
        return np.full((K, K), 1.0 / K), np.full(K, m), np.full(K, 0.5), 0
    cuts = np.quantile(h, list(thresholds)[:K - 1])
    phase = np.searchsorted(cuts, h, side="right")              # 0..K-1
    counts = np.full((K, K), prior)
    np.add.at(counts, (phase[:-1], phase[1:]), 1.0)
    P = counts / counts.sum(1, keepdims=True)
    mean = np.empty(K)
    cv = np.empty(K)
    gmean = float(h.mean())
    for k in range(K):
        sel = h[phase == k]
        if len(sel) >= 2 and sel.mean() > 0:
            mean[k] = sel.mean()
            cv[k] = float(np.clip(sel.std(ddof=1) / sel.mean(), 0.05, 2.0))
        else:
            mean[k] = sel.mean() if len(sel) else gmean
            cv[k] = 0.5
    return P, mean, cv, int(phase[-1])


def simulate_rstar_quantiles(P: np.ndarray, mean: np.ndarray, cv: np.ndarray, p0: np.ndarray, H: int,
                             deadline: float, levels: np.ndarray, n_paths: int, rng: np.random.Generator) -> np.ndarray:
    """Monte Carlo quantiles of r* over an H-slot horizon for ONE cell: phases from p0, Gamma increments."""
    K = len(mean)
    cum = np.cumsum(P, axis=1)
    state = rng.choice(K, size=n_paths, p=p0 / p0.sum())
    incr = np.empty((n_paths, H))
    shape = 1.0 / np.maximum(cv, 1e-6) ** 2
    scale = np.maximum(mean, 0.0) / shape
    for t in range(H):
        incr[:, t] = rng.gamma(shape[state], scale[state])
        u = rng.random(n_paths)
        state = np.minimum((u[:, None] > cum[state]).sum(1), K - 1)
    rs = required_rates(incr, np.full(n_paths, deadline))
    return np.quantile(rs, levels)


class _MarkovBase:
    def __init__(self, quantiles=DEFAULT_QUANTILES, n_paths: int = 200, seed: int = 0):
        self.quantiles = tuple(quantiles)
        self.n_paths = n_paths
        self.rng = np.random.default_rng(seed)
        self.last_fit: List[tuple] = []

    @property
    def median_index(self) -> int:
        return int(np.argmin(np.abs(np.array(self.quantiles) - 0.5)))


class MarkovChainForecaster(_MarkovBase):
    """K-phase Markov chain fitted to the last `window` slots of each cell (no training data)."""

    def __init__(self, quantiles=DEFAULT_QUANTILES, K: int = 3, window: int = 2000, n_paths: int = 200,
                 prior: float = 0.5, seed: int = 0):
        super().__init__(quantiles, n_paths, seed)
        self.K = K
        self.window = window
        self.prior = prior

    def predict_quantiles(self, obs: Observation) -> np.ndarray:
        H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
        hist = obs.history_fh_demand
        n, L = hist.shape
        levels = np.asarray(self.quantiles)
        out = np.zeros((n, len(levels)))
        self.last_fit = []
        for i in range(n):
            h = hist[i, max(0, L - self.window):]
            P, mean, cv, last = fit_phase_chain(h, self.K, self.prior)
            self.last_fit.append((P, mean, cv, last))
            if L == 0 or mean.max() <= 0:
                continue
            p0 = np.zeros(self.K)
            p0[last] = 1.0
            out[i] = simulate_rstar_quantiles(P, mean, cv, p0, H, obs.deadlines[i], levels, self.n_paths, self.rng)
        return out


class MarkovOracleForecaster(_MarkovBase):
    """True Family-M generator + HMM forward filter for the hidden phase (reference, Family M only)."""

    def __init__(self, sources: Sequence[MarkovSource], net, quantiles=DEFAULT_QUANTILES, n_paths: int = 200,
                 filter_window: int = 300, seed: int = 0):
        super().__init__(quantiles, n_paths, seed)
        self.sources = list(sources)
        beta = net.fh_bits_per_prb_layer
        # fronthaul-unit means: user bits / eta * beta (constant eta in Family M)
        self.fh_scale = np.array([beta / c.se_bits_per_prb_layer for c in net.cells])
        self.filter_window = filter_window

    def _posterior(self, hist: np.ndarray, src: MarkovSource, scale: float) -> np.ndarray:
        """Forward filter P(X_L | d_1..d_L) with Gamma emissions (log domain)."""
        from scipy.special import gammaln
        h = hist[-self.filter_window:]
        if len(h) == 0:
            return src.stationary()
        shape = 1.0 / src.cv ** 2
        gscale = src.mu * scale / shape                                  # fronthaul units
        x = np.maximum(h, 1e-9)[:, None]
        logf = (shape - 1) * np.log(x) - x / gscale - shape * np.log(gscale) - gammaln(shape)   # [W, K]
        alpha = np.log(src.stationary()) + logf[0]
        for t in range(1, len(h)):
            m = alpha.max()
            pred = np.exp(alpha - m) @ src.P                                # [K], prediction step
            alpha = m + np.log(np.maximum(pred, 1e-300)) + logf[t]          # update step
        p = np.exp(alpha - alpha.max())
        return p / p.sum()

    def predict_quantiles(self, obs: Observation) -> np.ndarray:
        H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
        hist = obs.history_fh_demand
        n = hist.shape[0]
        levels = np.asarray(self.quantiles)
        out = np.zeros((n, len(levels)))
        for i in range(n):
            src = self.sources[i]
            p0 = self._posterior(hist[i], src, self.fh_scale[i])
            # the horizon starts at obs_slot: advance the posterior by one step (the chain moves before the
            # first unseen slot) and simulate
            p0 = p0 @ src.P
            out[i] = simulate_rstar_quantiles(src.P, src.mu * self.fh_scale[i], src.cv, p0, H, obs.deadlines[i],
                                              levels, self.n_paths, self.rng)
        return out


class ChernoffBoundForecaster(MarkovChainForecaster):
    """Conservative quantiles from the Chernoff-union bound of the fitted chain (theory.py)."""

    def predict_quantiles(self, obs: Observation) -> np.ndarray:
        H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
        hist = obs.history_fh_demand
        n, L = hist.shape
        levels = np.asarray(self.quantiles)
        out = np.zeros((n, len(levels)))
        caps = obs.budget_caps
        self.last_fit = []
        for i in range(n):
            h = hist[i, max(0, L - self.window):]
            P, mean, cv, last = fit_phase_chain(h, self.K, self.prior)
            self.last_fit.append((P, mean, cv, last))
            if L == 0 or mean.max() <= 0:
                continue
            pi = stationary_distribution(P)
            out[i] = bound_quantiles(levels, P, mean, cv, pi, int(obs.deadlines[i]), H, x_max=float(caps[i]))
        return out
