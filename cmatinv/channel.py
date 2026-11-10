"""Standards-based massive-MIMO downlink channel generator.

* Large-scale fading : 3GPP TR 38.901 UMa NLOS path loss + log-normal shadowing
  (the same UMa model ITU-R M.2412 uses for IMT-2020 evaluation), users dropped
  uniformly in an annulus -> realistic near-far spread of user gains.
* Small-scale fading : 3GPP TR 38.901 TDL-A power-delay profile (23 taps), so the
  channel is frequency selective across the PRBs of a 100 MHz carrier.
* Spatial correlation: per-user ULA correlation from a Gaussian angular power
  spectrum (azimuth spread ~ TR 38.901 UMa), giving user-dependent R_k.
* Temporal evolution : Gauss-Markov / AR(1) with rho = J0(2 pi f_D T_slot)
  (Clarke/Jakes), the standard channel-aging model.
* Optional Rician LoS component (K-factor in dB).

Shapes: H is [S, K, M] = (subcarriers, users, BS antennas).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.special import j0

C = 299_792_458.0

TDL_A_DELAY = np.array([0.0000, 0.3819, 0.4025, 0.5868, 0.4610, 0.5375, 0.6708, 0.5750, 0.7618, 1.5375,
                        1.8978, 2.2242, 2.1718, 2.4942, 2.5119, 3.0582, 4.0810, 4.4579, 4.5695, 4.7966,
                        5.0066, 5.3043, 9.6586])
TDL_A_POWER_DB = np.array([-13.4, 0.0, -2.2, -4.0, -6.0, -8.1, -9.9, -10.5, -7.5, -15.9, -6.6, -16.7,
                           -12.4, -15.2, -10.8, -11.3, -12.7, -16.2, -18.3, -18.9, -16.6, -19.9, -29.7])


@dataclass
class ChannelConfig:
    M: int = 64                  # BS antennas
    K: int = 16                  # co-scheduled single-antenna layers
    S: int = 24                  # simulated subcarriers (spread over the carrier)
    bandwidth_hz: float = 100e6
    fc_hz: float = 3.5e9
    delay_spread_s: float = 300e-9
    speed_kmh: float = 30.0
    slot_s: float = 0.5e-3       # 30 kHz SCS
    min_dist_m: float = 100.0
    max_dist_m: float = 500.0
    shadow_db: float = 6.0
    angular_spread_deg: float = 12.0   # per-user azimuth spread (0 -> i.i.d. spatially white)
    rician_k_db: float | None = None
    h_bs: float = 25.0
    h_ut: float = 1.5
    seed: int = 0


def uma_nlos_pathloss_db(d2d, cfg: ChannelConfig):
    d3d = np.sqrt(d2d**2 + (cfg.h_bs - cfg.h_ut) ** 2)
    return 13.54 + 39.08 * np.log10(d3d) + 20 * np.log10(cfg.fc_hz / 1e9) - 0.6 * (cfg.h_ut - 1.5)


def doppler_rho(cfg: ChannelConfig) -> float:
    fd = cfg.speed_kmh / 3.6 * cfg.fc_hz / C
    return float(j0(2 * np.pi * fd * cfg.slot_s))


class MassiveMIMOChannel:
    def __init__(self, cfg: ChannelConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        K, M, S = cfg.K, cfg.M, cfg.S
        d = np.sqrt(self.rng.uniform(cfg.min_dist_m**2, cfg.max_dist_m**2, K))
        pl = uma_nlos_pathloss_db(d, cfg) + cfg.shadow_db * self.rng.standard_normal(K)
        edge_pl = uma_nlos_pathloss_db(cfg.max_dist_m, cfg)
        self.beta = 10 ** (-(pl - edge_pl) / 10)           # relative to an edge user (0 dB)
        self.theta = self.rng.uniform(-np.pi / 3, np.pi / 3, K)
        self.rsqrt = self._corr_sqrt()
        p = 10 ** (TDL_A_POWER_DB / 10)
        self.tap_p = p / p.sum()
        tau = TDL_A_DELAY * cfg.delay_spread_s
        f = (np.arange(S) / S - 0.5) * cfg.bandwidth_hz
        self.phase = np.exp(-2j * np.pi * f[:, None] * tau[None, :])      # [S, L]
        L = len(tau)
        self.g = self._cn((L, K, M))
        self.los = None
        if cfg.rician_k_db is not None:
            m = np.arange(M)
            self.los = np.exp(1j * np.pi * m[None, :] * np.sin(self.theta)[:, None]) \
                * np.exp(2j * np.pi * self.rng.uniform(size=(K, 1)))
        self.rho = doppler_rho(cfg)

    def _cn(self, shape):
        return (self.rng.standard_normal(shape) + 1j * self.rng.standard_normal(shape)) / np.sqrt(2)

    def _corr_sqrt(self):
        cfg = self.cfg
        K, M = cfg.K, cfg.M
        if cfg.angular_spread_deg <= 0:
            return None
        sd = np.deg2rad(cfg.angular_spread_deg)
        off = np.linspace(-2.5 * sd, 2.5 * sd, 41)
        w = np.exp(-0.5 * (off / sd) ** 2)
        w /= w.sum()
        m = np.arange(M)
        out = np.empty((K, M, M), complex)
        for k in range(K):
            ang = self.theta[k] + off
            a = np.exp(1j * np.pi * m[:, None] * np.sin(ang)[None, :])    # [M, 41]
            R = (a * w) @ a.conj().T
            ev, U = np.linalg.eigh(R)
            out[k] = (U * np.sqrt(np.clip(ev, 0, None))) @ U.conj().T
        return out

    def step(self):
        """Advance one slot (AR(1)) and return H [S, K, M]."""
        r = self.rho
        self.g = r * self.g + np.sqrt(1 - r * r) * self._cn(self.g.shape)
        return self.current()

    def current(self):
        cfg = self.cfg
        gt = np.einsum("l,sl,lkm->skm", np.sqrt(self.tap_p), self.phase, self.g)   # unit-power per entry
        if self.rsqrt is not None:
            gt = np.einsum("kmn,skn->skm", self.rsqrt, gt)
        if self.los is not None:
            kf = 10 ** (cfg.rician_k_db / 10)
            gt = np.sqrt(1 / (kf + 1)) * gt + np.sqrt(kf / (kf + 1)) * self.los[None]
        return np.sqrt(self.beta)[None, :, None] * gt

    def sequence(self, T: int):
        yield self.current()
        for _ in range(T - 1):
            yield self.step()
