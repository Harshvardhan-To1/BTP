"""RAS-BFP -- Randomised-sketch Adaptive-rank Subspace encoder with BFP.

A randomised low-rank approximation (Halko, Martinsson & Tropp 2011,
Algorithm 4.1 + 5.1) that replaces the O(M N min(M,N)) SVD of the baseline
with a sketch-and-QR pipeline of cost O(M N l), l = r + p:

    1. Sketch the antenna dimension:  Z = Omega Y   (l x N),
       Omega = SRHT  sqrt(M/l) * S * H_M * D   (or Gaussian).
    2. Thin QR of Z^H = Q R  ->  Q (N x l) approximates the dominant right
       singular subspace of Y.
    3. Project:  L = Y Q  (M x l);  small SVD of L truncates to rank r:
       L_r = U_r S_r,  Q_r = Q V_r,   Y_hat = L_r Q_r^H.
    4. Transmit  BFP(L_r) and BFP(Q_r)  -- the same payload shape as the
       truncated-SVD baseline at the same r, so compression ratios match.

Theorem 2 (adapted from HMT 2011, Thm. 10.5, Gaussian test matrix, p >= 2)
--------------------------------------------------------------------------
    E ||Y - Q Q^H-projection error||_F^2 <= (1 + r/(p-1)) * sum_{i>r} sigma_i^2

and, because truncating the projected matrix to rank r adds at most another
Eckart-Young term (triangle inequality + contraction),

    E ||Y - Y_hat||_F^2 <= (4 + 2 r/(p-1)) * sum_{i>r} sigma_i^2.

The bound is for Gaussian sketches; SRHT (Tropp 2011) needs larger
oversampling for a proof, so with the default SRHT sketch the bound is a
reference that Experiment 1 checks empirically.  ``theoretical_error_bound``
returns the *squared* error bound before BFP quantisation.
"""

from __future__ import annotations

import numpy as np

from ..metrics.nmse import compression_ratio, original_bits
from .bfp import DEFAULT_BLOCK, bfp_bits_used, bfp_decode, bfp_encode

RANK_HEADER_BITS = 8


def fwht(x: np.ndarray) -> np.ndarray:
    """Fast Walsh-Hadamard transform along axis 0 (length must be a power of two), unnormalised."""
    n = x.shape[0]
    if n & (n - 1):
        raise ValueError("fwht length must be a power of two")
    y = x.copy()
    h = 1
    while h < n:
        y = y.reshape(-1, 2, h, *x.shape[1:])
        a, b = y[:, 0].copy(), y[:, 1].copy()
        y[:, 0], y[:, 1] = a + b, a - b
        y = y.reshape(n, *x.shape[1:])
        h *= 2
    return y


class RASBFPEncoder:
    def __init__(self, r: int, bits: int = 10, oversample: int = 4, sketch: str = "srht",
                 block_size: int = DEFAULT_BLOCK, seed: int = 0):
        if r < 1:
            raise ValueError("rank r must be >= 1")
        if oversample < 0:
            raise ValueError("oversample must be >= 0")
        if sketch not in ("srht", "gaussian"):
            raise ValueError("sketch must be 'srht' or 'gaussian'")
        self.r, self.bits, self.p = int(r), int(bits), int(oversample)
        self.sketch, self.block_size, self.seed = sketch, int(block_size), int(seed)

    # -- sketch ---------------------------------------------------------------
    def _sketch(self, Y: np.ndarray, ell: int) -> np.ndarray:
        M = Y.shape[0]
        rng = np.random.default_rng(self.seed)
        if self.sketch == "gaussian":
            Omega = (rng.standard_normal((ell, M)) + 1j * rng.standard_normal((ell, M))) / np.sqrt(2 * ell)
            return Omega @ Y
        M_pad = 1 << (M - 1).bit_length()
        D = rng.choice([-1.0, 1.0], size=M)
        Yd = Y * D[:, None]
        if M_pad != M:
            Yd = np.concatenate([Yd, np.zeros((M_pad - M, Y.shape[1]), dtype=Y.dtype)], axis=0)
        HY = fwht(Yd) / np.sqrt(M_pad)
        rows = rng.choice(M_pad, size=ell, replace=False)
        return np.sqrt(M_pad / ell) * HY[rows]

    # -- codec ----------------------------------------------------------------
    def encode(self, Y: np.ndarray) -> dict:
        M, N = Y.shape
        r = min(self.r, M, N)
        ell = min(r + self.p, M, N)
        Z = self._sketch(Y, ell)                              # (ell, N)
        Q, _ = np.linalg.qr(Z.conj().T)                       # (N, ell)
        L = Y @ Q                                             # (M, ell)
        if ell > r:
            U, s, Vh = np.linalg.svd(L, full_matrices=False)  # tiny: (M, ell)
            L = U[:, :r] * s[:r][None, :]
            Q = Q @ Vh[:r].conj().T
        return {
            "L": bfp_encode(L.T, self.bits, self.block_size),
            "V": bfp_encode(Q.T, self.bits, self.block_size),
            "r": r, "M": M, "N": N,
        }

    def decode(self, enc: dict) -> np.ndarray:
        L = bfp_decode(enc["L"]).T
        Q = bfp_decode(enc["V"]).T
        return L @ Q.conj().T

    def bits_used(self, enc: dict) -> int:
        return bfp_bits_used(enc["L"]) + bfp_bits_used(enc["V"]) + RANK_HEADER_BITS

    def compression_ratio(self, enc: dict) -> float:
        return compression_ratio(original_bits(enc["M"], enc["N"]), self.bits_used(enc))

    # -- analysis -------------------------------------------------------------
    @staticmethod
    def theoretical_error_bound(Y: np.ndarray, r: int, oversample: int = 4) -> float:
        """Theorem 2: expected squared low-rank error bound (before quantisation).

        Returns ``(4 + 2 r/(p-1)) * sum_{i>r} sigma_i^2`` for ``p >= 2``.  For
        ``p < 2`` the Gaussian theorem gives no finite bound and ``inf`` is
        returned rather than a made-up number.
        """
        if oversample < 2:
            return float("inf")
        s = np.linalg.svd(Y, compute_uv=False)
        tail = float((s[r:] ** 2).sum())
        return (4.0 + 2.0 * r / (oversample - 1)) * tail
