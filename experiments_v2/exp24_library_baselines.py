"""Exp24: fused C RZF kernel vs optimised library pipelines on the same CPU (S = 273 subcarriers, complex64).

Baselines (kernels/rzf_baselines.cpp), OpenMP over subcarriers like our kernel:
  * OpenBLAS cgemm + LAPACK cposv (Cholesky solve, no explicit inverse)
  * Eigen fixed-size LLT solve
Single-thread and 4-thread numbers are reported separately.
"""
from common import *
import time
from cmatinv.fastkernels import rzf_chol, rzf_library


def timeit(fn, reps=60):
    for _ in range(5): fn()
    t = []
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); t.append(time.perf_counter() - t0)
    return 1e3 * float(np.median(t))


def main(S=273):
    rng = np.random.default_rng(0)
    rows = []
    for K, M in ((8, 64), (16, 64), (32, 64), (16, 128)):
        H = ((rng.standard_normal((S, K, M)) + 1j * rng.standard_normal((S, K, M))) / np.sqrt(2)).astype(np.complex64)
        al, P = K / 10.0, 1.0
        W = np.empty_like(H)
        ref = rzf_chol(H, al, P, threads=1)
        err = {w: float(np.abs(rzf_library(H, al, P, w, threads=1) - ref).max() / np.abs(ref).max())
               for w in ("lapack", "eigen")}
        r = dict(K=K, M=M, rel_err_vs_ours=err)
        for thr in (1, 4):
            r[f"ours_fused_{thr}t"] = timeit(lambda: rzf_chol(H, al, P, W, thr))
            r[f"openblas_lapack_{thr}t"] = timeit(lambda: rzf_library(H, al, P, "lapack", W, thr))
            r[f"eigen_{thr}t"] = timeit(lambda: rzf_library(H, al, P, "eigen", W, thr))
        rows.append(r)
        print(K, M, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k not in ("K", "M")})
    dump(dict(S=S, nproc=os.cpu_count(), rows=rows), "exp24_library_baselines")


if __name__ == "__main__":
    main()
