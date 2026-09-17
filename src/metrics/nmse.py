"""Distortion and rate metrics used throughout the simulator.

Definitions
-----------
* ``nmse_linear(Y, Y_hat) = ||Y - Y_hat||_F^2 / ||Y||_F^2``   (dimensionless)
* ``nmse(Y, Y_hat) = 10 log10(nmse_linear)``                     (dB)
* ``original_bits(M, N, b) = 2 M N b``  -- uncompressed I/Q bits for one
  OFDM symbol with ``b`` bits per real component (default 16, the eCPRI /
  O-RAN uncompressed IQ width).
* ``compression_ratio = original_bits / bits_used``            (dimensionless)
* ``effective_snr_db(S, Y_hat)`` -- signal energy over *all* error energy
  (thermal noise + compression) when ``S`` is the noiseless received signal.

Which reference matters
-----------------------
The encoders are applied to the *noisy* received matrix ``Y``.  NMSE against
``Y`` is what a bit-exact transport metric would report, but for any encoder
that discards noise-only components (delay-domain truncation, low-rank
projection) it saturates at about ``-SNR`` dB because the discarded noise is
counted as distortion.  NMSE against the noiseless ``S`` (or the effective
SNR) tells you how much *signal* was lost.  Experiment 4 reports both.
"""

from __future__ import annotations

import numpy as np


def nmse_linear(Y: np.ndarray, Y_hat: np.ndarray) -> float:
    den = np.linalg.norm(Y, "fro") ** 2
    if den == 0.0:
        return 0.0 if np.linalg.norm(Y_hat, "fro") == 0.0 else float("inf")
    return float(np.linalg.norm(Y - Y_hat, "fro") ** 2 / den)


def nmse(Y: np.ndarray, Y_hat: np.ndarray) -> float:
    return float(10.0 * np.log10(nmse_linear(Y, Y_hat) + 1e-20))


def effective_snr_db(S: np.ndarray, Y_hat: np.ndarray) -> float:
    """10 log10(||S||^2 / ||S - Y_hat||^2): signal over (noise + compression) error."""
    return float(-nmse(S, Y_hat))


def original_bits(M: int, N: int, bits_per_component: int = 16) -> int:
    return int(2 * M * N * bits_per_component)


def compression_ratio(orig_bits: float, used_bits: float) -> float:
    if used_bits <= 0:
        raise ValueError("used_bits must be positive")
    return float(orig_bits / used_bits)
