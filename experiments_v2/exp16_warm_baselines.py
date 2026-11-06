"""Exp16: warm-started Gauss-Seidel and CG (previous-slot inverse as initial guess) vs RMT-WS vs exact, under aging."""
from exp14_stronger_baselines import *
from cmatinv.tracker import WarmStartTracker
import warnings; warnings.filterwarnings("ignore")


def gs_warm(Gh, X0, sweeps):
    S, K, _ = Gh.shape
    out = np.empty_like(Gh)
    for i in range(S):
        A = Gh[i]; DL = np.tril(A); U = np.triu(A, 1); X = X0[i]
        for _ in range(sweeps):
            X = solve_triangular(DL, np.eye(K) - U @ X, lower=True)
        out[i] = X
    return out


def cg_warm(Gh, X0, iters):
    S, K, _ = Gh.shape
    X = X0.copy(); R = np.eye(K) - Gh @ X; P = R.copy(); rs = np.sum(np.abs(R) ** 2, axis=-2)
    for _ in range(iters):
        AP = Gh @ P
        a = rs / np.maximum(np.real(np.sum(np.conj(P) * AP, axis=-2)), 1e-30)
        X = X + P * a[:, None, :]; R = R - AP * a[:, None, :]
        rn = np.sum(np.abs(R) ** 2, axis=-2)
        P = R + P * (rn / np.maximum(rs, 1e-30))[:, None, :]; rs = rn
    return X


def main(n_drops=4, T=18):
    strat = {"exact (Cholesky), 1 GEMM-eq": ("exact", 0, 1.0),
             "warm Gauss-Seidel x2": ("gs", 2, 2.0), "warm Gauss-Seidel x4": ("gs", 4, 4.0),
             "warm CG x2 (+1 for residual)": ("cg", 2, 3.0), "warm CG x4 (+1)": ("cg", 4, 5.0),
             "RMT-WS (adaptive)": ("rmt", 0, None)}
    res = {}
    for v in (3, 30, 120):
        print("--", v, "km/h")
        for name, (kind, k, cost) in strat.items():
            L, C = [], []
            for cfg, ch, H0, al, rho in drops(n_drops, speed_kmh=v, M=64, K=16, seed0=5000):
                trk = WarmStartTracker(al, "adaptive") if kind == "rmt" else None
                prev = None
                for t, H in enumerate(ch.sequence(T)):
                    G = gram(H, al); Gh, s = equilibrate(G)
                    r_ex = rate_with(H, np.linalg.inv(G), rho)
                    if kind == "rmt":
                        Gi, c = trk.update(G); c = c.mean()
                    elif kind == "exact" or prev is None:
                        Gi, c = np.linalg.inv(G), 1.0
                    else:
                        X0 = prev / (s[:, :, None] * s[:, None, :])
                        X = gs_warm(Gh, X0, k) if kind == "gs" else cg_warm(Gh, X0, k)
                        Gi, c = unequilibrate(X, s), cost
                    prev = Gi
                    if t >= 2:
                        l = 100 * (1 - rate_with(H, Gi, rho) / r_ex)
                        L.append(l if np.isfinite(l) else 100.0); C.append(c)
            res[f"{v} | {name}"] = dict(loss_pct=float(np.mean(L)), gemms=float(np.mean(C)))
            print(f"  {name:32s} loss={np.mean(L):8.3f}%  GEMM-eq/slot={np.mean(C):.2f}")
    dump(res, "exp16_warm_baselines")

if __name__ == "__main__":
    main()
