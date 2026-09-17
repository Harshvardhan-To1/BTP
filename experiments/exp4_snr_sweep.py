"""
Experiment 4: SNR Robustness Sweep
====================================
Paper Figure 4 — NMSE vs SNR at fixed CR for all methods.

Shows that CSEE and RAS-BFP are robust across the operating SNR range
(unlike BFP which degrades at low SNR when the block exponent is poorly set).

Usage:
  python experiments/exp4_snr_sweep.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from tqdm import tqdm

from src.channel.tdl_a import TDLAChannel, ChannelConfig
from src.encoder.bfp import bfp_encode, bfp_decode, bfp_bits_used
from src.encoder.svd_encoder import SVDEncoder
from src.encoder.csee import CSEEEncoder
from src.encoder.ras_bfp import RASBFPEncoder
from src.metrics.nmse import nmse

matplotlib.rcParams.update({
    "font.family": "serif", "font.size": 11,
    "axes.labelsize": 12, "axes.titlesize": 13,
    "legend.fontsize": 10, "figure.dpi": 150,
    "axes.grid": True, "grid.alpha": 0.3, "lines.linewidth": 2.0,
})
COLORS  = {"BFP": "#7f8c8d", "SVD": "#2980b9", "CSEE": "#e74c3c", "RAS-BFP": "#27ae60"}
MARKERS = {"BFP": "s",       "SVD": "^",       "CSEE": "o",       "RAS-BFP": "D"}

SNR_VALUES       = [-5, 0, 5, 10, 15, 20, 25, 30]
NUM_REALIZATIONS = 12

# Fixed parameters giving roughly similar CR ~12–16x for fair comparison
BFP_BITS  = 8
SVD_RANK  = 12
CSEE_K    = 300
RASBFP_R  = 12


def run_experiment():
    results = {name: [] for name in ["BFP", "SVD", "CSEE", "RAS-BFP"]}

    svd_enc  = SVDEncoder(r=SVD_RANK, bits=10)
    csee_enc = CSEEEncoder(K=CSEE_K, bits=10)
    ras_enc  = RASBFPEncoder(r=RASBFP_R, bits=10)

    print("Experiment 4: SNR Robustness Sweep")
    for snr in tqdm(SNR_VALUES):
        cfg     = ChannelConfig(M=64, N=1200, SNR_dB=snr, seed=42)
        channel = TDLAChannel(cfg)
        _, Y_batch = channel.generate_batch(NUM_REALIZATIONS)

        nmse_bfp, nmse_svd, nmse_csee, nmse_ras = [], [], [], []
        for Y in Y_batch:
            # BFP
            enc = bfp_encode(Y, bits=BFP_BITS); nmse_bfp.append(nmse(Y, bfp_decode(enc)))
            # SVD
            enc = svd_enc.encode(Y); nmse_svd.append(nmse(Y, svd_enc.decode(enc)))
            # CSEE
            enc = csee_enc.encode(Y); nmse_csee.append(nmse(Y, csee_enc.decode(enc)))
            # RAS-BFP
            enc = ras_enc.encode(Y); nmse_ras.append(nmse(Y, ras_enc.decode(enc)))

        results["BFP"].append(np.mean(nmse_bfp))
        results["SVD"].append(np.mean(nmse_svd))
        results["CSEE"].append(np.mean(nmse_csee))
        results["RAS-BFP"].append(np.mean(nmse_ras))

    return results


def plot_results(results, save_path="results/figures/exp4_snr_sweep.pdf"):
    fig, ax = plt.subplots(figsize=(7, 5))

    for name, nmse_list in results.items():
        ax.plot(SNR_VALUES, nmse_list,
                color=COLORS[name], marker=MARKERS[name], label=name)

    ax.set_xlabel("SNR (dB)")
    ax.set_ylabel("NMSE (dB)")
    ax.set_title("NMSE vs SNR at Fixed Compression\n"
                 f"(BFP b={BFP_BITS}, r={SVD_RANK}/{RASBFP_R}, K={CSEE_K})")
    ax.legend()
    ax.set_xticks(SNR_VALUES)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    png_path = save_path.replace(".pdf", ".png")
    fig.savefig(png_path, bbox_inches="tight", dpi=300)
    print(f"\n✓ Figure saved to {save_path} and {png_path}")
    plt.close(fig)


if __name__ == "__main__":
    results = run_experiment()
    plot_results(results)
