"""
Experiment 4: NMSE vs SNR at Fixed Operating Points
====================================================
Operating points chosen for a compression ratio of ~8x (BFP cannot reach that
with 16-bit reference, so b=4 at CR 3.8x is the closest):
  BFP b=4 | SVD r=12, b=10 | CSEE K=120, b=10 | RAS-BFP r=12, b=10

Two panels on *reference* symbols (Y = H + W', where all four encoders apply):
  (a) NMSE against the transported (noisy) Y      -- what the link sees
  (b) NMSE against the noiseless channel H       -- what was actually lost
CSEE on *data* symbols is added to (a) as a dashed line to show that its
delay-domain assumption breaks under per-subcarrier modulation.

The earlier repository text described the encoders as "stable across SNR";
panel (a) shows the opposite -- truncating encoders track the noise floor
(-SNR dB) because discarded noise counts as error -- while panel (b) shows the
signal distortion is roughly flat or improves.

Usage:
  python experiments/exp4_snr_sweep.py [--realizations 12]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from tqdm import tqdm

from experiments._common import COLORS, MARKERS, plt, save_fig, save_json
from src.channel.tdl_a import ChannelConfig, TDLAChannel
from src.encoder.bfp import bfp_decode, bfp_encode
from src.encoder.csee import CSEEEncoder
from src.encoder.ras_bfp import RASBFPEncoder
from src.encoder.svd_encoder import SVDEncoder
from src.metrics.nmse import nmse_linear

SNR_VALUES = [-5, 0, 5, 10, 15, 20, 25, 30]
BFP_BITS, SVD_R, CSEE_K, RAS_R, BITS = 4, 12, 120, 12, 10


def run(n_real):
    enc = {"SVD": SVDEncoder(SVD_R, BITS), "CSEE": CSEEEncoder(CSEE_K, BITS), "RAS-BFP": RASBFPEncoder(RAS_R, BITS)}
    out = {"snr": SNR_VALUES, "vs_Y": {k: [] for k in ["BFP", "SVD", "CSEE", "RAS-BFP"]},
           "vs_clean": {k: [] for k in ["BFP", "SVD", "CSEE", "RAS-BFP"]}, "csee_data_vs_Y": [], "cr": {}}
    for snr in tqdm(SNR_VALUES, desc="SNR"):
        ch = TDLAChannel(ChannelConfig(M=64, N=1200, SNR_dB=snr, seed=42))
        _, Y_ref, S_ref = ch.generate_batch(n_real, return_clean=True, symbol_type="reference")
        _, Y_dat = ch.generate_batch(n_real, symbol_type="data")
        acc = {k: [] for k in out["vs_Y"]}; accc = {k: [] for k in out["vs_Y"]}; acc_d = []
        for Y, S, Yd in zip(Y_ref, S_ref, Y_dat):
            Yh = bfp_decode(bfp_encode(Y, bits=BFP_BITS)); acc["BFP"].append(nmse_linear(Y, Yh)); accc["BFP"].append(nmse_linear(S, Yh))
            for k, e in enc.items():
                c = e.encode(Y); Yh = e.decode(c); acc[k].append(nmse_linear(Y, Yh)); accc[k].append(nmse_linear(S, Yh))
                if snr == SNR_VALUES[0]:
                    out["cr"][k] = e.compression_ratio(c)
            c = enc["CSEE"].encode(Yd); acc_d.append(nmse_linear(Yd, enc["CSEE"].decode(c)))
        for k in acc:
            out["vs_Y"][k].append(10 * np.log10(np.mean(acc[k]))); out["vs_clean"][k].append(10 * np.log10(np.mean(accc[k])))
        out["csee_data_vs_Y"].append(10 * np.log10(np.mean(acc_d)))
    from src.encoder.bfp import bfp_bits_used
    from src.metrics.nmse import compression_ratio, original_bits
    out["cr"]["BFP"] = compression_ratio(original_bits(64, 1200), bfp_bits_used(bfp_encode(Y_ref[0], bits=BFP_BITS)))
    return out


def plot(out, n_real):
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    s = out["snr"]
    for k in out["vs_Y"]:
        lab = f"{k} (CR {out['cr'][k]:.1f}x)"
        a.plot(s, out["vs_Y"][k], color=COLORS[k], marker=MARKERS[k], label=lab)
        b.plot(s, out["vs_clean"][k], color=COLORS[k], marker=MARKERS[k], label=lab)
    a.plot(s, out["csee_data_vs_Y"], "--", color=COLORS["CSEE"], marker="x", alpha=0.8, label="CSEE on data symbols")
    a.plot(s, [-x for x in s], "k:", lw=1, alpha=0.6, label="noise floor (-SNR)")
    b.plot(s, [-x for x in s], "k:", lw=1, alpha=0.6, label="raw noisy Y (no compression)")
    a.set_title("(a) NMSE vs transported Y (reference symbols)"); b.set_title("(b) NMSE vs noiseless channel H")
    for ax in (a, b):
        ax.set_xlabel("SNR (dB)"); ax.set_xticks(s); ax.legend(fontsize=8, loc="lower left")
    a.set_ylabel("NMSE (dB)")
    fig.suptitle(f"NMSE vs SNR at fixed operating points  (M=64, N=1200, {n_real} realisations; "
                 f"BFP b={BFP_BITS}, SVD/RAS r={SVD_R}, CSEE K={CSEE_K}, b={BITS})", fontsize=11)
    save_fig(fig, "exp4_snr_sweep")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--realizations", type=int, default=12)
    args = ap.parse_args()
    out = run(args.realizations)
    plot(out, args.realizations)
    save_json("exp4_snr_sweep.json", {"realizations": args.realizations, "operating_points":
              {"BFP_bits": BFP_BITS, "SVD_r": SVD_R, "CSEE_K": CSEE_K, "RAS_r": RAS_R, "bits": BITS}, **out})
    for i, snr in enumerate(s := out["snr"]):
        print(f"SNR {snr:>3}: " + "  ".join(f"{k} {out['vs_Y'][k][i]:6.1f}/{out['vs_clean'][k][i]:6.1f}" for k in out["vs_Y"])
              + f"  CSEE-data {out['csee_data_vs_Y'][i]:6.1f}   [vs Y / vs H, dB]")


if __name__ == "__main__":
    main()
