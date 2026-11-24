"""Uplink frequency-domain IQ at the O-RU for one slot: Y_p = H_p X_p + N per PRB.

Shapes: Y [P, M, n] with n = 12 subcarriers x 14 symbols per PRB, H [P, 12, M, K], X [P, K, n].
The channel comes from cmatinv.channel (3GPP TR 38.901 UMa + TDL-A + spatial correlation) evaluated on
contiguous 30 kHz subcarriers, so the per-PRB channel variation is physical.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cmatinv.channel import ChannelConfig, MassiveMIMOChannel

SC, SYM = 12, 14
SCS_HZ = 30e3


def qam_constellation(order):
    m = int(np.sqrt(order))
    lv = np.arange(-(m - 1), m, 2, dtype=float)
    c = (lv[:, None] + 1j * lv[None, :]).ravel()
    return c / np.sqrt(np.mean(np.abs(c) ** 2))


@dataclass
class UplinkConfig:
    M: int = 64
    K: int = 8
    n_prb: int = 24
    snr_db: float = 25.0                 # per-user received SNR per antenna after power control
    qam: int = 256
    angular_spread_deg: float = 12.0
    rician_k_db: float | None = None
    power_control: bool = True           # full path-loss compensation (equal received power)
    seed: int = 0


def _channel(cfg: UplinkConfig, speed_kmh=30.0):
    S = cfg.n_prb * SC
    return MassiveMIMOChannel(ChannelConfig(M=cfg.M, K=cfg.K, S=S, bandwidth_hz=S * SCS_HZ, seed=cfg.seed,
                                            angular_spread_deg=cfg.angular_spread_deg,
                                            rician_k_db=cfg.rician_k_db, speed_kmh=speed_kmh))


def make_slot(cfg: UplinkConfig, ch=None, rng=None):
    """Return dict with Y [P,M,n], H [P,12,M,K], X [P,K,n], noise_var."""
    ch = ch or _channel(cfg)
    Hd = ch.current()                                            # [S, K, M] downlink orientation
    if cfg.power_control:
        Hd = Hd / np.sqrt(ch.beta)[None, :, None]
    H = np.swapaxes(Hd, -1, -2).reshape(cfg.n_prb, SC, cfg.M, cfg.K)
    rng = rng or np.random.default_rng(cfg.seed + 10_000)
    const = qam_constellation(cfg.qam)
    X = const[rng.integers(0, len(const), (cfg.n_prb, cfg.K, SC, SYM))]
    p = 10 ** (cfg.snr_db / 10)
    # y[p, :, sc, sym] = H[p, sc] @ x[p, :, sc, sym]
    Y = np.sqrt(p) * np.einsum("psmk,pkst->pmst", H, X)
    N = (rng.standard_normal(Y.shape) + 1j * rng.standard_normal(Y.shape)) / np.sqrt(2)
    Y = Y + N
    n = SC * SYM
    return dict(Y=Y.reshape(cfg.n_prb, cfg.M, n), H=H, X=X.reshape(cfg.n_prb, cfg.K, n),
                power=p, noise_var=1.0, cfg=cfg)


def slot_sequence(cfg: UplinkConfig, T, speed_kmh):
    """T consecutive slots on one AR(1)-aged (Clarke/Jakes) channel."""
    ch = _channel(cfg, speed_kmh)
    rng = np.random.default_rng(cfg.seed + 10_000)
    for t in range(T):
        if t:
            ch.step()
        yield make_slot(cfg, ch, rng)


def mmse_detect(Y, H, power, noise_var=1.0):
    """Per-subcarrier unbiased MMSE detection. Y [P,M,n] -> Xhat [P,K,n]."""
    P, M, n = Y.shape
    K = H.shape[-1]
    Ys = Y.reshape(P, M, SC, SYM)
    Hs = np.sqrt(power) * H                                     # [P, SC, M, K]
    Hh = np.conj(np.swapaxes(Hs, -1, -2))
    A = Hh @ Hs + noise_var * np.eye(K)
    F = np.linalg.solve(A, Hh)                                  # [P, SC, K, M]
    bias = np.real(np.diagonal(F @ Hs, axis1=-2, axis2=-1))     # [P, SC, K]
    Xh = np.einsum("pskm,pmst->pkst", F, Ys) / np.transpose(bias, (0, 2, 1))[..., None]
    return Xh.reshape(P, K, n)


def evm(Xh, X):
    """RMS EVM over all users and REs (fraction, not %)."""
    return float(np.sqrt(np.mean(np.abs(Xh - X) ** 2) / np.mean(np.abs(X) ** 2)))


def post_detection_quality(Yhat, slot, combined=False):
    """Post-MMSE-detection EVM / SINR. combined=True: Yhat already holds per-user MMSE outputs [P,K,n]."""
    if combined:
        P, K, n = Yhat.shape
        Hs = np.sqrt(slot["power"]) * slot["H"]
        Hh = np.conj(np.swapaxes(Hs, -1, -2))
        F = np.linalg.solve(Hh @ Hs + slot["noise_var"] * np.eye(K), Hh)
        bias = np.real(np.diagonal(F @ Hs, axis1=-2, axis2=-1))              # [P, SC, K]
        Xh = (Yhat.reshape(P, K, SC, SYM) / np.transpose(bias, (0, 2, 1))[..., None]).reshape(P, K, n)
    else:
        Xh = mmse_detect(Yhat, slot["H"], slot["power"], slot["noise_var"])
    e = evm(Xh, slot["X"])
    return dict(evm=e, sinr_db=float(-20 * np.log10(e)))
