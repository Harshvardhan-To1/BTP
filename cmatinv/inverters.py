"""Complex Hermitian-positive-definite inversion kernels for RZF Gram matrices.

All kernels act on a *Jacobi-equilibrated* Gram matrix  Gh = D^-1/2 G D^-1/2  (unit
diagonal), batched over subcarriers: shape [S, K, K]. ``mm`` counts K^3-MAC complex
matrix products (the cost unit used throughout), optionally emulating a low-precision
GEMM unit (operands and result rounded to ``bits`` mantissa bits, wide accumulate).
"""
from __future__ import annotations

import numpy as np


def rnd(x, bits):
    """Round to `bits` mantissa bits (unbounded exponent); complex handled per component."""
    if bits is None:
        return x
    if np.iscomplexobj(x):
        return rnd(x.real, bits) + 1j * rnd(x.imag, bits)
    m, e = np.frexp(x)
    return np.ldexp(np.round(m * 2.0**bits) / 2.0**bits, e)


class Ctx:
    """Tracks GEMM count and (optionally) emulates low-precision GEMMs."""

    def __init__(self, bits=None):
        self.bits = bits
        self.gemms = 0.0

    def mm(self, a, b):
        self.gemms += 1
        return rnd(rnd(a, self.bits) @ rnd(b, self.bits), self.bits)


def equilibrate(G):
    d = np.real(np.diagonal(G, axis1=-2, axis2=-1))
    s = 1.0 / np.sqrt(d)
    return G * s[..., :, None] * s[..., None, :], s


def unequilibrate(Xh, s):
    return Xh * s[..., :, None] * s[..., None, :]


def eye_like(G):
    return np.broadcast_to(np.eye(G.shape[-1], dtype=G.dtype), G.shape)


# ---------------------------------------------------------------- spectral interval
def mp_interval(G, M, alpha, margin_hi=1.0, margin_lo=1.0):
    """Zero-eigensolve spectral interval [a, b] of the equilibrated Gram matrix.

    G = H H^H + alpha I  ->  Gh = Ah + diag(delta),  delta_k = alpha / G_kk,
    Ah = D^-1/2 H H^H D^-1/2 has rows of squared norm s_k = 1 - delta_k.
    Marchenko-Pastur edges (1 -+ sqrt(K/M))^2 for the unit-norm-row Gram plus Weyl's
    inequalities give  a = delta_min + s_min (1-sqrt(beta))^2,  b = delta_max + s_max (1+sqrt(beta))^2.
    Only K, M, alpha and diag(G) are used (O(K) work per matrix).
    """
    K = G.shape[-1]
    beta = K / M
    d = np.real(np.diagonal(G, axis1=-2, axis2=-1))
    delta = alpha / d
    s = 1.0 - delta
    lo = delta.min(-1) + s.min(-1) * max(1 - np.sqrt(beta), 0.0) ** 2 * margin_lo
    hi = delta.max(-1) + s.max(-1) * (1 + np.sqrt(beta)) ** 2 * margin_hi
    return lo, hi


def moment_interval(Gh, alpha_over_d, margin_hi=1.0, margin_lo=1.0):
    """Moment-matched MP interval: needs only ||Gh||_F (K^2 MACs) and the diagonal of G.

    Gh has unit diagonal, so its spectral mean is 1 and its variance is v = ||Gh||_F^2/K - 1
    (all off-diagonal energy). Writing Gh = delta_bar I + s_bar * MP-like  ->  edges
    1 + v/s_bar -+ 2 sqrt(v). Spatial correlation / LoS raise v and widen the interval
    automatically, which the fixed-ratio edge (1 -+ sqrt(K/M))^2 cannot do.
    """
    K = Gh.shape[-1]
    delta = alpha_over_d
    s_bar = 1.0 - delta.mean(-1)
    v = np.maximum(np.sum(np.abs(Gh) ** 2, axis=(-2, -1)) / K - 1.0, 1e-12)
    lo = np.maximum(delta.min(-1), 1 + v / s_bar - 2 * np.sqrt(v)) * margin_lo
    hi = (1 + v / s_bar + 2 * np.sqrt(v)) * margin_hi
    return lo, hi


def power_interval(Gh, iters=3, safety=1.15, rng=None, alpha_floor=None):
    """Alternative: lambda_max from a few power iterations (K^2 each), lambda_min = floor."""
    rng = rng or np.random.default_rng(0)
    S, K, _ = Gh.shape
    v = rng.standard_normal((S, K, 1)) + 1j * rng.standard_normal((S, K, 1))
    for _ in range(iters):
        v = Gh @ v
        v /= np.linalg.norm(v, axis=(-2, -1), keepdims=True)
    hi = np.real(np.einsum("ski,ski->s", v.conj(), Gh @ v)) * safety
    return alpha_floor, hi


# ---------------------------------------------------------------- kernels
def neumann(Gh, ctx, terms, omega=1.0):
    """Truncated Neumann series  omega * sum_{i<terms} (I - omega Gh)^i  (Horner, terms-1 GEMMs)."""
    I = eye_like(Gh)
    T = I - omega * Gh
    X = I.copy()
    for _ in range(terms - 1):
        X = I + ctx.mm(T, X)
    return omega * X


def newton_schulz(Gh, ctx, X0, steps):
    I = eye_like(Gh)
    X = X0
    for _ in range(steps):
        X = ctx.mm(X, 2.0 * I - ctx.mm(Gh, X))
    return X


def classical_ns_init(G):
    n1 = np.abs(G).sum(-2).max(-1)
    ni = np.abs(G).sum(-1).max(-1)
    return np.conj(np.swapaxes(G, -1, -2)) / (n1 * ni)[:, None, None]


def cheb_coeffs(a, b, d):
    """Chebyshev coefficients of 1/x on [a, b] (per-batch), degree d."""
    N = d + 1
    j = np.arange(N)
    th = np.pi * (j + 0.5) / N
    a = np.asarray(a)[..., None]
    b = np.asarray(b)[..., None]
    x = 0.5 * (b + a) + 0.5 * (b - a) * np.cos(th)
    f = 1.0 / x
    k = np.arange(N)
    return (2.0 / N) * np.einsum("...j,kj->...k", f, np.cos(np.outer(k, th)))


def chebyshev_inverse(Gh, ctx, a, b, d):
    """Degree-d Chebyshev polynomial p(Gh) ~ Gh^-1 on [a,b] via Clenshaw (d-1 GEMMs)."""
    I = eye_like(Gh)
    a = np.broadcast_to(a, Gh.shape[:1])
    b = np.broadcast_to(b, Gh.shape[:1])
    c = cheb_coeffs(a, b, d)
    T = (2.0 * Gh - (a + b)[:, None, None] * I) / (b - a)[:, None, None]
    ce = lambda k: c[:, k][:, None, None]
    if d == 0:
        return ce(0) / 2 * I
    b1, b2 = ce(d) * I, 0.0 * I
    for k in range(d - 1, 0, -1):
        Tb = ctx.mm(T, b1) if k < d - 1 else T * ce(d)
        b1, b2 = ce(k) * I + 2.0 * Tb - b2, b1
    Tb = ctx.mm(T, b1) if d > 1 else T * ce(1)
    return ce(0) / 2 * I + Tb - b2


def cheb_ns(Gh, ctx, a, b, d0, steps):
    """Proposed cold start: Chebyshev (MP interval) initial guess followed by Newton-Schulz."""
    X0 = chebyshev_inverse(Gh, ctx, a, b, d0)
    return newton_schulz(Gh, ctx, X0, steps)


def ns_optimal_scalar(Gh, ctx, a, b, steps):
    w = (2.0 / (a + b))[:, None, None]
    return newton_schulz(Gh, ctx, w * eye_like(Gh), steps)


def exact_inverse(Gh):
    return np.linalg.inv(Gh)


def gauss_jordan_lowprec(Gh, bits):
    """Direct (no-pivot, HPD-safe) Gauss-Jordan inversion with every operation rounded to `bits`."""
    S, K, _ = Gh.shape
    aug = np.concatenate([Gh, np.broadcast_to(np.eye(K, dtype=Gh.dtype), Gh.shape)], -1)
    aug = rnd(aug, bits)
    for c in range(K):
        piv = np.real(aug[:, c, c])[:, None]
        row = rnd(aug[:, c, :] / piv, bits)
        aug[:, c, :] = row
        f = aug[:, :, c].copy()
        f[:, c] = 0
        aug = rnd(aug - rnd(f[:, :, None] * row[:, None, :], bits), bits)
    return aug[:, :, K:]


def residual(Gh, X):
    K = Gh.shape[-1]
    R = np.eye(K) - Gh @ X
    return np.linalg.norm(R, axis=(-2, -1)) / np.sqrt(K)


# ---------------------------------------------------------------- certificate
def probe_residual(Gh, X, probes=2, rng=None):
    """Randomised residual certificate: ||(I - Gh X) z|| / ||z|| with Gaussian probes z (2K^2 per probe)."""
    rng = rng or np.random.default_rng(1)
    S, K, _ = Gh.shape
    z = rng.standard_normal((S, K, probes)) + 1j * rng.standard_normal((S, K, probes))
    r = z - Gh @ (X @ z)
    # E||Rz||^2 / ||z||^2 = ||R||_F^2 / K  ->  estimate of the normalised Frobenius residual
    return np.sqrt(np.sum(np.abs(r) ** 2, axis=(-2, -1)) / np.sum(np.abs(z) ** 2, axis=(-2, -1)))
