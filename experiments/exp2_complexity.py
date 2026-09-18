"""
Experiment 2: Encoder Runtime vs Number of Antennas
====================================================
Median wall-clock encode time (Python/numpy, single process) for M in
{8,...,128} at fixed N=1200, plus an O(MN) reference line anchored at BFP's
M=8 timing.  Timings are for the *reference implementation*, not a real-time
DU/RU; they establish relative scaling, not deployable latencies.

Fixes relative to the earlier repository figure: the SVD baseline now uses
the economy SVD (``full_matrices=False``), and the O(MN) reference line is
plotted in the same units (ms) as the measurements.

Usage:
  python experiments/exp2_complexity.py [--reps 7]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from tqdm import tqdm

from experiments._common import COLORS, MARKERS, plt, save_fig, save_json
from src.encoder.bfp import bfp_encode
from src.encoder.csee import CSEEEncoder
from src.encoder.ras_bfp import RASBFPEncoder
from src.encoder.svd_encoder import SVDEncoder

N_FIXED = 1200
M_VALUES = [8, 16, 24, 32, 48, 64, 96, 128]
R_FIXED, K_FIXED = 12, 120


def time_fn(fn, reps):
    fn()                                   # warm-up
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
    return float(np.median(ts)) * 1e3, float(np.percentile(ts, 95)) * 1e3


def run(reps):
    rng = np.random.default_rng(0)
    timings = {n: {"median_ms": [], "p95_ms": []} for n in ["BFP", "SVD", "CSEE", "RAS-BFP"]}
    for M in tqdm(M_VALUES, desc="M"):
        Y = (rng.standard_normal((M, N_FIXED)) + 1j * rng.standard_normal((M, N_FIXED))) / np.sqrt(2)
        fns = {
            "BFP": lambda: bfp_encode(Y, bits=10),
            "SVD": SVDEncoder(r=R_FIXED, bits=10).encode,
            "CSEE": CSEEEncoder(K=K_FIXED, bits=10).encode,
            "RAS-BFP": RASBFPEncoder(r=R_FIXED, bits=10).encode,
        }
        for name, f in fns.items():
            med, p95 = time_fn((lambda f=f: f(Y)) if name != "BFP" else f, reps)
            timings[name]["median_ms"].append(med); timings[name]["p95_ms"].append(p95)
    return timings


def plot(timings, reps):
    fig, ax = plt.subplots(figsize=(7, 4.8))
    ms = np.array(M_VALUES, dtype=float)
    for name, t in timings.items():
        ax.semilogy(ms, t["median_ms"], color=COLORS[name], marker=MARKERS[name], label=name)
    ref = timings["BFP"]["median_ms"][0] * ms / ms[0]
    ax.semilogy(ms, ref, "k:", lw=1, alpha=0.6, label="O(MN) ref. (anchored at BFP, M=8)")
    ax.set_xlabel("Number of antennas M"); ax.set_ylabel("Median encode time (ms, log)")
    ax.set_title(f"Encoder runtime vs M  (N={N_FIXED}, r={R_FIXED}, K={K_FIXED}, {reps} reps, numpy)")
    ax.set_xticks(M_VALUES); ax.legend()
    save_fig(fig, "exp2_complexity")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=7)
    args = ap.parse_args()
    timings = run(args.reps)
    plot(timings, args.reps)
    save_json("exp2_complexity.json", {"M": M_VALUES, "N": N_FIXED, "r": R_FIXED, "K": K_FIXED,
                                       "reps": args.reps, "timings_ms": timings})
    i = M_VALUES.index(64)
    print("M=64 median ms: " + ", ".join(f"{n}={t['median_ms'][i]:.2f}" for n, t in timings.items()))


if __name__ == "__main__":
    main()
