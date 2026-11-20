"""Experiment 5: link-level effect of compressing the reference-symbol IQ (sum-rate, not NMSE).

K users each send a reference symbol; the RU de-rotates it and ships Y_k = H_k + W_k (M x N) over the
fronthaul, compressed by each encoder. The DU decompresses, uses Y_hat_k as the channel estimate of
user k, and builds per subcarrier
  * an uplink MMSE combiner   V = (Hh Hh^H + s2 I)^-1 Hh
  * a downlink RZF precoder   W = Hh (Hh^H Hh + K s2 / P I)^-1, total power P
Rates are evaluated on the TRUE channel. "uncompressed" uses Y_k itself (16-bit I/Q, CR = 1).
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np

from src.channel.tdl_a import TDLAChannel, ChannelConfig
from src.encoder.bfp import bfp_encode, bfp_decode, bfp_bits_used
from src.encoder.svd_encoder import SVDEncoder
from src.encoder.csee import CSEEEncoder
from src.encoder.ras_bfp import RASBFPEncoder
from src.metrics.nmse import original_bits

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "link_level")


def _bfp(bits):
    def f(Y):
        e = bfp_encode(Y, bits=bits, block_size=16)
        return bfp_decode(e), bfp_bits_used(e)
    return f


def _obj(enc):
    def f(Y):
        e = enc.encode(Y)
        return enc.decode(e), enc.bits_used(e)
    return f


METHODS = {
    "uncompressed (16-bit)": lambda Y: (Y, None),
    "BFP-8 (O-RAN)": _bfp(8),
    "SVD r=12": _obj(SVDEncoder(r=12, bits=10)),
    "CSEE K=300": _obj(CSEEEncoder(K=300, bits=10)),
    "RAS-BFP r=12": _obj(RASBFPEncoder(r=12, bits=10)),
    "CSEE K=60": _obj(CSEEEncoder(K=60, bits=10)),
    "RAS-BFP r=16": _obj(RASBFPEncoder(r=16, bits=10)),
    "RAS-BFP r=24": _obj(RASBFPEncoder(r=24, bits=10)),
    "uncompressed + DU delay denoising K=60": lambda Y: (CSEEEncoder(K=60, bits=16).decode(CSEEEncoder(K=60, bits=16).encode(Y)), None),
    "uncompressed + DU delay denoising K=300": lambda Y: (CSEEEncoder(K=300, bits=16).decode(CSEEEncoder(K=300, bits=16).encode(Y)), None),
}


def ul_mmse_rate(H, Hh, s2):
    """H, Hh: [N, M, K]. Sum over users of log2(1 + SINR), averaged over subcarriers."""
    M = H.shape[1]
    A = Hh @ np.conj(np.swapaxes(Hh, 1, 2)) + s2 * np.eye(M)
    V = np.linalg.solve(A, Hh)                                  # [N, M, K]
    G = np.conj(np.swapaxes(V, 1, 2)) @ H                       # [N, K, K]  v_k^H h_j
    p = np.abs(G) ** 2
    sig = np.diagonal(p, axis1=1, axis2=2)
    den = p.sum(2) - sig + s2 * np.sum(np.abs(V) ** 2, axis=1)
    return float(np.mean(np.sum(np.log2(1 + sig / den), axis=1)))


def dl_rzf_rate(H, Hh, s2, P=1.0):
    K = H.shape[2]
    A = np.conj(np.swapaxes(Hh, 1, 2)) @ Hh + K * s2 / P * np.eye(K)
    W = Hh @ np.linalg.inv(A)                                   # [N, M, K]
    W *= np.sqrt(P / np.sum(np.abs(W) ** 2, axis=(1, 2), keepdims=True))
    G = np.conj(np.swapaxes(H, 1, 2)) @ W                       # [N, K, K]  h_k^H w_j
    p = np.abs(G) ** 2
    sig = np.diagonal(p, axis1=1, axis2=2)
    den = p.sum(2) - sig + s2
    return float(np.mean(np.sum(np.log2(1 + sig / den), axis=1)))


def main(drops=20, K=8, M=64, N=1200, est_snr_db=20.0, data_snrs=(0.0, 10.0, 20.0), sub=4):
    os.makedirs(OUT, exist_ok=True)
    acc = {m: {"ul": {s: [] for s in data_snrs}, "dl": {s: [] for s in data_snrs}, "cr": [], "nmse_true": []}
           for m in ["perfect CSI"] + list(METHODS)}
    ob = original_bits(M, N)
    for d in range(drops):
        users = []
        for k in range(K):
            ch = TDLAChannel(ChannelConfig(M=M, N=N, SNR_dB=est_snr_db, seed=1000 * d + 17 * k + 3))
            H = ch.generate_H(0)
            Y = ch.generate_received_signal(H, 0, symbol_type="reference")
            users.append((H, Y))
        Htrue = np.stack([u[0] for u in users], axis=2)[:, ::sub, :].transpose(1, 0, 2)   # [N', M, K]
        ests = {"perfect CSI": Htrue}
        for name, f in METHODS.items():
            dec = []
            for H, Y in users:
                Yh, bits = f(Y)
                dec.append(Yh)
                acc[name]["cr"].append(1.0 if bits is None else ob / bits)
                acc[name]["nmse_true"].append(np.sum(np.abs(Yh - H) ** 2) / np.sum(np.abs(H) ** 2))
            ests[name] = np.stack(dec, axis=2)[:, ::sub, :].transpose(1, 0, 2)
        for name, Hh in ests.items():
            for s in data_snrs:
                s2 = 10 ** (-s / 10)
                acc[name]["ul"][s].append(ul_mmse_rate(Htrue, Hh, s2))
                acc[name]["dl"][s].append(dl_rzf_rate(Htrue, Hh, s2))
        print(f"drop {d + 1}/{drops}", flush=True)
    ref = "uncompressed (16-bit)"
    summary = {}
    for name, a in acc.items():
        row = {"compression_ratio": float(np.mean(a["cr"])) if a["cr"] else None,
               "nmse_vs_true_H_db": float(10 * np.log10(np.mean(a["nmse_true"]))) if a["nmse_true"] else None}
        for link in ("ul", "dl"):
            for s in data_snrs:
                x, r = np.array(a[link][s]), np.array(acc[ref][link][s])
                rel = x / r - 1
                row[f"{link}_{s:g}dB_bps_hz"] = float(x.mean())
                row[f"{link}_{s:g}dB_vs_uncompressed_pct"] = float(100 * rel.mean())
                row[f"{link}_{s:g}dB_ci95_pct"] = float(196 * rel.std(ddof=1) / np.sqrt(len(rel)))
        summary[name] = row
    json.dump(dict(config=dict(drops=drops, K=K, M=M, N=N, est_snr_db=est_snr_db, subcarrier_step=sub),
                   results=summary), open(os.path.join(OUT, "exp5_link_level.json"), "w"), indent=1)
    for name, row in summary.items():
        print(f"{name:22s} CR={row['compression_ratio'] or 0:5.1f}  NMSE(H)={row['nmse_vs_true_H_db'] or -99:6.1f} dB  " +
              "  ".join(f"{l.upper()}@{s:g}dB {row[f'{l}_{s:g}dB_bps_hz']:.2f} ({row[f'{l}_{s:g}dB_vs_uncompressed_pct']:+.2f}%)"
                        for l in ("ul", "dl") for s in data_snrs))


if __name__ == "__main__":
    main()
