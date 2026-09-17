"""
Experiment 2: Computational Complexity Comparison
==================================================
Paper Figure 2 — Runtime vs matrix size (M × N).

Sweeps M from 8 to 128 (fixed N=1200) and measures wall-clock time
per encode operation for all 4 methods.

Also plots the theoretical complexity curves:
  BFP:     O(MN)
  SVD:     O(MN·min(M,N))
  CSEE:    O(MN log N)
  RAS-BFP: O(MN log r + Nr²)  — SRHT + QR

Usage:
  python experiments/exp2_complexity.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import time
from tqdm import tqdm

from src.encoder.bfp import bfp_encode
from src.encoder.svd_encoder import SVDEncoder
from src.encoder.csee import CSEEEncoder
from src.encoder.ras_bfp import RASBFPEncoder

matplotlib.rcParams.update({
    "font.family": "serif", "font.size": 11,
    "axes.labelsize": 12, "axes.titlesize": 13,
    "legend.fontsize": 10, "figure.dpi": 150,
    "axes.grid": True, "grid.alpha": 0.3, "lines.linewidth": 2.0,
})
COLORS  = {"BFP": "#7f8c8d", "SVD": "#2980b9", "CSEE": "#e74c3c", "RAS-BFP": "#27ae60"}
MARKERS = {"BFP": "s", "SVD": "^", "CSEE": "o", "RAS-BFP": "D"}

N_FIXED  = 1200
M_VALUES = [8, 16, 24, 32, 48, 64, 96, 128]
NUM_REPS = 5    # repetitions per timing measurement


def time_encoder(encoder_fn, Y: np.ndarray, reps: int = 5) -> float:
    """Returns median wall-clock time (seconds) for encoder_fn(Y)."""
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        encoder_fn(Y)
        times.append(time.perf_counter() - t0)
    return float(np.median(times))


def run_experiment():
    rng = np.random.default_rng(0)
    timings = {name: [] for name in ["BFP", "SVD", "CSEE", "RAS-BFP"]}
    r_fixed, K_fixed = 8, 24

    print("Experiment 2: Complexity Timing")
    for M in tqdm(M_VALUES):
        Y = (rng.standard_normal((M, N_FIXED)) +
             1j * rng.standard_normal((M, N_FIXED))) / np.sqrt(2)

        svd_enc   = SVDEncoder(r=r_fixed, bits=10)
        csee_enc  = CSEEEncoder(K=K_fixed, bits=10)
        rasbfp    = RASBFPEncoder(r=r_fixed, bits=10)

        timings["BFP"].append(time_encoder(lambda y=Y: bfp_encode(y, bits=10), Y, NUM_REPS))
        timings["SVD"].append(time_encoder(svd_enc.encode, Y, NUM_REPS))
        timings["CSEE"].append(time_encoder(csee_enc.encode, Y, NUM_REPS))
        timings["RAS-BFP"].append(time_encoder(rasbfp.encode, Y, NUM_REPS))

    return timings


def plot_results(timings, save_path="results/figures/exp2_complexity.pdf"):
    fig, ax = plt.subplots(figsize=(7, 5))
    ms = np.array(M_VALUES)

    for name, times in timings.items():
        ax.semilogy(ms, [t * 1000 for t in times],
                    color=COLORS[name], marker=MARKERS[name], label=name)

    # Theoretical complexity curves (scaled to fit)
    scale_ref = timings["BFP"][0] / (M_VALUES[0] * N_FIXED)
    ax.semilogy(ms, scale_ref * ms * N_FIXED,
                "k:", alpha=0.4, linewidth=1.0, label="O(MN) ref.")

    ax.set_xlabel("Number of Antennas M")
    ax.set_ylabel("Encode Time (ms, log scale)")
    ax.set_title(f"Encoder Complexity vs M  (N={N_FIXED})")
    ax.legend()
    ax.set_xticks(M_VALUES)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    png_path = save_path.replace(".pdf", ".png")
    fig.savefig(png_path, bbox_inches="tight", dpi=300)
    print(f"\n✓ Figure saved to {save_path} and {png_path}")
    plt.close(fig)


if __name__ == "__main__":
    timings = run_experiment()
    plot_results(timings)
