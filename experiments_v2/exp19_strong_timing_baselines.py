"""Exp19: whole per-slot RZF precoder against stronger baselines.

Baselines: numpy inv (exp17), numpy batched solve (no explicit inverse), and a C precoder on OpenBLAS +
LAPACK (cherk + cpotrf + two ctrsm per subcarrier, OpenMP over subcarriers, same thread count).
"""
from common import *
from cmatinv.fastkernels import rzf_chol
import ctypes, time, os

_lib = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "..", "kernels", "liblapackbase.so"))
_p = ctypes.c_void_p
_lib.set_blas_single()
_lib.rzf_lapack.argtypes = [_p, _p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_int]


def rzf_lapack(H, al, P, W, threads):
    S, K, M = H.shape
    _lib.rzf_lapack(H.ctypes.data, W.ctypes.data, S, K, M, al, P, threads)
    return W


def timeit(fn, reps=200):
    for _ in range(5):
        fn()
    t = []
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); t.append(time.perf_counter() - t0)
    return 1e3 * float(np.median(t))


def np_inv(H, al, P):
    Hh = np.conj(np.swapaxes(H, -1, -2))
    G = H @ Hh + al * np.eye(H.shape[1], dtype=np.complex64)
    W = Hh @ np.linalg.inv(G)
    return W * np.sqrt(P / np.sum(np.abs(W) ** 2, axis=(-2, -1), keepdims=True))


def np_solve(H, al, P):
    G = H @ np.conj(np.swapaxes(H, -1, -2)) + al * np.eye(H.shape[1], dtype=np.complex64)
    Wt = np.conj(np.linalg.solve(G, H))                      # W^T = conj(G^-1 H), layout [S, K, M]
    return Wt * np.sqrt(P / np.sum(np.abs(Wt) ** 2, axis=(-2, -1), keepdims=True))


def main(S=273, threads=4):
    rng = np.random.default_rng(0)
    rows = []
    for K, M in ((8, 64), (16, 64), (32, 64), (16, 128), (32, 128)):
        H = ((rng.standard_normal((S, K, M)) + 1j * rng.standard_normal((S, K, M))) / np.sqrt(2)).astype(np.complex64)
        al, P = K / 10.0, 10.0
        W1, W2 = np.empty((S, K, M), np.complex64), np.empty((S, K, M), np.complex64)
        ref = np.swapaxes(np_inv(H.astype(np.complex128), al, P), -1, -2)
        rzf_chol(H, al, P, W1, threads); rzf_lapack(H, al, P, W2, threads)
        err = lambda W: float(np.linalg.norm(W - ref) / np.linalg.norm(ref))
        r = dict(K=K, M=M,
                 numpy_inv=timeit(lambda: np_inv(H, al, P)),
                 numpy_solve=timeit(lambda: np_solve(H, al, P)),
                 c_lapack_1t=timeit(lambda: rzf_lapack(H, al, P, W2, 1)),
                 c_lapack_4t=timeit(lambda: rzf_lapack(H, al, P, W2, threads)),
                 fused_1t=timeit(lambda: rzf_chol(H, al, P, W1, 1)),
                 fused_4t=timeit(lambda: rzf_chol(H, al, P, W1, threads)),
                 relerr_fused=err(W1), relerr_lapack=err(W2), relerr_solve=err(np_solve(H, al, P)))
        r["speedup_vs_numpy_solve"] = r["numpy_solve"] / r["fused_4t"]
        r["speedup_vs_c_lapack_4t"] = r["c_lapack_4t"] / r["fused_4t"]
        r["speedup_vs_c_lapack_1t_same_threads"] = r["c_lapack_1t"] / r["fused_1t"]
        rows.append({k: (float('%.4g' % v) if isinstance(v, float) else v) for k, v in r.items()})
        print(rows[-1])
    dump(dict(S=S, threads=threads, nproc=os.cpu_count(), rows=rows), "exp19_strong_timing_baselines")
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    labs = [("numpy_inv", "numpy inv"), ("numpy_solve", "numpy batched solve"),
            ("c_lapack_4t", "C OpenBLAS/LAPACK Cholesky (4 thr)"), ("fused_4t", "fused C kernel (4 thr)")]
    for i, (k, l) in enumerate(labs):
        ax.bar(np.arange(len(rows)) + (i - 1.5) * 0.2, [r[k] for r in rows], 0.2, label=l)
    ax.set_yscale("log"); ax.set_xticks(range(len(rows))); ax.set_xticklabels([f"K={r['K']}\nM={r['M']}" for r in rows])
    ax.axhline(0.5, c="k", ls=":"); ax.text(-0.4, 0.55, "0.5 ms slot", fontsize=7)
    ax.set_ylabel("ms per slot, whole precoder (273 PRBs)"); ax.legend(fontsize=7)
    save(fig, "exp19_strong_timing_baselines")


if __name__ == "__main__":
    main()
