"""
Experiment 1: NMSE vs Compression Ratio
========================================
Rate-distortion frontier of the four encoders on TDL-A received matrices
(M=64, N=1200, SNR=20 dB), averaged over ``--realizations`` channel draws.

Two panels, because the encoders exploit *different* structure:
  (a) data-bearing symbols  (random QPSK on every subcarrier) -- the common case
      on the fronthaul; only structure that survives per-subcarrier modulation
      (spatial low rank, since Y = H diag(X)) can be exploited.
  (b) reference symbols de-rotated by the known sequence (Y = H + W') --
      delay-domain sparsity is visible and CSEE applies.

Dashed lines: Proposition 1 (CSEE, worst-case quantisation) and Theorem 2
(RAS-BFP, Gaussian-sketch reference) evaluated on the same realisations.

Sweeps:
  BFP     bits = 4, 6, 8, 10, 12, 16          (block = 12 REs, 4-bit exponent)
  SVD     r    = 2, 4, 8, 12, 16, 24, 32      (bits = 10)
  CSEE    K    = 24 ... 400                   (bits = 10)
  RAS-BFP r    = 2, 4, 8, 12, 16, 24          (bits = 10, oversample 4, SRHT)

Usage:
  python experiments/exp1_nmse_vs_cr.py [--realizations 30] [--snr 20]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from tqdm import tqdm

from experiments._common import COLORS, MARKERS, plt, save_fig, save_json
from src.channel.tdl_a import ChannelConfig, TDLAChannel
from src.encoder.bfp import bfp_bits_used, bfp_decode, bfp_encode
from src.encoder.csee import CSEEEncoder
from src.encoder.ras_bfp import RASBFPEncoder
from src.encoder.svd_encoder import SVDEncoder
from src.metrics.nmse import compression_ratio, nmse_linear, original_bits

BFP_BITS = [4, 6, 8, 10, 12, 16]
SVD_R = [2, 4, 8, 12, 16, 24, 32]
CSEE_K = [24, 40, 60, 80, 120, 200, 300, 400]
RAS_R = [2, 4, 8, 12, 16, 24]
BITS = 10


def sweep(Y_batch, cfg):
    orig_b = original_bits(cfg.M, cfg.N)
    res = {n: {"cr": [], "nmse_db": [], "param": []} for n in ["BFP", "SVD", "CSEE", "RAS-BFP"]}
    bounds = {"CSEE": {"cr": [], "bound_db": []}, "RAS-BFP": {"cr": [], "bound_db": []}}
    energy = np.array([np.linalg.norm(Y, "fro") ** 2 for Y in Y_batch])

    def record(name, param, lin, crs):
        res[name]["nmse_db"].append(10 * np.log10(np.mean(lin) + 1e-20))
        res[name]["cr"].append(float(np.mean(crs)))
        res[name]["param"].append(param)

    for bits in tqdm(BFP_BITS, desc="BFP "):
        lin, crs = [], []
        for Y in Y_batch:
            enc = bfp_encode(Y, bits=bits)
            lin.append(nmse_linear(Y, bfp_decode(enc))); crs.append(compression_ratio(orig_b, bfp_bits_used(enc)))
        record("BFP", bits, lin, crs)

    for r in tqdm(SVD_R, desc="SVD "):
        enc_obj = SVDEncoder(r=r, bits=BITS)
        lin, crs = [], []
        for Y in Y_batch:
            enc = enc_obj.encode(Y)
            lin.append(nmse_linear(Y, enc_obj.decode(enc))); crs.append(enc_obj.compression_ratio(enc))
        record("SVD", r, lin, crs)

    for K in tqdm(CSEE_K, desc="CSEE"):
        enc_obj = CSEEEncoder(K=K, bits=BITS)
        lin, crs, bnd = [], [], []
        for Y in Y_batch:
            enc = enc_obj.encode(Y)
            lin.append(nmse_linear(Y, enc_obj.decode(enc))); crs.append(enc_obj.compression_ratio(enc))
            bnd.append(CSEEEncoder.theoretical_nmse_bound(Y, K, bits=BITS, worst_case=True))
        record("CSEE", K, lin, crs)
        bounds["CSEE"]["cr"].append(float(np.mean(crs)))
        bounds["CSEE"]["bound_db"].append(10 * np.log10(np.mean(bnd) + 1e-20))

    for r in tqdm(RAS_R, desc="RAS "):
        enc_obj = RASBFPEncoder(r=r, bits=BITS)
        lin, crs, bnd = [], [], []
        for Y, e in zip(Y_batch, energy):
            enc = enc_obj.encode(Y)
            lin.append(nmse_linear(Y, enc_obj.decode(enc))); crs.append(enc_obj.compression_ratio(enc))
            bnd.append(RASBFPEncoder.theoretical_error_bound(Y, r, enc_obj.p) / e)
        record("RAS-BFP", r, lin, crs)
        bounds["RAS-BFP"]["cr"].append(float(np.mean(crs)))
        bounds["RAS-BFP"]["bound_db"].append(10 * np.log10(np.mean(bnd) + 1e-20))
    return res, bounds


def plot(all_results, cfg, n_real):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    titles = {"data": "(a) data symbols: Y = H diag(X) + W", "reference": "(b) reference symbols: Y = H + W'"}
    for ax, (kind, (res, bounds)) in zip(axes, all_results.items()):
        for name, d in res.items():
            ax.plot(d["cr"], d["nmse_db"], color=COLORS[name], marker=MARKERS[name], label=name, zorder=3)
        ax.plot(bounds["CSEE"]["cr"], bounds["CSEE"]["bound_db"], "--", color=COLORS["CSEE"], alpha=0.7,
                label="CSEE Prop. 1 (worst-case)")
        ax.plot(bounds["RAS-BFP"]["cr"], bounds["RAS-BFP"]["bound_db"], "--", color=COLORS["RAS-BFP"], alpha=0.7,
                label="RAS-BFP Thm. 2 (Gaussian ref.)")
        ax.axhline(-cfg.SNR_dB, color="k", ls=":", lw=1, alpha=0.6)
        ax.text(1.05, -cfg.SNR_dB + 1.5, "noise floor (-SNR)", fontsize=8, alpha=0.7)
        ax.set_xscale("log")
        ax.set_xlabel("Compression ratio vs 16-bit I/Q (higher = fewer bits)")
        ax.set_title(titles[kind])
    axes[0].set_ylabel("NMSE vs transported Y (dB)")
    axes[0].legend(loc="lower left")
    fig.suptitle(f"NMSE vs compression ratio  (M={cfg.M}, N={cfg.N}, SNR={cfg.SNR_dB:g} dB, TDL-A, "
                 f"{n_real} realisations)", fontsize=12)
    save_fig(fig, "exp1_nmse_vs_cr")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--realizations", type=int, default=30)
    ap.add_argument("--snr", type=float, default=20.0)
    args = ap.parse_args()
    cfg = ChannelConfig(M=64, N=1200, SNR_dB=args.snr, seed=42)
    channel = TDLAChannel(cfg)
    all_results = {}
    for kind in ("data", "reference"):
        print(f"=== Experiment 1 [{kind} symbols], {args.realizations} realisations, SNR {args.snr} dB ===")
        _, Y_batch = channel.generate_batch(args.realizations, symbol_type=kind)
        all_results[kind] = sweep(Y_batch, cfg)
    plot(all_results, cfg, args.realizations)
    save_json("exp1_nmse_vs_cr.json", {
        "config": vars(cfg), "realizations": args.realizations, "bits": BITS,
        "results": {k: {"curves": v[0], "bounds": v[1]} for k, v in all_results.items()},
    })
    for kind, (res, _) in all_results.items():
        print(f"[{kind}] " + " | ".join(
            f"{n}: CR {res[n]['cr'][i]:.1f} -> {res[n]['nmse_db'][i]:.1f} dB"
            for n, i in (("BFP", 2), ("SVD", 3), ("CSEE", 1), ("RAS-BFP", 3))))


if __name__ == "__main__":
    main()
