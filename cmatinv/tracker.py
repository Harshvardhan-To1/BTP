"""Proposed slot-to-slot inverse tracker ("RMT-WS"): warm-started Newton-Schulz with a randomised
residual certificate and a Marchenko-Pastur / Chebyshev cold-start fallback."""
from __future__ import annotations

import numpy as np

from .inverters import (Ctx, equilibrate, unequilibrate, moment_interval, cheb_ns, newton_schulz,
                        probe_residual, eye_like)

MP_LO, MP_HI = 0.5, 1.1


def cold_start(G, Gh, alpha, ctx, d0=3, steps=2):
    dg = np.real(np.diagonal(G, axis1=-2, axis2=-1))
    a, b = moment_interval(Gh, alpha / dg, margin_hi=MP_HI, margin_lo=MP_LO)
    return cheb_ns(Gh, ctx, a, b, d0, steps)


class WarmStartTracker:
    """mode: 'fixed' -> always `steps` warm NS iterations; 'adaptive' -> certificate-driven."""

    def __init__(self, alpha, mode="adaptive", steps=1, tol=0.002, r_refresh=0.3, max_steps=3,
                 probes=2, cold=(3, 2), seed=0, bits=None):
        self.bits = bits
        self.alpha, self.mode, self.steps, self.tol = alpha, mode, steps, tol
        self.r_refresh, self.max_steps, self.probes, self.cold = r_refresh, max_steps, probes, cold
        self.Ginv = None
        self.rng = np.random.default_rng(seed)
        self.stats = dict(refresh=0, total=0)

    def update(self, G):
        """Return (Ginv, gemm_cost_per_subcarrier_array)."""
        S, K, _ = G.shape
        Gh, s = equilibrate(G)
        if self.Ginv is None:
            ctx = Ctx(self.bits)
            X = cold_start(G, Gh, self.alpha, ctx, *self.cold)
            self.Ginv = unequilibrate(X, s)
            return self.Ginv, np.full(S, ctx.gemms)
        X0 = self.Ginv / (s[:, :, None] * s[:, None, :])
        cost = np.zeros(S)
        if self.mode == "fixed":
            ctx = Ctx(self.bits)
            X = newton_schulz(Gh, ctx, X0, self.steps)
            cost[:] = ctx.gemms
            self.Ginv = unequilibrate(X, s)
            return self.Ginv, cost
        rhat = probe_residual(Gh, X0, self.probes, self.rng)
        cost += 2.0 * self.probes / K                                   # certificate: 2 matvecs / probe
        ctx = Ctx(self.bits)
        cand = [X0]
        for _ in range(self.max_steps):
            cand.append(newton_schulz(Gh, ctx, cand[-1], 1))
        with np.errstate(divide="ignore", invalid="ignore"):
            n = np.ceil(np.log2(np.log(self.tol) / np.log(np.clip(rhat, 1e-12, 0.999))))
        n = np.clip(np.nan_to_num(n, nan=self.max_steps), 0, self.max_steps).astype(int)
        refresh = rhat > self.r_refresh
        X = np.stack(cand)[n, np.arange(S)]
        cost += 2.0 * n
        if refresh.any():
            c2 = Ctx(self.bits)
            Xc = cold_start(G, Gh, self.alpha, c2, *self.cold)
            X = np.where(refresh[:, None, None], Xc, X)
            cost = np.where(refresh, 2.0 * self.probes / K + c2.gemms, cost)
        self.stats["refresh"] += int(refresh.sum()); self.stats["total"] += S
        self.Ginv = unequilibrate(X, s)
        return self.Ginv, cost


def predicted_warm_residual(K, M, one_minus_rho, corr=1.0):
    """First-order Doppler law: residual of the previous-slot inverse, r0 ~ corr * 2 sqrt(K/(M-K)) sqrt(1-rho).

    Derivation sketch (i.i.d. equal-gain channel): H_t - H_{t-1} ~ sqrt(2(1-rho)) N, so
    I - G_t X_{t-1} ~ -(N H^H + H N^H) G^-1 sqrt(2(1-rho)); the Frobenius energy of that,
    divided by K, is 4 K/(M-K) (1-rho). `corr` ~ 1.2-1.5 absorbs near-far + spatial correlation (38.901).
    """
    return corr * 2.0 * np.sqrt(K / (M - K)) * np.sqrt(one_minus_rho)


def max_warm_speed_kmh(K, M, fc_hz=3.5e9, slot_s=0.5e-3, r_max=0.3, corr=1.0):
    """Largest UE speed for which one warm-start slot keeps r0 <= r_max (small-Doppler: 1-rho ~ (pi fD T)^2)."""
    c_coef = corr * 2.0 * np.sqrt(K / (M - K))
    fd = r_max / (c_coef * np.pi * slot_s)
    return fd * 299_792_458.0 / fc_hz * 3.6
