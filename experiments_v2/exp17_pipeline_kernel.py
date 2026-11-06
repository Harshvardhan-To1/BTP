"""Exp17: full per-slot RZF precoder (Gram + inverse + W + power scaling) -- numpy baseline vs fused C kernels."""
from common import *
from cmatinv.fastkernels import rzf_chol, rzf_ns
import time, os


def timeit(fn, reps=40):
    for _ in range(5): fn()
    t = []
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); t.append(time.perf_counter() - t0)
    return 1e3 * float(np.median(t))


def numpy_pipeline(H, al, P):
    G = H @ np.conj(np.swapaxes(H, -1, -2)) + al * np.eye(H.shape[1], dtype=np.complex64)
    W = np.conj(np.swapaxes(H, -1, -2)) @ np.linalg.inv(G)
    return W * np.sqrt(P / np.sum(np.abs(W) ** 2, axis=(-2, -1), keepdims=True))


def main(S=273):
    rng = np.random.default_rng(0)
    rows = []
    for K, M in ((8, 64), (16, 64), (32, 64), (16, 128), (32, 128)):
        H = ((rng.standard_normal((S, K, M)) + 1j * rng.standard_normal((S, K, M))) / np.sqrt(2)).astype(np.complex64)
        al, P = K / 10.0, 10.0
        G = H @ np.conj(np.swapaxes(H, -1, -2)) + al * np.eye(K, dtype=np.complex64)
        X = np.linalg.inv(G).astype(np.complex64)
        W = np.empty((S, K, M), np.complex64)
        r = dict(K=K, M=M, numpy_lapack=timeit(lambda: numpy_pipeline(H, al, P)),
                 c_fused_1t=timeit(lambda: rzf_chol(H, al, P, W, 1)),
                 c_fused_2t=timeit(lambda: rzf_chol(H, al, P, W, 2)),
                 c_fused_4t=timeit(lambda: rzf_chol(H, al, P, W, 4)),
                 c_ns_4t=timeit(lambda: rzf_ns(H, X.copy(), al, P, W, 4)))
        r["speedup_chol_4t"] = r["numpy_lapack"] / r["c_fused_4t"]
        rows.append({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
        print(rows[-1])
    dump(dict(S=S, nproc=os.cpu_count(), rows=rows), "exp17_pipeline_kernel")
    fig, ax = plt.subplots(figsize=(8, 3.8))
    labs = [("numpy_lapack", "numpy + LAPACK"), ("c_fused_1t", "fused C, GJ sweep (1 thr)"),
            ("c_fused_4t", "fused C, GJ sweep (4 thr)"), ("c_ns_4t", "fused C, Newton step (4 thr)")]
    for i, (k, l) in enumerate(labs):
        ax.bar(np.arange(len(rows)) + (i - 1.5) * 0.2, [r[k] for r in rows], 0.2, label=l)
    ax.set_yscale("log"); ax.set_xticks(range(len(rows))); ax.set_xticklabels([f"K={r['K']}\nM={r['M']}" for r in rows])
    ax.axhline(0.5, c="k", ls=":"); ax.text(-0.4, 0.55, "0.5 ms slot", fontsize=7)
    ax.set_ylabel("ms per slot, whole precoder (273 PRBs)"); ax.legend(fontsize=7)
    save(fig, "exp17_pipeline_kernel")

if __name__ == "__main__":
    main()
