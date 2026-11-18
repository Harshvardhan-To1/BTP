"""Exp20: full-band encode time per slot (273 PRBs, M = 64, K = 8, complex64), 1 and 4 threads.

numpy reference encoders vs the C/OpenMP kernels (kernels/iq_kernels.c). "25 % refresh" is the C pilot
encoder with a quarter of the PRBs recomputing their basis, the regime the certificate reaches at
pedestrian speed (Exp21).
"""
from common import *
import time
from threadpoolctl import threadpool_limits
from iqcomp.uplink import UplinkConfig, make_slot
from iqcomp.codecs import bfp, svd_code, pilot_code, mp_rank, dmrs_columns
from iqcomp import fastcodec as fc


def timeit(f, reps=15):
    f()
    t = []
    for _ in range(reps):
        t0 = time.perf_counter(); f(); t.append(time.perf_counter() - t0)
    return 1e3 * float(np.median(t))


def main():
    s = make_slot(UplinkConfig(n_prb=273, K=8, snr_db=20, seed=3))
    Y = s["Y"].astype(np.complex64)
    P = Y.shape[0]
    pil = dmrs_columns()
    _, _, _, _, _, st = fc.pilot_encode(Y, pil)
    quarter = (np.arange(P) % 4) == 0
    res = {}
    for thr in (1, 4):
        meths = {
            "numpy O-RAN BFP (b=9)": lambda: bfp(Y, 9),
            "numpy PCA / exact SVD + RMT rank": lambda: svd_code(Y, mp_rank(Y), 8, 8),
            "numpy RAS-BFP pilot sketch": lambda: pilot_code(Y, 8, 8, pil),
            "C O-RAN BFP (b=9)": lambda: fc.bfp(Y, 9, threads=thr),
            "C RAS-BFP pilot sketch, full refresh": lambda: fc.pilot_encode(Y, pil, threads=thr),
            "C RAS-BFP pilot sketch, 25 % refresh": lambda: fc.pilot_encode(
                Y, pil, threads=thr, refresh=quarter, state=tuple(a.copy() for a in st)),
        }
        with threadpool_limits(thr):
            for name, f in meths.items():
                res[f"{name} | {thr} thr"] = timeit(f)
                print(f"{name:40s} {thr} thr: {res[f'{name} | {thr} thr']:8.2f} ms / slot")
    r = st[1].mean()
    res["projection_gflop_per_slot"] = 8 * P * r * 64 * 168 / 1e9
    print(f"projection L = Q^H Y: {res['projection_gflop_per_slot']:.2f} GFLOP per slot (mean rank {r:.1f})")
    dump(res, "exp20_iq_encode_time")


if __name__ == "__main__":
    main()
