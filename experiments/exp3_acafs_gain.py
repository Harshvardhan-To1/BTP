"""
Experiment 3: ACAFS Fronthaul Load Reduction vs SNR
====================================================
For each SNR, estimate the numerical rank (99 % energy) of the received
matrix for ``--realizations`` channel draws and apply the ACAFS decision rule.
Reports the mean fronthaul-bit saving relative to the *fixed antenna-space
split* (7.1 / 7.2x-A, all M streams) -- see ``src/split/acafs.py`` for the
bandwidth model and why split 6 is the cheapest, not the most expensive, option.

Curves
  * exact rank (Gram eigenvalues, O(M^2 N)), split 6 allowed
  * exact rank, split 6 NOT allowed (pure beam-space stream selection)
  * subsampled-subcarrier rank estimate (1/8 of the subcarriers), split 6 allowed
  * Proposition 5 (expected saving for uniform rank) as a dotted reference

Right panel: split decision distribution at SNR 16-20 dB.

Usage:
  python experiments/exp3_acafs_gain.py [--realizations 20]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from tqdm import tqdm

from experiments._common import plt, save_fig, save_json
from src.channel.tdl_a import ChannelConfig, TDLAChannel, estimate_rank, estimate_rank_fast
from src.split.acafs import ACAFSController

SNR_VALUES = [-5, 0, 5, 10, 15, 16, 17, 18, 19, 20, 25, 30]
TAU_LOW, TAU_HIGH = 0.15, 0.55
M, N = 64, 1200


def run(n_real):
    ctrl6 = ACAFSController(TAU_LOW, TAU_HIGH, M, allow_split6=True)
    ctrl_bs = ACAFSController(TAU_LOW, TAU_HIGH, M, allow_split6=False)
    out = {"snr": SNR_VALUES, "exact_split6": [], "exact_beamspace": [], "fast_split6": [],
           "mean_rank_exact": [], "mean_rank_fast": [], "rank_abs_err": [],
           "t_exact_ms": [], "t_fast_ms": []}
    pie_ranks = []
    for snr in tqdm(SNR_VALUES, desc="SNR"):
        ch = TDLAChannel(ChannelConfig(M=M, N=N, SNR_dB=snr, seed=42))
        _, Y_batch = ch.generate_batch(n_real)
        t0 = time.perf_counter(); r_exact = np.array([estimate_rank(Y) for Y in Y_batch]); t_ex = time.perf_counter() - t0
        t0 = time.perf_counter(); r_fast = np.array([estimate_rank_fast(Y, subsample=8, seed=i) for i, Y in enumerate(Y_batch)]); t_fa = time.perf_counter() - t0
        out["exact_split6"].append(ctrl6.expected_bw_reduction(r_exact))
        out["exact_beamspace"].append(ctrl_bs.expected_bw_reduction(r_exact))
        out["fast_split6"].append(ctrl6.expected_bw_reduction(r_fast))
        out["mean_rank_exact"].append(float(r_exact.mean())); out["mean_rank_fast"].append(float(r_fast.mean()))
        out["rank_abs_err"].append(float(np.abs(r_exact - r_fast).mean()))
        out["t_exact_ms"].append(t_ex / n_real * 1e3); out["t_fast_ms"].append(t_fa / n_real * 1e3)
        if 16 <= snr <= 20:
            pie_ranks.append(r_exact)
    out["prop5_split6"] = ACAFSController.theorem5_bound(M, TAU_LOW, TAU_HIGH, allow_split6=True)
    out["prop5_beamspace"] = ACAFSController.theorem5_bound(M, TAU_LOW, TAU_HIGH, allow_split6=False)
    out["split_distribution_16_20dB"] = ctrl6.split_distribution(np.concatenate(pie_ranks))
    return out


def plot(out, n_real):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.6, 1]})
    s = out["snr"]
    ax1.plot(s, 100 * np.array(out["exact_split6"]), "o-", color="#e74c3c", label="ACAFS, exact rank, split 6 allowed")
    ax1.plot(s, 100 * np.array(out["fast_split6"]), "s--", color="#e67e22", label="ACAFS, 1/8-subcarrier rank est.")
    ax1.plot(s, 100 * np.array(out["exact_beamspace"]), "^-", color="#27ae60", label="ACAFS, beam-space only (no split 6)")
    ax1.axhline(100 * out["prop5_split6"], color="#e74c3c", ls=":", lw=1.4, label=f"Prop. 5, uniform rank, split 6 ({100*out['prop5_split6']:.0f}%)")
    ax1.axhline(100 * out["prop5_beamspace"], color="#27ae60", ls=":", lw=1.4, label=f"Prop. 5, uniform rank, beam-space ({100*out['prop5_beamspace']:.0f}%)")
    ax1.set_xlabel("SNR (dB)"); ax1.set_ylabel("Fronthaul bit saving vs fixed antenna-space split (%)")
    ax1.set_title(f"ACAFS saving vs SNR  (M={M}, N={N}, {n_real} realisations, 99% energy rank)")
    ax1.set_ylim(-5, 105); ax1.legend(loc="center left", fontsize=8)
    ax1b = ax1.twinx()
    ax1b.plot(s, out["mean_rank_exact"], color="grey", lw=1, alpha=0.6)
    ax1b.set_ylabel("mean estimated rank (grey)", color="grey"); ax1b.set_ylim(0, M + 2); ax1b.grid(False)

    dist = out["split_distribution_16_20dB"]
    labels = [f"7.2x beam-space\n({dist['7.2x']*100:.0f}%)", f"7.1 antenna-space\n({dist['7.1']*100:.0f}%)", f"split 6\n({dist['6']*100:.0f}%)"]
    sizes = [max(dist["7.2x"], 1e-6), max(dist["7.1"], 1e-6), max(dist["6"], 1e-6)]
    ax2.pie(sizes, labels=labels, colors=["#27ae60", "#7f8c8d", "#e74c3c"], startangle=90, textprops={"fontsize": 9})
    ax2.set_title("Split decisions, SNR 16-20 dB")
    save_fig(fig, "exp3_acafs")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--realizations", type=int, default=20)
    args = ap.parse_args()
    out = run(args.realizations)
    plot(out, args.realizations)
    save_json("exp3_acafs.json", {"M": M, "N": N, "tau_low": TAU_LOW, "tau_high": TAU_HIGH,
                                  "realizations": args.realizations, **out})
    for i, snr in enumerate(out["snr"]):
        print(f"SNR {snr:>3} dB: rank {out['mean_rank_exact'][i]:5.1f} (fast {out['mean_rank_fast'][i]:5.1f}, "
              f"|err| {out['rank_abs_err'][i]:.2f})  saving split6 {100*out['exact_split6'][i]:5.1f}%  "
              f"beam-space {100*out['exact_beamspace'][i]:5.1f}%  t_exact {out['t_exact_ms'][i]:.2f} ms  t_fast {out['t_fast_ms'][i]:.2f} ms")


if __name__ == "__main__":
    main()
