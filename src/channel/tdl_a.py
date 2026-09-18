"""3GPP TR 38.901 TDL-A tapped-delay-line channel and uplink received signal.

Model
-----
For an RU with ``M`` antennas and ``N`` OFDM subcarriers the frequency-domain
channel of one OFDM symbol is

    H[m, n] = sum_l  a_l[m] * exp(-j 2 pi f_n tau_l),     f_n = n * SCS

where ``tau_l`` and the tap powers ``P_l`` come from TR 38.901 Table 7.7.2-1
(TDL-A, 23 Rayleigh taps, delays scaled by the desired RMS delay spread) and
``a_l ~ CN(0, P_l R)`` carries an exponential spatial correlation
``R[i, j] = rho^|i-j|`` across antennas.  Because ``H`` is a sum of 23 rank-one
terms its rank is at most 23; this is the delay-domain / low-rank structure the
CSEE and RAS-BFP encoders exploit.

The received matrix is ``Y = H * X + W`` (element-wise, single-layer uplink,
unit-modulus QPSK pilots ``X``), with ``W ~ CN(0, sigma^2)`` and
``sigma^2 = 10^(-SNR_dB / 10)`` because ``sum_l P_l = 1`` normalises
``E|H|^2 = 1``.

Units: delays in seconds, subcarrier spacing in Hz, powers linear.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# TR 38.901 Table 7.7.2-1 (TDL-A): normalised delay, power [dB]. All taps NLOS/Rayleigh.
_TDL_A_TABLE = np.array(
    [
        [0.0000, -13.4], [0.3819, 0.0], [0.4025, -2.2], [0.5868, -4.0],
        [0.4610, -6.0], [0.5375, -8.2], [0.6708, -9.9], [0.5750, -10.5],
        [0.7618, -7.5], [1.5375, -15.9], [1.8978, -6.6], [2.2242, -16.7],
        [2.1718, -12.4], [2.4942, -15.2], [2.5119, -10.8], [3.0582, -11.3],
        [4.0810, -12.7], [4.4579, -16.2], [4.5695, -18.3], [4.7966, -18.9],
        [5.0066, -16.6], [5.3043, -19.9], [9.6586, -29.7],
    ]
)


@dataclass
class ChannelConfig:
    M: int = 64                 # RU antennas
    N: int = 1200               # subcarriers (1200 x 15 kHz = 18 MHz occupied, 20 MHz carrier)
    SNR_dB: float = 20.0        # per-element SNR of Y
    seed: int = 42
    rho: float = 0.7            # exponential spatial correlation coefficient
    delay_spread_ns: float = 100.0   # TR 38.901 "nominal" scaling (Table 7.7.3-1)
    scs_hz: float = 15e3

    def __post_init__(self) -> None:
        if self.M < 1 or self.N < 1:
            raise ValueError("M and N must be positive")
        if not 0.0 <= self.rho < 1.0:
            raise ValueError("rho must lie in [0, 1)")
        if self.delay_spread_ns <= 0 or self.scs_hz <= 0:
            raise ValueError("delay_spread_ns and scs_hz must be positive")


class TDLAChannel:
    """Generates TDL-A channel matrices and noisy received matrices."""

    def __init__(self, cfg: ChannelConfig):
        self.cfg = cfg
        self.delays_s = _TDL_A_TABLE[:, 0] * cfg.delay_spread_ns * 1e-9
        powers = 10.0 ** (_TDL_A_TABLE[:, 1] / 10.0)
        self.powers = powers / powers.sum()
        self.num_taps = len(self.powers)
        # Spatial correlation square root (Hermitian, so Cholesky works; R is SPD for rho<1).
        idx = np.arange(cfg.M)
        R = cfg.rho ** np.abs(idx[:, None] - idx[None, :])
        self._R_sqrt = np.linalg.cholesky(R)
        freqs = np.arange(cfg.N) * cfg.scs_hz
        # (taps, N) steering matrix in frequency
        self._E = np.exp(-2j * np.pi * np.outer(self.delays_s, freqs))

    # -- generation -------------------------------------------------------
    def _rng(self, seed_offset: int) -> np.random.Generator:
        return np.random.default_rng(self.cfg.seed + seed_offset)

    def generate_H(self, seed_offset: int = 0) -> np.ndarray:
        """One channel realisation, shape (M, N), E|H|^2 = 1."""
        rng = self._rng(seed_offset)
        M = self.cfg.M
        g = (rng.standard_normal((M, self.num_taps)) + 1j * rng.standard_normal((M, self.num_taps))) / np.sqrt(2)
        a = (self._R_sqrt @ g) * np.sqrt(self.powers)[None, :]        # (M, taps)
        return a @ self._E                                             # (M, N)

    def generate_pilots(self, seed_offset: int = 0) -> np.ndarray:
        rng = self._rng(10_000 + seed_offset)
        return np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, size=self.cfg.N)))

    def generate_received_signal(
        self, H: np.ndarray, seed_offset: int = 0, pilots: bool = True, return_clean: bool = False,
        symbol_type: str = "data",
    ):
        """Y = H * X + W.  With ``return_clean`` also returns the noiseless S = H * X.

        ``symbol_type``:
          * ``"data"``      -- random QPSK on every subcarrier (what a data-bearing
                               OFDM symbol looks like on the fronthaul; default).
          * ``"reference"`` -- a known sequence that the RU de-rotates, so the
                               transported matrix is ``H + W'`` (DMRS/SRS symbols,
                               i.e. what a channel-estimate compressor sees).
        ``pilots=False`` keeps the legacy all-ones sequence (equivalent to
        ``"reference"``).
        """
        if symbol_type not in ("data", "reference"):
            raise ValueError("symbol_type must be 'data' or 'reference'")
        rng = self._rng(20_000 + seed_offset)
        X = self.generate_pilots(seed_offset) if pilots else np.ones(self.cfg.N, dtype=complex)
        S = H * X[None, :]
        sigma2 = 10.0 ** (-self.cfg.SNR_dB / 10.0)
        W = np.sqrt(sigma2 / 2) * (rng.standard_normal(S.shape) + 1j * rng.standard_normal(S.shape))
        Y = S + W
        if symbol_type == "reference":
            # De-rotation by the known unit-modulus sequence: noise stays white with the same variance.
            Y = Y * np.conj(X)[None, :]
            S = H
        return (Y, S) if return_clean else Y

    def generate_batch(self, num_realizations: int, return_clean: bool = False, symbol_type: str = "data"):
        """Returns (H_batch, Y_batch[, S_batch]) with shape (num, M, N)."""
        Hs, Ys, Ss = [], [], []
        for i in range(num_realizations):
            H = self.generate_H(seed_offset=i)
            Y, S = self.generate_received_signal(H, seed_offset=i, return_clean=True, symbol_type=symbol_type)
            Hs.append(H); Ys.append(Y); Ss.append(S)
        out = (np.stack(Hs), np.stack(Ys))
        return out + (np.stack(Ss),) if return_clean else out

    # -- derived quantities ------------------------------------------------
    def noise_variance(self) -> float:
        return float(10.0 ** (-self.cfg.SNR_dB / 10.0))

    def raw_fronthaul_bits_per_symbol(self, bits_per_component: int = 16) -> int:
        """Uncompressed antenna-space I/Q bits for one OFDM symbol: 2 * M * N * b."""
        return 2 * self.cfg.M * self.cfg.N * bits_per_component


# -- rank estimation ----------------------------------------------------------
def estimate_rank(Y: np.ndarray, energy_threshold: float = 0.99) -> int:
    """Numerical rank: smallest r with sum_{i<=r} sigma_i^2 >= threshold * ||Y||_F^2.

    Uses the eigenvalues of the M x M Gram matrix Y Y^H (O(M^2 N)), which is
    exact and cheaper than a full SVD when M << N.
    """
    if not 0.0 < energy_threshold <= 1.0:
        raise ValueError("energy_threshold must lie in (0, 1]")
    total = np.linalg.norm(Y, "fro") ** 2
    if total == 0.0:
        return 0
    G = Y @ Y.conj().T
    eig = np.sort(np.linalg.eigvalsh(G))[::-1]
    eig = np.clip(eig, 0.0, None)
    cum = np.cumsum(eig) / eig.sum()
    return int(np.searchsorted(cum, energy_threshold) + 1)


def estimate_rank_fast(
    Y: np.ndarray, energy_threshold: float = 0.99, subsample: int = 8, seed: int = 0
) -> int:
    """Cheap rank estimate from a random subset of N/``subsample`` subcarriers.

    The spatial (antenna) covariance of a TDL channel is shared across
    subcarriers, so the eigen-spectrum of the Gram matrix built from a column
    subset is an unbiased estimate of the full one, at 1/``subsample`` of the
    O(M^2 N) cost.  Variance grows as the subset shrinks; Experiment 3 compares
    it against :func:`estimate_rank` (the earlier repository figure used a fake
    "fast" curve made by perturbing the exact rank, which is replaced by this).
    """
    if subsample < 1:
        raise ValueError("subsample must be >= 1")
    M, N = Y.shape
    if np.linalg.norm(Y, "fro") == 0.0:
        return 0
    rng = np.random.default_rng(seed)
    cols = rng.choice(N, size=max(M, N // subsample), replace=False) if N // subsample < N else np.arange(N)
    return estimate_rank(Y[:, np.sort(cols)], energy_threshold)
