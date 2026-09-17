"""
Experiment 5: Capacity-Constrained Multi-Cell Fronthaul Allocation
===================================================================
``--cells`` RUs (default 8) with heterogeneous SNR share one fronthaul link.
For each capacity (fraction of the raw 16-bit antenna-space load) the
controller picks one CSEE operating point (K, bits) per cell.  Every cell is
then *actually encoded* at the chosen point and the measured NMSE is reported
(predictions are only used to decide).

Policies
  uniform-CSEE  same (K, bits) for all cells, best that fits           [baseline]
  uniform-BFP   same BFP bit width for all cells (O-RAN static config)  [baseline]
  greedy-sum    marginal-gain allocation on Prop.-1 predicted NMSE      [proposed]
  greedy-max    same, min-max objective (worst cell first)             [proposed]
  oracle        greedy-sum on *measured* NMSE (ablation: prediction error cost)

Scenarios: capacity fractions {0.5 low load, 0.2, 0.1, 0.05 near saturation
of the menu, 0.02, 0.005 overload}, ``--seeds`` independent channel draws; the
per-cell SNRs are a fixed heterogeneous set {0,5,...,30,20} dB.  Reference
symbols are used because CSEE is only valid there (see Experiment 1).

Metrics (all measured unless stated): mean and worst-cell NMSE (dB), link
utilisation = used/capacity, dropped cells, decision time (ms, Python), and
|predicted - measured| NMSE (dB) of the proposed policy.

Usage:
  python experiments/exp5_fronthaul_allocation.py [--cells 8] [--seeds 5]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from tqdm import tqdm

from experiments._common import COLORS, DATA_DIR, MARKERS, plt, save_fig, save_json
from src.channel.tdl_a import ChannelConfig, TDLAChannel
from src.control.allocator import (
    bits_per_symbol_to_gbps,
    build_bfp_menu,
    build_csee_menu,
    greedy_allocate,
    uniform_allocate,
)
from src.encoder.bfp import bfp_decode, bfp_encode
from src.encoder.csee import CSEEEncoder
from src.metrics.nmse import nmse_linear

M, N = 64, 1200
CELL_SNRS = [0, 5, 10, 15, 20, 25, 30, 20]
CAPACITY_FRACS = [0.5, 0.2, 0.1, 0.05, 0.02, 0.005]
CSEE_KS = [24, 40, 60, 90, 120, 200, 300, 450, 600, 900, 1200]
CSEE_BITS = [4, 6, 8, 10, 12, 14]
BFP_BITS = [2, 3, 4, 6, 8, 10, 12, 16]
POLICIES = ["uniform-CSEE", "uniform-BFP", "greedy-sum", "greedy-max", "oracle"]


def measure(menu, res, Y_batch, S_batch):
    """Encode every non-dropped cell at its chosen point; return (nmse_vs_Y, nmse_vs_clean) linear arrays."""
    vy, vc = np.ones(len(Y_batch)), np.ones(len(Y_batch))
    for c in range(len(Y_batch)):
        if res.dropped[c]:
            continue
        p = menu.params[res.choice[c]]
        if menu.name == "CSEE":
            enc = CSEEEncoder(p["K"], p["bits"]); e = enc.encode(Y_batch[c]); Yh = enc.decode(e)
            assert enc.bits_used(e) == menu.rates[res.choice[c]], "rate accounting mismatch"
        else:
            e = bfp_encode(Y_batch[c], bits=p["bits"]); Yh = bfp_decode(e)
        vy[c] = nmse_linear(Y_batch[c], Yh); vc[c] = nmse_linear(S_batch[c], Yh)
    return vy, vc


def run(n_cells, seeds):
    snrs = (CELL_SNRS * ((n_cells + len(CELL_SNRS) - 1) // len(CELL_SNRS)))[:n_cells]
    raw = 2 * M * N * 16 * n_cells
    rows = []
    for seed in tqdm(seeds, desc="seed"):
        Ys, Ss = [], []
        for k, snr in enumerate(snrs):
            ch = TDLAChannel(ChannelConfig(M=M, N=N, SNR_dB=snr, seed=1000 * seed + k))
            Y, S = ch.generate_received_signal(ch.generate_H(), return_clean=True, symbol_type="reference")
            Ys.append(Y); Ss.append(S)
        Y_batch, S_batch = np.stack(Ys), np.stack(Ss)
        csee = build_csee_menu(Y_batch, CSEE_KS, CSEE_BITS)
        bfp = build_bfp_menu(Y_batch, BFP_BITS)
        # Oracle distortions: measure every CSEE option once per cell (expensive; ablation only).
        measured = np.empty_like(csee.predicted)
        for c in range(n_cells):
            for j, p in enumerate(csee.params):
                enc = CSEEEncoder(p["K"], p["bits"]); measured[c, j] = nmse_linear(Y_batch[c], enc.decode(enc.encode(Y_batch[c])))
        for frac in CAPACITY_FRACS:
            C = raw * frac
            runs = {
                "uniform-CSEE": (csee, uniform_allocate(csee.rates, csee.predicted, C)),
                "uniform-BFP": (bfp, uniform_allocate(bfp.rates, bfp.predicted, C)),
                "greedy-sum": (csee, greedy_allocate(csee.rates, csee.predicted, C, "sum")),
                "greedy-max": (csee, greedy_allocate(csee.rates, csee.predicted, C, "max")),
                "oracle": (csee, greedy_allocate(csee.rates, measured, C, "sum")),
            }
            for pol, (menu, res) in runs.items():
                assert res.feasible, f"{pol} violated capacity"
                vy, vc = measure(menu, res, Y_batch, S_batch)
                rows.append({
                    "seed": seed, "capacity_frac": frac, "capacity_gbps": bits_per_symbol_to_gbps(C), "policy": pol,
                    "mean_nmse_db": 10 * np.log10(vy.mean()), "worst_nmse_db": 10 * np.log10(vy.max()),
                    "mean_nmse_clean_db": 10 * np.log10(vc.mean()),
                    "utilization": res.utilization, "dropped": int(res.dropped.sum()),
                    "decision_ms": res.decision_time_s * 1e3 + (menu.prediction_time_s * 1e3 if pol.startswith("greedy") else 0.0),
                    "alloc_only_ms": res.decision_time_s * 1e3,
                    "pred_abs_err_db": float(np.mean(np.abs(10 * np.log10(res.predicted[~res.dropped] + 1e-20)
                                                            - 10 * np.log10(vy[~res.dropped] + 1e-20)))) if (~res.dropped).any() else 0.0,
                    "choices": ";".join(menu.labels[i] if i >= 0 else "DROP" for i in res.choice),
                })
    return pd.DataFrame(rows), snrs, raw


def plot(df, n_cells, n_seeds):
    agg = df.drop(columns=["choices"]).groupby(["policy", "capacity_frac"]).agg(["mean", "std"])
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    cap_gbps = df.groupby("capacity_frac")["capacity_gbps"].first()
    for pol in POLICIES:
        g = agg.loc[pol]
        x = cap_gbps.loc[g.index].values
        kw = dict(color=COLORS[pol], marker=MARKERS[pol], label=pol, capsize=3, lw=1.8)
        axes[0].errorbar(x, g[("mean_nmse_db", "mean")], yerr=g[("mean_nmse_db", "std")], **kw)
        axes[1].errorbar(x, g[("worst_nmse_db", "mean")], yerr=g[("worst_nmse_db", "std")], **kw)
        axes[2].errorbar(x, 100 * g[("utilization", "mean")], yerr=100 * g[("utilization", "std")], **kw)
    for ax, t, yl in zip(axes, ["(a) mean cell NMSE (measured)", "(b) worst cell NMSE (measured)", "(c) link utilisation"],
                         ["NMSE vs Y (dB)", "NMSE vs Y (dB)", "used / capacity (%)"]):
        ax.set_xscale("log"); ax.set_xlabel("shared fronthaul capacity (Gbps)"); ax.set_title(t); ax.set_ylabel(yl)
    axes[2].set_ylim(0, 105); axes[0].legend(fontsize=8)
    fig.suptitle(f"Multi-cell fronthaul allocation: {n_cells} cells, SNR {{{','.join(map(str, CELL_SNRS[:n_cells]))}}} dB, "
                 f"{n_seeds} seeds (mean +- std); dropped cells count as 0 dB", fontsize=11)
    save_fig(fig, "exp5_allocation")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=int, default=8); ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()
    df, snrs, raw = run(args.cells, list(range(args.seeds)))
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(os.path.join(DATA_DIR, "exp5_allocation_runs.csv"), index=False)
    summary = df.drop(columns=["choices"]).groupby(["capacity_frac", "policy"]).agg(["mean", "std"])
    summary.columns = ["_".join(c) for c in summary.columns]
    summary.reset_index().to_csv(os.path.join(DATA_DIR, "exp5_allocation_summary.csv"), index=False)
    plot(df, args.cells, args.seeds)
    save_json("exp5_allocation_config.json", {"cells": args.cells, "cell_snrs_db": snrs, "seeds": args.seeds,
              "raw_bits_per_symbol": raw, "raw_gbps": bits_per_symbol_to_gbps(raw), "capacity_fracs": CAPACITY_FRACS,
              "csee_Ks": CSEE_KS, "csee_bits": CSEE_BITS, "bfp_bits": BFP_BITS})
    pd.set_option("display.width", 200)
    cols = ["mean_nmse_db_mean", "mean_nmse_db_std", "worst_nmse_db_mean", "utilization_mean", "dropped_mean", "decision_ms_mean", "pred_abs_err_db_mean"]
    print(summary[cols].round(2).to_string())


if __name__ == "__main__":
    main()
