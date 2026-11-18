"""Exp22: the closest prior-art inverters, which Exp14/16 did not include (all are our implementations).

Cold start (GEMMs for <= 1 % RZF sum-rate loss, same drops as Exp14):
  * Chebyshev cubic matrix iteration X <- X (3I - A X (3I - A X)) (3 GEMMs / step), the iteration used by
    Chebyshev-iteration RZF precoding and the ChebI-NS family; initial value either the classical
    norm-based scalar or the MP-interval scalar 2 / (a + b).
  * ChebI-NS-style hybrid: one Chebyshev cubic step, then Newton-Schulz.
  * Truncated polynomial expansion (TPE) with coefficients that minimise the expected residual
    sum_l (1 - lambda p(lambda))^2 over the *exact* empirical spectral moments of A (an upper bound on
    TPE with RMT-predicted moments; the moment computation is not counted).
Tracking (same aging setup as Exp16):
  * Warm-started Neumann series around the previous inverse, X = sum_{i<n} (I - X0 A)^i X0, with an exact
    re-inversion every Tr slots (the time-correlated approximate inversion of the Malaga group).
"""
from common import *
from cmatinv.tracker import WarmStartTracker
import warnings; warnings.filterwarnings("ignore")


def cheb_cubic(Gh, ctx, X0, steps):
    I = eye_like(Gh)
    X = X0
    for _ in range(steps):
        Y = ctx.mm(Gh, X)
        X = ctx.mm(X, 3.0 * I - ctx.mm(Y, 3.0 * I - Y))
    return X


def tpe_moments(Gh, J):
    """TPE coefficients w (degree J-1) minimising mean_i (1 - lambda_i p(lambda_i))^2 with exact moments."""
    lam = np.linalg.eigvalsh(Gh)                                     # [S, K]
    m = np.stack([np.mean(lam ** j, -1) for j in range(2 * J + 1)], -1)
    A = np.stack([np.stack([m[:, l + k + 2] for k in range(J)], -1) for l in range(J)], -2)
    b = np.stack([m[:, l + 1] for l in range(J)], -1)
    return np.linalg.solve(A, b[..., None])[..., 0]                  # [S, J]


def tpe_inverse(Gh, ctx, w):
    I = eye_like(Gh)
    J = w.shape[-1]
    X = w[:, J - 1][:, None, None] * I
    for l in range(J - 2, -1, -1):
        X = w[:, l][:, None, None] * I + ctx.mm(Gh, X)
    return X


def neumann_warm(Gh, ctx, X0, terms):
    I = eye_like(Gh)
    E = I - ctx.mm(X0, Gh)
    S = I.copy()
    for _ in range(terms - 1):
        S = I + ctx.mm(E, S)
    return ctx.mm(S, X0)


def cold(n=12):
    res = {}
    for pn, kw in {"M=64,K=16": dict(M=64, K=16), "M=128,K=16": dict(M=128, K=16),
                   "M=64,K=32": dict(M=64, K=32)}.items():
        acc = {}
        for cfg, ch, H, al, rho in drops(n, seed0=5000, **kw):
            G = gram(H, al); Gh, s = equilibrate(G); r_ex = rate_with(H, np.linalg.inv(G), rho)
            a, b = interval(G, Gh, al)
            add = lambda name, c, X: acc.setdefault(name, {}).setdefault(c.gemms, []).append(
                100 * (1 - rate_with(H, unequilibrate(X, s), rho) / r_ex))
            for st in range(1, 8):
                c = Ctx(); add("Chebyshev cubic iteration, classical init", c, cheb_cubic(Gh, c, classical_ns_init(Gh), st))
                c = Ctx(); add("Chebyshev cubic iteration, MP-scalar init", c,
                               cheb_cubic(Gh, c, (2.0 / (a + b))[:, None, None] * eye_like(Gh), st))
                c = Ctx(); X = cheb_cubic(Gh, c, (2.0 / (a + b))[:, None, None] * eye_like(Gh), 1)
                add("ChebI-NS-style: 1 cubic step + Newton-Schulz", c, newton_schulz(Gh, c, X, st - 1)) if st > 1 else None
            for J in range(2, 18):
                c = Ctx(); add("TPE, exact-moment optimal coefficients", c, tpe_inverse(Gh, c, tpe_moments(Gh, J)))
            for d0 in range(1, 9):
                for st in range(1, 4):
                    c = Ctx(); add("_ours", c, cheb_ns(Gh, c, a, b, d0, st))
        out = {}
        for name, d in acc.items():
            curve = {float(g): float(np.mean(np.where(np.isfinite(v), v, 100))) for g, v in sorted(d.items())}
            if name == "_ours":
                best = {}
                for g, l in curve.items():
                    best[g] = min(best.get(g, 1e9), l)
                name, curve = "Chebyshev-MP init + NS (ours)", best
            ok = [g for g, l in curve.items() if l <= 1.0]
            out[name] = dict(curve=curve, gemms_for_1pct=min(ok) if ok else None)
        res[pn] = out
        print(pn)
        for name, o in out.items():
            print(f"   {name:46s} GEMMs for <=1% loss: {o['gemms_for_1pct'] if o['gemms_for_1pct'] else '> max'}")
    return res


def tracking(n_drops=4, T=18):
    strat = {"warm Neumann n=2, exact every 8": (2, 8), "warm Neumann n=3, exact every 8": (3, 8),
             "warm Neumann n=4, exact every 8": (4, 8), "warm Neumann n=3, exact every 4": (3, 4),
             "RMT-WS (adaptive)": None}
    res = {}
    for v in (3, 30, 120):
        print("--", v, "km/h")
        for name, par in strat.items():
            L, C = [], []
            for cfg, ch, H0, al, rho in drops(n_drops, speed_kmh=v, M=64, K=16, seed0=5000):
                trk = WarmStartTracker(al, "adaptive") if par is None else None
                prev = None
                for t, H in enumerate(ch.sequence(T)):
                    G = gram(H, al); Gh, s = equilibrate(G)
                    r_ex = rate_with(H, np.linalg.inv(G), rho)
                    if par is None:
                        Gi, c = trk.update(G); c = c.mean()
                    elif prev is None or t % par[1] == 0:
                        Gi, c = np.linalg.inv(G), 1.0
                    else:
                        ctx = Ctx()
                        X = neumann_warm(Gh, ctx, prev / (s[:, :, None] * s[:, None, :]), par[0])
                        Gi, c = unequilibrate(X, s), ctx.gemms
                    prev = Gi
                    if t >= 2:
                        l = 100 * (1 - rate_with(H, Gi, rho) / r_ex)
                        L.append(l if np.isfinite(l) else 100.0); C.append(c)
            res[f"{v} | {name}"] = dict(loss_pct=float(np.mean(L)), gemms=float(np.mean(C)))
            print(f"  {name:34s} loss={np.mean(L):8.3f}%  GEMM-eq/slot={np.mean(C):.2f}")
    return res


def main():
    dump(dict(cold_start=cold(), tracking=tracking()), "exp22_prior_art_baselines")


if __name__ == "__main__":
    main()
