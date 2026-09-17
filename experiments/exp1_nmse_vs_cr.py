"""
Experiment 1: NMSE vs Compression Ratio
========================================
Main comparison plot for the paper (Figure 1).

Sweeps compression parameters for all encoders and plots:
  NMSE (dB) vs Compression Ratio (CR)

Encoders compared:
  - BFP baseline (sweep: bits = 4, 6, 8, 10, 12, 16)
  - SVD baseline (sweep: r = 2, 4, 8, 12, 16, 24, 32)
  - CSEE proposed (sweep: K = 10, 15, 20, 30, 40, 60)
  - RAS-BFP proposed (sweep: r = 2, 4, 8, 12, 16, 24)

Also plots:
  - Theorem 1 NMSE bound for CSEE (dashed)
  - Theorem 2 bound for RAS-BFP (dashed)

Usage:
  python experiments/exp1_nmse_vs_cr.py
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
from src.metrics.nmse import nmse, nmse_linear, compression_ratio, original_bits

# ── Plot style ──────────────────────────────────────────────────────
matplotlib.rcParams.update({
    "font.family":       "serif",
    "font.size":         11,
    "axes.labelsize":    12,
    "axes.titlesize":    13,
    "legend.fontsize":   10,
    "xtick.labelsize":   10,
    "ytick.labelsize":   10,
    "figure.dpi":        150,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "lines.linewidth":   2.0,
    "lines.markersize":  6,
})
COLORS = {
    "BFP":      "#7f8c8d",
    "SVD":      "#2980b9",
    "CSEE":     "#e74c3c",
    "RAS-BFP":  "#27ae60",
}
MARKERS = {"BFP": "s", "SVD": "^", "CSEE": "o", "RAS-BFP": "D"}


def run_experiment(num_realizations: int = 50, snr_db: float = 20.0):
    """Run the full NMSE vs CR sweep."""

    print("=" * 60)
    print("Experiment 1: NMSE vs Compression Ratio")
    print(f"  Realizations: {num_realizations}  |  SNR: {snr_db} dB")
    print("=" * 60)

    # ── Channel setup ────────────────────────────────────────────────
    cfg     = ChannelConfig(M=64, N=1200, SNR_dB=snr_db, seed=42)
    channel = TDLAChannel(cfg)
    _, Y_batch = channel.generate_batch(num_realizations)

    orig_b = original_bits(cfg.M, cfg.N)

    results = {name: {"cr": [], "nmse": []} for name in ["BFP", "SVD", "CSEE", "RAS-BFP"]}
    bound_results = {"CSEE": {"cr": [], "bound": []}, "RAS-BFP": {"cr": [], "bound": []}}

    # ── BFP sweep ────────────────────────────────────────────────────
    print("\n[1/4] BFP sweep...")
    for bits in tqdm([4, 6, 8, 10, 12, 16]):
        nmse_vals, cr_vals = [], []
        for Y in Y_batch:
            enc   = bfp_encode(Y, bits=bits, block_size=16)
            Y_hat = bfp_decode(enc)
            bu    = bfp_bits_used(enc)
            nmse_vals.append(nmse(Y, Y_hat))
            cr_vals.append(compression_ratio(orig_b, bu))
        results["BFP"]["nmse"].append(np.mean(nmse_vals))
        results["BFP"]["cr"].append(np.mean(cr_vals))

    # ── SVD sweep ────────────────────────────────────────────────────
    print("[2/4] SVD sweep...")
    for r in tqdm([2, 4, 8, 12, 16, 24, 32]):
        nmse_vals, cr_vals = [], []
        enc_obj = SVDEncoder(r=r, bits=10)
        for Y in Y_batch:
            enc   = enc_obj.encode(Y)
            Y_hat = enc_obj.decode(enc)
            bu    = enc_obj.bits_used(enc)
            nmse_vals.append(nmse(Y, Y_hat))
            cr_vals.append(compression_ratio(orig_b, bu))
        results["SVD"]["nmse"].append(np.mean(nmse_vals))
        results["SVD"]["cr"].append(np.mean(cr_vals))

    # ── CSEE sweep ───────────────────────────────────────────────────
    print("[3/4] CSEE sweep...")
    for K in tqdm([24, 40, 60, 80, 120, 200, 300, 400]):
        nmse_vals, cr_vals, bounds = [], [], []
        enc_obj = CSEEEncoder(K=K, bits=10)
        for Y in Y_batch:
            enc   = enc_obj.encode(Y)
            Y_hat = enc_obj.decode(enc)
            bu    = enc_obj.bits_used(enc)
            nmse_vals.append(nmse(Y, Y_hat))
            cr_vals.append(compression_ratio(orig_b, bu))
            bounds.append(CSEEEncoder.theoretical_nmse_bound(Y, K, bits=10))
        results["CSEE"]["nmse"].append(np.mean(nmse_vals))
        results["CSEE"]["cr"].append(np.mean(cr_vals))
        bound_results["CSEE"]["cr"].append(np.mean(cr_vals))
        bound_results["CSEE"]["bound"].append(10 * np.log10(np.mean(bounds) + 1e-20))

    # ── RAS-BFP sweep ────────────────────────────────────────────────
    print("[4/4] RAS-BFP sweep...")
    for r in tqdm([2, 4, 8, 12, 16, 24]):
        nmse_vals, cr_vals, bounds = [], [], []
        enc_obj = RASBFPEncoder(r=r, bits=10)
        for Y in Y_batch:
            enc   = enc_obj.encode(Y)
            Y_hat = enc_obj.decode(enc)
            bu    = enc_obj.bits_used(enc)
            nmse_vals.append(nmse(Y, Y_hat))
            cr_vals.append(compression_ratio(orig_b, bu))
            bounds.append(RASBFPEncoder.theoretical_error_bound(Y, r))
        results["RAS-BFP"]["nmse"].append(np.mean(nmse_vals))
        results["RAS-BFP"]["cr"].append(np.mean(cr_vals))
        bound_results["RAS-BFP"]["cr"].append(np.mean(cr_vals))
        # Normalise bound by ||Y||_F² averaged across realizations
        norm_bound = np.mean(bounds) / np.mean([np.linalg.norm(Y, 'fro')**2 for Y in Y_batch])
        bound_results["RAS-BFP"]["bound"].append(10 * np.log10(norm_bound + 1e-20))

    return results, bound_results, cfg


def plot_results(results, bound_results, cfg, save_path="results/figures/exp1_nmse_vs_cr.pdf"):
    """Generate the paper-quality NMSE vs CR plot."""

    fig, ax = plt.subplots(figsize=(7, 5))

    for name, data in results.items():
        ax.plot(data["cr"], data["nmse"],
                color=COLORS[name], marker=MARKERS[name],
                label=name, zorder=3)

    # Theoretical bounds (dashed)
    ax.plot(bound_results["CSEE"]["cr"], bound_results["CSEE"]["bound"],
            color=COLORS["CSEE"], linestyle="--", alpha=0.6,
            label="CSEE Thm. 1 bound", zorder=2)
    ax.plot(bound_results["RAS-BFP"]["cr"], bound_results["RAS-BFP"]["bound"],
            color=COLORS["RAS-BFP"], linestyle="--", alpha=0.6,
            label="RAS-BFP Thm. 2 bound", zorder=2)

    ax.set_xlabel("Compression Ratio (CR)")
    ax.set_ylabel("NMSE (dB)")
    ax.set_title(f"NMSE vs Compression Ratio\n"
                 f"(M={cfg.M}, N={cfg.N}, SNR={cfg.SNR_dB} dB, 3GPP TDL-A)")
    ax.legend(ncol=2, loc="upper right")
    ax.invert_xaxis()   # Higher CR = more compression (right → left for dB curves)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    png_path = save_path.replace(".pdf", ".png")
    fig.savefig(png_path, bbox_inches="tight", dpi=300)
    print(f"\n✓ Figure saved to {save_path} and {png_path}")
    plt.close(fig)


if __name__ == "__main__":
    results, bounds, cfg = run_experiment(num_realizations=30, snr_db=20.0)
    plot_results(results, bounds, cfg)
