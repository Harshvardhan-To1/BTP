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
