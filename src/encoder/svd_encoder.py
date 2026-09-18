"""Truncated-SVD fronthaul encoder (strong low-rank baseline).

    Y = U S V^H,   Y_r = U_r S_r V_r^H          (Eckart-Young optimal rank-r)

The RU transmits ``L = U_r S_r`` (M x r) and ``V_r`` (N x r), both BFP
quantised with ``bits`` mantissa bits.  Uses the *economy* SVD
(``full_matrices=False``), cost O(M N min(M, N)); an earlier version of the
repository's Experiment 2 appears to have timed the full N x N SVD, which made
the baseline look ~100x slower than it should be.
"""

from __future__ import annotations

import numpy as np

from ..metrics.nmse import compression_ratio, original_bits
from .bfp import DEFAULT_BLOCK, bfp_bits_used, bfp_decode, bfp_encode

RANK_HEADER_BITS = 8


class SVDEncoder:
    def __init__(self, r: int, bits: int = 10, block_size: int = DEFAULT_BLOCK):
        if r < 1:
            raise ValueError("rank r must be >= 1")
        self.r, self.bits, self.block_size = int(r), int(bits), int(block_size)

    def encode(self, Y: np.ndarray) -> dict:
        M, N = Y.shape
        r = min(self.r, M, N)
        U, s, Vh = np.linalg.svd(Y, full_matrices=False)
        L = U[:, :r] * s[:r][None, :]                    # (M, r)
        V = Vh[:r].conj().T                              # (N, r)
        return {
            "L": bfp_encode(L.T, self.bits, self.block_size),   # blocks along M
            "V": bfp_encode(V.T, self.bits, self.block_size),   # blocks along N
            "r": r, "M": M, "N": N,
        }

    def decode(self, enc: dict) -> np.ndarray:
        L = bfp_decode(enc["L"]).T
        V = bfp_decode(enc["V"]).T
        return L @ V.conj().T

    def bits_used(self, enc: dict) -> int:
        return bfp_bits_used(enc["L"]) + bfp_bits_used(enc["V"]) + RANK_HEADER_BITS

    def compression_ratio(self, enc: dict) -> float:
        return compression_ratio(original_bits(enc["M"], enc["N"]), self.bits_used(enc))

    @staticmethod
    def truncation_error(Y: np.ndarray, r: int) -> float:
        """||Y - Y_r||_F^2 = sum_{i>r} sigma_i^2 (Eckart-Young floor for any rank-r scheme)."""
        s = np.linalg.svd(Y, compute_uv=False)
        return float((s[r:] ** 2).sum())
