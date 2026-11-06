"""Exp15: optimised C kernels (AVX/FMA + OpenMP) vs numpy/LAPACK and a hand-written C Cholesky inverse."""
from common import *
from cmatinv.fastkernels import ns_step, chol_inverse
import time, os, json


def timeit(fn, reps=40):
    for _ in range(5): fn()
    t = []
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); t.append(time.perf_counter() - t0)
    return 1e3 * float(np.median(t))


def main(S=273, M=64):
    rng = np.random.default_rng(0)
    rows = []
    for K in (8, 16, 32):
        H = ((rng.standard_normal((S, K, M)) + 1j * rng.standard_normal((S, K, M))) / np.sqrt(2)).astype(np.complex64)
        G = (H @ np.conj(np.swapaxes(H, -1, -2)) + (K / 10) * np.eye(K)).astype(np.complex64)
        X0 = (np.linalg.inv(G) * (1 + 0.03 * rng.standard_normal((S, K, K)))).astype(np.complex64)
        out = np.empty_like(X0)
        I2 = 2 * np.eye(K, dtype=np.complex64)
        r = dict(K=K,
                 lapack_inv=timeit(lambda: np.linalg.inv(G)),
                 numpy_ns_step=timeit(lambda: X0 @ (I2 - G @ X0)),
                 c_chol_1t=timeit(lambda: chol_inverse(G, 1)),
                 c_chol_4t=timeit(lambda: chol_inverse(G, 4)),
                 c_ns_1t=timeit(lambda: ns_step(G, X0, out, 1)),
                 c_ns_4t=timeit(lambda: ns_step(G, X0, out, 4)))
        r["c_ns_2steps_4t"] = timeit(lambda: ns_step(G, ns_step(G, X0, out, 4)[0], out, 4))
        rows.append({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
        print(rows[-1])
    dump(dict(S=S, M=M, nproc=os.cpu_count(), rows=rows), "exp15_kernel_bench")
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    labs = [("lapack_inv", "numpy/LAPACK inv"), ("c_chol_4t", "C Cholesky inverse (4 thr)"),
            ("numpy_ns_step", "numpy NS step"), ("c_ns_4t", "C fused NS step (4 thr)")]
    for i, (k, l) in enumerate(labs):
        ax.bar(np.arange(3) + (i - 1.5) * 0.2, [r[k] for r in rows], 0.2, label=l)
    ax.set_yscale("log"); ax.set_xticks(range(3)); ax.set_xticklabels([f"K={r['K']}" for r in rows])
    ax.axhline(0.5, c="k", ls=":"); ax.text(-0.4, 0.55, "0.5 ms slot", fontsize=7)
    ax.set_ylabel("ms per slot (273 PRBs)"); ax.legend(fontsize=7)
    save(fig, "exp15_kernel_bench")

if __name__ == "__main__":
    main()
