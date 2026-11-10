"""Exp14: stronger existing baselines (Gauss-Seidel, block conjugate gradient) vs the proposed cold start."""
from common import *
from scipy.linalg import solve_triangular
import warnings; warnings.filterwarnings("ignore")


def gauss_seidel_inverse(Gh, sweeps):
    """GS on Gh X = I from X0 = I; one sweep = triangular solve + U product ~ 1 K^3-MAC GEMM-equivalent."""
    S, K, _ = Gh.shape
    out = np.empty_like(Gh)
    for i in range(S):
        A = Gh[i]
        DL = np.tril(A); U = np.triu(A, 1)
        X = np.eye(K, dtype=A.dtype)
        for _ in range(sweeps):
            X = solve_triangular(DL, np.eye(K) - U @ X, lower=True)
        out[i] = X
    return out


def cg_inverse(Gh, iters):
    """Block CG on Gh X = I (K independent right-hand sides, Hestenes-Stiefel per column); 1 GEMM per iteration."""
    S, K, _ = Gh.shape
    X = np.zeros_like(Gh); R = np.broadcast_to(np.eye(K, dtype=Gh.dtype), Gh.shape).copy(); P = R.copy()
    rs = np.sum(np.abs(R) ** 2, axis=-2)
    for _ in range(iters):
        AP = Gh @ P
        a = rs / np.maximum(np.real(np.sum(np.conj(P) * AP, axis=-2)), 1e-30)
        X = X + P * a[:, None, :]; R = R - AP * a[:, None, :]
        rn = np.sum(np.abs(R) ** 2, axis=-2)
        P = R + P * (rn / np.maximum(rs, 1e-30))[:, None, :]; rs = rn
    return X


def main(n=12):
    res = {}
    for pn, kw in {"M=64,K=16": dict(M=64, K=16), "M=128,K=16": dict(M=128, K=16), "M=64,K=32": dict(M=64, K=32)}.items():
        acc = {}
        for cfg, ch, H, al, rho in drops(n, seed0=5000, **kw):
            G = gram(H, al); Gh, s = equilibrate(G); r_ex = rate_with(H, np.linalg.inv(G), rho)
            a, b = interval(G, Gh, al)
            runs = {}
            for g in range(2, 13):
                runs.setdefault("Gauss-Seidel", []).append((g, gauss_seidel_inverse(Gh, g)))
                runs.setdefault("Block CG (no spectrum info)", []).append((g, cg_inverse(Gh, g)))
                runs.setdefault("Chebyshev-MP (ours)", []).append((g - 1, chebyshev_inverse(Gh, Ctx(), a, b, g)))
            for d0 in range(1, 9):
                for st in range(1, 4):
                    c = Ctx(); X = cheb_ns(Gh, c, a, b, d0, st)
                    runs.setdefault(f"_cheb_ns_{d0}_{st}", []).append((c.gemms, X))
            for name, lst in runs.items():
                for g, X in lst:
                    l = 100 * (1 - rate_with(H, unequilibrate(X, s), rho) / r_ex)
                    acc.setdefault(name, {}).setdefault(g, []).append(l if np.isfinite(l) else 100)
        out = {}
        for name, d in acc.items():
            if name.startswith("_cheb_ns"):
                continue
            out[name] = {int(g): float(np.mean(v)) for g, v in sorted(d.items())}
        best = {}
        for name, d in acc.items():
            if name.startswith("_cheb_ns"):
                for g, v in d.items():
                    best[int(g)] = min(best.get(int(g), 1e9), float(np.mean(v)))   # oracle best-per-budget over a small grid
        out["Chebyshev-MP init + NS (ours; best of grid per budget)"] = dict(sorted(best.items()))
        res[pn] = out
        print(pn)
        for name, d in out.items():
            ok = [g for g, l in d.items() if l <= 1.0]
            print(f"   {name:55s} GEMMs for <=1% loss: {min(ok) if ok else '>' + str(max(d))}")
    dump(res, "exp14_stronger_baselines")

if __name__ == "__main__":
    main()
