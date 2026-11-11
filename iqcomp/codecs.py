"""Per-PRB, per-slot IQ encoders. Every encoder returns (Yhat, bits) for Y [P, M, n] (n = 12 x 14).

Bit accounting follows O-RAN WG4 block floating point: one 4-bit exponent per block of 12 complex
samples (one PRB, one stream, one symbol) and b-bit signed mantissas for I and Q. The uncompressed
reference is 16-bit I + 16-bit Q per sample.
"""
from __future__ import annotations

import numpy as np

from .uplink import SC, SYM

RAW_BITS = 16
EXP_BITS = 4


def raw_bits(P, M):
    return P * M * SC * SYM * 2 * RAW_BITS


def _bfp_blocks(x, b, axis):
    """Quantise complex x with one power-of-two exponent per block along `axis` (b-bit signed mantissas)."""
    peak = np.max(np.maximum(np.abs(x.real), np.abs(x.imag)), axis=axis, keepdims=True)
    lv = 2 ** (b - 1) - 1
    e = np.ceil(np.log2(np.maximum(peak, 1e-30) / lv))
    scale = 2.0 ** e
    q = lambda v: np.clip(np.round(v / scale), -lv - 1, lv) * scale
    return q(x.real) + 1j * q(x.imag)


def bfp_stream(Z, b):
    """BFP over streams Z [P, R, n] in O-RAN blocks of 12 subcarriers per symbol. Returns (Zhat, bits)."""
    P, R, n = Z.shape
    Zb = Z.reshape(P, R, SC, SYM)
    Zq = _bfp_blocks(Zb, b, axis=2).reshape(P, R, n)
    return Zq, P * R * SYM * (SC * 2 * b + EXP_BITS)


def bfp(Y, b):
    return bfp_stream(Y, b)


def _quant_basis(Q, bq):
    """BFP for a basis Q [P, M, r]: one exponent per column. Returns (Qhat, bits)."""
    P, M, r = Q.shape
    return _bfp_blocks(Q, bq, axis=1), P * r * (M * 2 * bq + EXP_BITS)


def _project(Y, Qh):
    """Least-squares coefficients of Y on the (quantised) basis: L = (Q^H Q)^-1 Q^H Y."""
    QhH = np.conj(np.swapaxes(Qh, -1, -2))
    return np.linalg.solve(QhH @ Qh, QhH @ Y)


def mp_rank(Y, noise_var=1.0, margin=1.5, r_max=None):
    """Signal rank per PRB: eigenvalues of Y Y^H / n above the Marchenko-Pastur noise edge.

    For pure noise, eig(Y Y^H / n) <= noise_var (1 + sqrt(M/n))^2 asymptotically; `margin` covers the
    finite-size Tracy-Widom fluctuation. Needs only the noise variance, which the RU measures on
    unallocated subcarriers.
    """
    P, M, n = Y.shape
    ev = np.linalg.eigvalsh(Y @ np.conj(np.swapaxes(Y, -1, -2)) / n)
    edge = noise_var * (1 + np.sqrt(M / n)) ** 2 * margin
    r = np.sum(ev > edge, axis=-1)
    return np.clip(r, 1, r_max or M)


def _subspace_code(Y, Q, r, b, bq):
    """Truncate basis Q [P, M, >=r_max] to per-PRB rank r (array), quantise, project, quantise coefficients."""
    P, M, n = Y.shape
    r = np.broadcast_to(np.asarray(r), (P,))
    Yhat = np.empty_like(Y)
    bits = 0
    for rr in np.unique(r):
        idx = np.nonzero(r == rr)[0]
        Qr = Q[idx, :, :rr]
        Qh, bq_bits = _quant_basis(Qr, bq)
        L = _project(Y[idx], Qh)
        Lh, l_bits = bfp_stream(L, b)
        Yhat[idx] = Qh @ Lh
        bits += bq_bits + l_bits
    return Yhat, bits


def svd_code(Y, r, b=9, bq=8):
    """PCA / truncated SVD per PRB: exact top-r left singular vectors (O(M^2 n) per PRB)."""
    YH = np.conj(np.swapaxes(Y, -1, -2))
    ev, U = np.linalg.eigh(Y @ YH)
    U = U[..., ::-1]
    return _subspace_code(Y, U, r, b, bq)


def ras_code(Y, r, b=9, bq=8, oversample=4, sketch="gaussian", pilot_cols=None, seed=0):
    """RAS-BFP: randomised range finder (Halko-Martinsson-Tropp) per PRB, then BFP.

    sketch="gaussian": Z = Y Omega with Omega complex Gaussian [n, r_max + p]  (O(M n (r+p)))
    sketch="pilot":    Z = Y[:, :, pilot_cols], i.e. a column-sampling sketch on the DMRS REs (no GEMM).
    The sketch range is rotated to its principal directions with an SVD of the small (r+p) x n matrix.
    """
    P, M, n = Y.shape
    r_arr = np.broadcast_to(np.asarray(r), (P,))
    k = int(r_arr.max()) + oversample
    if sketch == "pilot":
        Z = Y[:, :, pilot_cols]
    else:
        rng = np.random.default_rng(seed)
        Om = (rng.standard_normal((n, k)) + 1j * rng.standard_normal((n, k))) / np.sqrt(2)
        Z = Y @ Om
    Qz, _ = np.linalg.qr(Z)                                  # [P, M, k]
    B = np.conj(np.swapaxes(Qz, -1, -2)) @ Y                 # [P, k, n]
    Ub, _, _ = np.linalg.svd(B, full_matrices=False)
    return _subspace_code(Y, Qz @ Ub, r_arr, b, bq)


def dft_beamspace_code(Y, r, b=9):
    """Prior-art beamspace compression: project on the M-point DFT (ULA) beams, keep the r strongest
    beams per PRB, send them with BFP plus log2(M) bits per selected beam index."""
    P, M, n = Y.shape
    F = np.exp(-2j * np.pi * np.outer(np.arange(M), np.arange(M)) / M) / np.sqrt(M)
    Bm = np.conj(F.T)[None] @ Y                              # [P, M, n]
    r_arr = np.broadcast_to(np.asarray(r), (P,))
    order = np.argsort(-np.sum(np.abs(Bm) ** 2, axis=-1), axis=-1)
    Yhat = np.empty_like(Y)
    bits = 0
    for rr in np.unique(r_arr):
        idx = np.nonzero(r_arr == rr)[0]
        sel = order[idx, :rr]
        Bs = np.take_along_axis(Bm[idx], sel[..., None], axis=1)
        Bq, bb = bfp_stream(Bs, b)
        Fs = F[:, sel].transpose(1, 0, 2)                    # [p, M, rr]
        Yhat[idx] = Fs @ Bq
        bits += bb + len(idx) * rr * int(np.ceil(np.log2(M)))
    return Yhat, bits


def pilot_code(Y, b=9, bq=8, pilot_cols=None, margin=1.5, noise_var=1.0, r_fixed=None):
    """RAS-BFP with a pilot column-sampling sketch and RMT rank selection from the sketch itself.

    Z = Y[:, :, pilot_cols] (M x p) is both the range sketch and the rank detector: eigenvalues of Z^H Z / p
    above the Marchenko-Pastur edge noise_var (1 + sqrt(M/p))^2 give r. Cost per PRB: O(M p^2) for the
    sketch SVD plus O(M n r) for the projection -- no M x M eigen-decomposition.
    """
    P, M, n = Y.shape
    Z = Y[:, :, pilot_cols]
    p = Z.shape[-1]
    U, sv, _ = np.linalg.svd(Z, full_matrices=False)
    if r_fixed is None:
        edge = noise_var * (1 + np.sqrt(M / p)) ** 2 * margin
        r = np.clip(np.sum(sv ** 2 / p > edge, axis=-1), 1, p)
    else:
        r = np.full(P, r_fixed)
    return _subspace_code(Y, U, r, b, bq), r


def rrqr_basis(Z, noise_var=1.0, margin=1.5, r_max=None):
    """Greedy column-pivoted Gram-Schmidt on the pilot sketch Z [P, M, p] with a noise stopping rule.

    After i directions are removed, the residual energy of a noise-only column is chi-square with mean
    (M - i) noise_var and std sqrt(M - i) noise_var, so the largest of p such columns is about
    (M - i) noise_var (1 + sqrt(2 ln p / (M - i))). Stop when the best remaining column falls below that
    level times `margin` on the deviation term. Cost O(M p r) per PRB, no eigen-decomposition.
    """
    P, M, p = Z.shape
    r_max = r_max or p
    W = Z.copy()
    Q = np.zeros((P, M, r_max), Z.dtype)
    nrm = np.sum(np.abs(W) ** 2, axis=1)                                 # [P, p]
    active = np.ones(P, bool)
    r = np.zeros(P, int)
    for i in range(r_max):
        thr = (M - i) * noise_var * (1 + margin * np.sqrt(2 * np.log(p) / (M - i)))
        j = np.argmax(nrm, axis=1)
        best = nrm[np.arange(P), j]
        active &= best > thr
        if not active.any():
            break
        q = W[np.arange(P), :, j] / np.sqrt(np.maximum(best, 1e-30))[:, None]
        q[~active] = 0
        Q[:, :, i] = q
        r += active
        c = np.einsum("pm,pmj->pj", np.conj(q), W)
        W -= q[:, :, None] * c[:, None, :]
        nrm = np.sum(np.abs(W) ** 2, axis=1)
        nrm[np.arange(P), j] = 0
    return Q, np.maximum(r, 1)


def rrqr_code(Y, b=9, bq=8, pilot_cols=None, margin=1.5, noise_var=1.0):
    """RAS-BFP with the pilot sketch and the RRQR noise-stopping rank (the variant implemented in C)."""
    Q, r = rrqr_basis(Y[:, :, pilot_cols], noise_var, margin)
    return _subspace_code(Y, Q, r, b, bq), r


def combine_code(Y, H, power, b=9, noise_var=1.0):
    """CSI-aided reference (O-RAN Category-B-style uplink): the RU applies per-subcarrier MMSE combiners
    supplied by the DU and sends K streams. Weight transport is not counted here (C-plane)."""
    P, M, n = Y.shape
    K = H.shape[-1]
    Hs = np.sqrt(power) * H
    Hh = np.conj(np.swapaxes(Hs, -1, -2))
    F = np.linalg.solve(Hh @ Hs + noise_var * np.eye(K), Hh)              # [P, SC, K, M]
    Z = np.einsum("pskm,pmst->pkst", F, Y.reshape(P, M, SC, SYM)).reshape(P, K, n)
    Zq, bits = bfp_stream(Z, b)
    return Zq, bits


def dmrs_columns(symbols=(2, 11)):
    """Column indices (in the n = 12 x 14, subcarrier-major layout) of the DMRS REs of a PUSCH slot."""
    sc = np.arange(SC)
    return np.concatenate([sc * SYM + s for s in symbols])
