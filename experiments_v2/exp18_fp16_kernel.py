"""Exp18: AVX512-FP16 weight-formation kernel -- speed and sum-rate cost vs the float32 kernel."""
from common import *
from cmatinv.fastkernels import rzf_chol, rzf_fp16, HAS_FP16
import time


def timeit(fn, reps=40):
    for _ in range(5): fn()
    t = []
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); t.append(time.perf_counter() - t0)
    return 1e3 * float(np.median(t))


def main(S=273):
    assert HAS_FP16, "needs an AVX512-FP16 CPU"
    acc = {}
    scen = {"K=16, 10 dB": dict(M=64, K=16), "K=16, 30 dB": dict(M=64, K=16, snr_db=30.0),
            "ill-cond (3 deg, 25 dB)": dict(M=64, K=16, angular_spread_deg=3, snr_db=25.0),
            "K=32, 20 dB": dict(M=64, K=32, snr_db=20.0), "K=16, M=128, 30 dB": dict(M=128, K=16, snr_db=30.0)}
    for name, kw in scen.items():
        l32, l16, rates = [], [], []
        for cfg, ch, H, al, rho in drops(10, **kw):
            Hc = H.astype(np.complex64)
            r_ex = rate_with(H, np.linalg.inv(gram(H, al)), rho)
            for f, L in ((rzf_chol, l32), (rzf_fp16, l16)):
                W = f(Hc, np.float32(al), np.float32(rho)).transpose(0, 2, 1).astype(complex)
                L.append(100 * (1 - sum_rate(H, W) / r_ex))
        acc[name] = dict(loss_fp32_pct=float(np.mean(l32)), loss_fp16_pct=float(np.mean(l16)), worst_fp16_pct=float(np.max(l16)))
        print(f"{name:26s} fp32 loss {np.mean(l32):8.5f}%   fp16 loss {np.mean(l16):8.5f}%  (worst drop {np.max(l16):.5f}%)")
    rng = np.random.default_rng(0)
    rows = []
    for K, M in ((8, 64), (16, 64), (32, 64), (16, 128), (32, 128)):
        H = ((rng.standard_normal((S, K, M)) + 1j * rng.standard_normal((S, K, M))) / np.sqrt(2)).astype(np.complex64)
        W = np.empty((S, K, M), np.complex64)
        r = dict(K=K, M=M, fp32_4t=timeit(lambda: rzf_chol(H, K / 10, 10., W, 4)), fp16_4t=timeit(lambda: rzf_fp16(H, K / 10, 10., W, 4)),
                 fp32_1t=timeit(lambda: rzf_chol(H, K / 10, 10., W, 1)), fp16_1t=timeit(lambda: rzf_fp16(H, K / 10, 10., W, 1)))
        r["speedup_4t"] = r["fp32_4t"] / r["fp16_4t"]
        rows.append({k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()}); print(rows[-1])
    dump(dict(sum_rate=acc, timing=rows), "exp18_fp16_kernel")

if __name__ == "__main__":
    main()
