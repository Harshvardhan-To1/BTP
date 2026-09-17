"""Synthetic downlink traffic generator (exogenous to the controller).

The traffic is SYNTHETIC. It is designed to reproduce qualitative features
that matter for fronthaul budget allocation rather than to match a measured
trace:

  * many-small-flows background  -> Gamma-distributed per-slot volume
  * bursty large flows           -> ON/OFF component with heavy-tailed sojourns
  * slow non-stationarity        -> piecewise-constant regime multipliers
                                    (optionally including flash crowds)
  * per-cell spectral efficiency -> user bits per PRB-layer, drifting slowly

The fronthaul demand of a cell is NOT its user traffic: a user bit costs
fh_bits_per_prb_layer / se_i fronthaul bits, so low-SE cells load the
fronthaul more per delivered bit (split 7-2x carries IQ per scheduled PRB).
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .config import NetworkConfig, TrafficConfig


@dataclass
class TrafficTrace:
    arrivals_bits: np.ndarray     # [N, S] user-plane bits arriving at the DU per slot
    se: np.ndarray                # [N, S] spectral efficiency (user bits per PRB-layer per slot)
    fh_demand_bits: np.ndarray    # [N, S] fronthaul bits needed to carry the arrivals immediately
    regime_mult: np.ndarray       # [N, S] regime multiplier (diagnostics only)
    mean_fh_load: float           # realised mean fronthaul demand / usable capacity

    @property
    def num_cells(self) -> int:
        return self.arrivals_bits.shape[0]

    @property
    def num_slots(self) -> int:
        return self.arrivals_bits.shape[1]


def _piecewise_regimes(rng: np.random.Generator, num_slots: int, mean_len: float,
                       log_sigma: float, flash_prob: float, flash_mult: float) -> np.ndarray:
    """Piecewise-constant multiplier with exponential regime durations, mean 1."""
    out = np.empty(num_slots)
    t = 0
    # log-normal with E[m]=1
    while t < num_slots:
        length = max(1, int(rng.exponential(mean_len)))
        if flash_prob > 0 and rng.random() < flash_prob:
            m = flash_mult
        else:
            m = float(np.exp(rng.normal(-0.5 * log_sigma ** 2, log_sigma)))
        out[t:t + length] = m
        t += length
    return out


def _pareto_duration(rng: np.random.Generator, mean: float, alpha: float, cap_factor: float = 50.0) -> int:
    """Heavy-tailed sojourn time (slots) with the given mean; Pareto shape alpha > 1."""
    xm = mean * (alpha - 1.0) / alpha
    d = xm * rng.random() ** (-1.0 / alpha)
    return int(np.clip(np.ceil(d), 1, cap_factor * mean))


def _on_off_process(rng: np.random.Generator, num_slots: int, on_mean: float, off_mean: float,
                    alpha_on: float = 1.5, alpha_off: float = 1.8) -> np.ndarray:
    """ON/OFF source with heavy-tailed (Pareto) sojourn times; returns 0/1 array.

    Heavy-tailed ON/OFF periods are the classical generative explanation of
    self-similar / long-range-dependent network traffic (Willinger et al.,
    IEEE/ACM ToN 1997). They also mean that the recent past carries
    information about the near future (a long-running burst tends to
    continue), which is what any forecaster has to exploit.
    """
    state = np.empty(num_slots, dtype=np.int8)
    s = 1 if rng.random() < on_mean / (on_mean + off_mean) else 0
    t = 0
    while t < num_slots:
        d = _pareto_duration(rng, on_mean if s else off_mean, alpha_on if s else alpha_off)
        state[t:t + d] = s
        t += d
        s = 1 - s
    return state


def _gamma_with_cv(rng: np.random.Generator, mean: np.ndarray, cv: float) -> np.ndarray:
    """Gamma samples with given per-element mean and constant coefficient of variation."""
    mean = np.asarray(mean, dtype=float)
    out = np.zeros_like(mean)
    pos = mean > 0
    if cv <= 0:
        out[pos] = mean[pos]
        return out
    k = 1.0 / cv ** 2
    out[pos] = rng.gamma(shape=k, scale=mean[pos] / k)
    return out


def generate_traffic(net: NetworkConfig, tcfg: TrafficConfig, num_slots: int, seed: int) -> TrafficTrace:
    rng = np.random.default_rng(seed)
    n = net.num_cells
    beta = net.fh_bits_per_prb_layer
    cap = net.usable_bits_per_slot

    if tcfg.load_share:
        shares = np.array(tcfg.load_share, dtype=float)
    else:  # low-latency cells carry less volume than eMBB cells by default
        shares = np.array([0.6 if c.deadline_slots <= 10 else 1.0 for c in net.cells])
    shares = shares / shares.sum()
    target_fh_mean = tcfg.load * cap * shares          # mean fronthaul bits/slot per cell

    arrivals = np.zeros((n, num_slots))
    se = np.zeros((n, num_slots))
    regimes = np.zeros((n, num_slots))

    for i, cell in enumerate(net.cells):
        # --- slow processes -------------------------------------------------
        m = _piecewise_regimes(rng, num_slots, tcfg.regime_mean_slots, tcfg.regime_log_sigma,
                               tcfg.flash_crowd_prob, tcfg.flash_crowd_mult)
        regimes[i] = m
        # spectral efficiency drifts per regime (random walk in log domain, clipped)
        se_i = np.empty(num_slots)
        eta = cell.se_bits_per_prb_layer
        cur = eta
        t = 0
        while t < num_slots:
            length = max(1, int(rng.exponential(tcfg.regime_mean_slots)))
            cur = float(np.clip(cur * np.exp(rng.normal(0, tcfg.se_drift_sigma)), 0.5 * eta, 1.5 * eta))
            se_i[t:t + length] = cur
            t += length
        se[i] = se_i

        # mean user bits per slot that produce the target fronthaul load at nominal SE
        mu_user = target_fh_mean[i] * eta / beta

        # --- smooth component ------------------------------------------------
        smooth_mean = (1.0 - cell.burst_fraction) * mu_user * m
        smooth = _gamma_with_cv(rng, smooth_mean, cell.smooth_cv)

        # --- bursty ON/OFF component (mean preserved under scaling) ----------
        on_mean = cell.on_mean_slots * tcfg.on_duration_scale
        off_mean = cell.off_mean_slots * tcfg.on_duration_scale
        # burst_rate_scale s: ON intensity x s, duty cycle / s  -> same mean, higher peaks
        s = tcfg.burst_rate_scale
        duty = on_mean / (on_mean + off_mean)
        duty_scaled = min(0.95, duty / s)
        off_mean_scaled = on_mean * (1.0 - duty_scaled) / duty_scaled
        state = _on_off_process(rng, num_slots, on_mean, off_mean_scaled,
                                tcfg.pareto_alpha_on, tcfg.pareto_alpha_off)
        on_intensity = cell.burst_fraction * mu_user * m / duty_scaled
        burst = _gamma_with_cv(rng, on_intensity * state, 0.5)

        arrivals[i] = smooth + burst

    fh_demand = arrivals / se * beta
    return TrafficTrace(arrivals_bits=arrivals, se=se, fh_demand_bits=fh_demand,
                        regime_mult=regimes, mean_fh_load=float(fh_demand.sum(0).mean() / cap))
