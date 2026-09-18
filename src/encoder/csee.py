"""CSEE -- Compressed Sparse delay-domain Encoder (delay-domain top-K + BFP).

Idea
----
A TDL channel has a handful of delay taps, so the received matrix is sparse
along the delay axis after an IFFT over subcarriers.  All antennas share the
same tap delays, so one support set ``S`` (|S| = K) is selected from the
antenna-summed delay-domain energy and signalled once.

    Y_d = IFFT_N(Y)  (row-wise),   S = TopK_n( sum_m |Y_d[m, n]|^2 ),
    transmit  BFP(Y_d[:, S]) + S,   decode  Y_hat = FFT_N( zero-fill(Y_d[:, S]) ).

Complexity O(M N log N) for the FFT + O(N) partial sort + O(M K) quantisation.

Proposition 1 (NMSE decomposition; exact tail term)
---------------------------------------------------
With numpy's normalisation ``||Y||_F^2 = N ||Y_d||_F^2``, the FFT is a scaled
isometry, so

    NMSE = ( T_S + E_q ) / ||Y_d||_F^2,
    T_S  = sum_{n not in S} ||Y_d[:, n]||^2     (discarded tail energy, exact),
    E_q  = ||Y_d[:, S] - Q(Y_d[:, S])||_F^2       (BFP quantisation energy).

``E_q`` is predicted from the block exponents alone, either as the high-rate
estimate ``sum Delta^2/6`` or the deterministic worst case ``sum Delta^2/2``.
The worst-case version is a true upper bound; the estimate is what the
allocator uses as a rate-distortion predictor because it can be evaluated for
every candidate ``(K, bits)`` without running the encoder.
"""

from __future__ import annotations

import numpy as np

from ..metrics.nmse import compression_ratio, original_bits
from .bfp import (
    DEFAULT_BLOCK,
    bfp_bits_used,
    bfp_decode,
    bfp_encode,
    bfp_quantization_noise_energy,
)


def _support_bits(K: int, N: int) -> int:
    return int(K * int(np.ceil(np.log2(max(N, 2)))))


class CSEEEncoder:
    def __init__(self, K: int, bits: int = 10, block_size: int = DEFAULT_BLOCK):
        if K < 1:
            raise ValueError("K must be >= 1")
        self.K, self.bits, self.block_size = int(K), int(bits), int(block_size)

    # -- core ---------------------------------------------------------------
    @staticmethod
    def delay_domain(Y: np.ndarray) -> np.ndarray:
        return np.fft.ifft(Y, axis=1)

    @staticmethod
    def select_support(Yd: np.ndarray, K: int) -> np.ndarray:
        energy = (np.abs(Yd) ** 2).sum(axis=0)
        K = min(K, Yd.shape[1])
        idx = np.argpartition(energy, -K)[-K:]
        return np.sort(idx)

    def encode(self, Y: np.ndarray) -> dict:
        M, N = Y.shape
        Yd = self.delay_domain(Y)
        S = self.select_support(Yd, self.K)
        return {"taps": bfp_encode(Yd[:, S], self.bits, self.block_size), "support": S, "M": M, "N": N}

    def decode(self, enc: dict) -> np.ndarray:
        Yd_hat = np.zeros((enc["M"], enc["N"]), dtype=np.complex128)
        Yd_hat[:, enc["support"]] = bfp_decode(enc["taps"])
        return np.fft.fft(Yd_hat, axis=1)

    def bits_used(self, enc: dict) -> int:
        return bfp_bits_used(enc["taps"]) + _support_bits(len(enc["support"]), enc["N"])

    def compression_ratio(self, enc: dict) -> float:
        return compression_ratio(original_bits(enc["M"], enc["N"]), self.bits_used(enc))

    # -- analysis -----------------------------------------------------------
    @staticmethod
    def predicted_bits(M: int, N: int, K: int, bits: int, block_size: int = DEFAULT_BLOCK) -> int:
        """Rate of a CSEE operating point without encoding (exact bit accounting)."""
        K = min(K, N)
        n_blocks = -(-K // block_size)
        return 2 * bits * M * K + 4 * M * n_blocks + _support_bits(K, N)

    @staticmethod
    def predict_menu(Yd: np.ndarray, Ks, bits_list, block_size: int = DEFAULT_BLOCK,
                     noise_var: float | None = None) -> np.ndarray:
        """Proposition-1 predictions for every (K, bits) pair, shape (len(Ks), len(bits_list)).

        Same numbers as :meth:`theoretical_nmse_bound` (estimate form) but the
        block maxima are computed once per K and the ``bits`` dependence is
        applied as a shift of ``log2(qmax)``, so a whole menu costs about one
        encoder pass instead of one per option.

        ``noise_var`` (per-element variance sigma^2 of W in Y = S + W, known to
        the RU from its noise estimate) switches to the *noise-aware* form,
        which predicts the distortion against the noiseless S instead of Y:
        the discarded tail is credited with the noise it contains, the kept
        bins are charged with the noise they carry, and the denominator is the
        signal energy.  In delay-domain units the white noise has total energy
        M sigma^2 spread evenly over the N bins.
        """
        M, N = Yd.shape
        total = float((np.abs(Yd) ** 2).sum())
        out = np.zeros((len(Ks), len(bits_list)))
        if total == 0.0:
            return out
        noise_total = 0.0 if noise_var is None else float(M * noise_var)
        signal_total = max(total - noise_total, 1e-12 * total)
        energy = (np.abs(Yd) ** 2).sum(axis=0)
        order = np.argsort(-energy, kind="stable")
        cum = np.cumsum(energy[order])
        log_qmax = np.log2(np.array([2 ** (int(b) - 1) - 1 for b in bits_list], dtype=float))
        for i, K in enumerate(Ks):
            K = min(int(K), N)
            S = np.sort(order[:K])
            tail = total - cum[K - 1]
            sub = Yd[:, S]
            n_blocks = -(-K // block_size)
            pad = n_blocks * block_size - K
            if pad:
                sub = np.concatenate([sub, np.zeros((M, pad), dtype=sub.dtype)], axis=1)
            xb = sub.reshape(M, n_blocks, block_size)
            max_abs = np.maximum(np.abs(xb.real), np.abs(xb.imag)).max(axis=-1)      # (M, n_blocks)
            nonzero = (np.abs(xb) > 0).sum(axis=-1)
            with np.errstate(divide="ignore"):
                log_max = np.log2(max_abs)
            if noise_var is None:
                dist_fixed, den = tail, total
            else:
                noise_in_tail = noise_total * (N - K) / N
                noise_in_kept = noise_total * K / N
                dist_fixed, den = max(tail - noise_in_tail, 0.0) + noise_in_kept, signal_total
            for j, lq in enumerate(log_qmax):
                e = np.ceil(log_max - lq)
                e[~np.isfinite(e)] = 0.0
                e_q = float((np.exp2(2.0 * e) * nonzero / 6.0).sum())
                out[i, j] = (dist_fixed + e_q) / den
        return out

    @staticmethod
    def theoretical_nmse_bound(Y: np.ndarray, K: int, bits: int = 10,
                               block_size: int = DEFAULT_BLOCK, worst_case: bool = False,
                               Yd: np.ndarray | None = None) -> float:
        """Proposition 1: linear NMSE = (tail energy + predicted BFP error) / ||Y_d||^2."""
        Yd = CSEEEncoder.delay_domain(Y) if Yd is None else Yd
        total = float((np.abs(Yd) ** 2).sum())
        if total == 0.0:
            return 0.0
        S = CSEEEncoder.select_support(Yd, K)
        kept = float((np.abs(Yd[:, S]) ** 2).sum())
        tail = total - kept
        e_q = bfp_quantization_noise_energy(Yd[:, S], bits, block_size, worst_case=worst_case)
        return float((tail + e_q) / total)
