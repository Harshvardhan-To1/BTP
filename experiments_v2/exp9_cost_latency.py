"""Exp9: honest cost model (complex MACs, critical path) + measured CPU wall-clock, batched over PRBs."""
from common import *
import time, platform


def timeit(fn, reps=15):
    fn()
    t = []
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); t.append(time.perf_counter() - t0)
    return 1e3 * float(np.median(t))


def main(S=273, M=64):
    rng = np.random.default_rng(0)
    rows = []
    for K in (8, 16, 32):
        H = ((rng.standard_normal((S, K, M)) + 1j * rng.standard_normal((S, K, M))) / np.sqrt(2)).astype(np.complex64)
        G = H @ np.conj(np.swapaxes(H, -1, -2)) + (K / 10) * np.eye(K, dtype=np.complex64)
        Gh, s = equilibrate(G)
        Gh = Gh.astype(np.complex64)
        a, b = interval(G, Gh, K / 10)
        X0 = np.linalg.inv(Gh).astype(np.complex64)
        I2 = 2 * np.eye(K, dtype=np.complex64)
        Hh = np.conj(np.swapaxes(H, -1, -2))
        t = dict(
            gram=timeit(lambda: H @ Hh),
            exact=timeit(lambda: np.linalg.inv(G)),
            chol=timeit(lambda: np.linalg.cholesky(G)),
            cold6=timeit(lambda: cheb_ns(Gh, Ctx(), a, b, 3, 2)),
            warm1=timeit(lambda: X0 @ (I2 - Gh @ X0)),
            warm2=timeit(lambda: (lambda X: X @ (I2 - Gh @ X))(X0 @ (I2 - Gh @ X0))),
            wform=timeit(lambda: Hh @ X0),
        )
        rows.append(dict(K=K, M=M, S=S, **{k: round(v, 3) for k, v in t.items()},
                         macs_exact_inv=K**3, macs_w_formation=K * K * M, macs_gram=K * K * M,
                         depth_exact=3 * K, depth_cold6=int(6 * (np.log2(K) + 1)), depth_warm1=int(2 * (np.log2(K) + 1))))
        print(rows[-1])
    dump(dict(host=platform.processor() or platform.machine(), numpy=np.__version__, rows=rows), "exp9_cost_latency")
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    Ks = [r["K"] for r in rows]; w = 0.2
    for i, (k, lab) in enumerate([("exact", "LAPACK inv (batched)"), ("cold6", "Cheb-MP+2NS (6 GEMM)"),
                                  ("warm1", "warm NS x1 (2 GEMM)"), ("wform", "W = H$^H$G$^{-1}$ product")]):
        ax[0].bar(np.arange(3) + (i - 1.5) * w, [r[k] for r in rows], w, label=lab)
    ax[0].set_xticks(range(3)); ax[0].set_xticklabels([f"K={k}" for k in Ks]); ax[0].set_ylabel("ms per slot (273 PRBs, 4-core CPU)")
    ax[0].set_yscale("log"); ax[0].legend(fontsize=7); ax[0].axhline(0.5, c="k", ls=":"); ax[0].text(-0.4, 0.55, "0.5 ms slot", fontsize=7)
    ax[0].set_title("measured wall-clock")
    ax[1].bar(np.arange(3) - 0.2, [r["macs_exact_inv"] / (r["macs_exact_inv"] + r["macs_w_formation"] + r["macs_gram"]) * 100 for r in rows], 0.4, label="inversion share of RZF MACs")
    ax[1].bar(np.arange(3) + 0.2, [r["macs_w_formation"] / (r["macs_exact_inv"] + r["macs_w_formation"] + r["macs_gram"]) * 100 for r in rows], 0.4, label="W formation share")
    ax[1].set_xticks(range(3)); ax[1].set_xticklabels([f"K={k}" for k in Ks]); ax[1].set_ylabel("% of RZF complex MACs"); ax[1].legend(fontsize=7)
    ax[1].set_title("where the RZF compute goes (M=64)")
    save(fig, "exp9_cost_latency")

if __name__ == "__main__":
    main()
