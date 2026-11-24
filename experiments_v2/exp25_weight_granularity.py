"""Exp25: frequency granularity of RU-side beamforming weights, evaluated on *every* subcarrier.

Exp10 computed one weight per 3-PRB group but scored it only at the subcarrier it was computed on, so
the loss from applying one weight across a whole group was not measured. Here a 24-PRB sub-band
(288 subcarriers at 30 kHz, TDL-A with 30 / 100 / 300 ns delay spread) is simulated at full resolution and compared:

  * group weights: exact RZF at the group's centre subcarrier, applied to all 12 g subcarriers of the group
    (g = 1, 2, 3, 4, 6, 12, 24 PRBs);
  * delay-domain weights: per (antenna, user) the 288-point weight response is IDFT'd and only the L
    strongest taps (common positions over antennas/users, positions signalled with 9 bits each) are sent;
    the RU rebuilds per-subcarrier weights with a DFT.

Weights are BFP-quantised to 8 bits, updated every slot (frequency effect only). The fronthaul rate is
scaled to 273 PRBs and compared with DU-side precoding (M streams) and the K-layer floor.
"""
from common import *
from cmatinv.fronthaul import stream_rate_gbps, quantize_weights, OVERHEAD, SLOTS_PER_S, BFP_EXP_BITS, PRB

SC, NPRB, M, K, BW = 12, 24, 64, 16, 8
S = SC * NPRB


def fh_gbps(coeffs_per_subband, extra_bits=0):
    """Weight fronthaul for 273 PRBs when one sub-band of NPRB PRBs needs `coeffs_per_subband` weight sets."""
    bits = coeffs_per_subband * K * (M * 2 * BW + BFP_EXP_BITS) + extra_bits
    return (PRB / NPRB) * bits * OVERHEAD * SLOTS_PER_S / 1e9


def group_weights(W, g):
    n = SC * g
    Wg = np.empty_like(W)
    for s0 in range(0, S, n):
        c = min(s0 + n // 2, S - 1)
        Wg[s0:s0 + n] = W[c]
    return Wg


def delay_weights(W, L):
    T = np.fft.ifft(W, axis=0)                                   # [taps, M, K]
    keep = np.argsort(np.sum(np.abs(T) ** 2, axis=(1, 2)))[::-1][:L]
    Tq = np.zeros_like(T)
    Tq[keep] = quantize_weights(T[keep], BW)
    Wr = np.fft.fft(Tq, axis=0)
    p = np.sum(np.abs(W) ** 2, axis=(-2, -1), keepdims=True)
    return Wr * np.sqrt(p / np.sum(np.abs(Wr) ** 2, axis=(-2, -1), keepdims=True))


def run(ds, n_drops=8):
    gs = [1, 2, 3, 4, 6, 12, 24]
    Ls = [4, 8, 12, 16, 24, 32, 48, 64]
    acc = {**{f"group g={g}": [] for g in gs}, **{f"delay L={L}": [] for L in Ls}, "per-subcarrier": []}
    for i in range(n_drops):
        cfg = ChannelConfig(seed=8000 + i, M=M, K=K, S=S, bandwidth_hz=S * 30e3, speed_kmh=3, delay_spread_s=ds)
        H = MassiveMIMOChannel(cfg).current()
        rho = snr_to_rho(10.0); al = K / rho
        W = rzf_weights(H, np.linalg.inv(gram(H, al)), rho)
        r_ex = sum_rate(H, W)
        acc["per-subcarrier"].append(sum_rate(H, quantize_weights(W, BW)) / r_ex)
        for g in gs:
            acc[f"group g={g}"].append(sum_rate(H, quantize_weights(group_weights(W, g), BW)) / r_ex)
        for L in Ls:
            acc[f"delay L={L}"].append(sum_rate(H, delay_weights(W, L)) / r_ex)
    res = {}
    for name, v in acc.items():
        if name.startswith("group"):
            g = int(name.split("=")[1]); n = NPRB // g
            fh = fh_gbps(n)
        elif name.startswith("delay"):
            L = int(name.split("=")[1]); fh = fh_gbps(L, extra_bits=9 * L)
        else:
            fh = fh_gbps(S)
        res[name] = dict(rate_ratio=float(np.mean(v)), rate_ratio_min=float(np.min(v)),
                         weight_gbps=fh, total_gbps=fh + stream_rate_gbps(K))
        print(f"  {name:16s} rate {np.mean(v):.4f} (min {np.min(v):.4f})  weights {fh:7.2f} Gbps  "
              f"total {fh + stream_rate_gbps(K):7.2f} Gbps")
    return res


def main():
    out = {}
    for ds in (30e-9, 100e-9, 300e-9):
        print(f"-- delay spread {ds * 1e9:.0f} ns")
        out[f"{ds * 1e9:.0f}ns"] = run(ds)
    print(f"DU precoding (M streams) {stream_rate_gbps(M):.2f} Gbps, K-layer floor {stream_rate_gbps(K):.2f} Gbps")
    dump(dict(out, du_precoding_gbps=stream_rate_gbps(M), k_layer_floor_gbps=stream_rate_gbps(K)), "exp25_weight_granularity")
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.8), sharey=True)
    for ax, (dsn, res) in zip(axs, out.items()):
        for pre, c, lab in (("group", "#c0392b", "group weights (g PRBs)"), ("delay", "#2980b9", "delay-domain weights (L taps)")):
            pts = sorted((r["total_gbps"], r["rate_ratio"], k.split("=")[1]) for k, r in res.items() if k.startswith(pre))
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", c=c, label=lab)
            for x, y, t in pts:
                ax.annotate(t, (x, y), fontsize=6, xytext=(3, -8), textcoords="offset points")
        ax.axvline(stream_rate_gbps(M), c="k", ls="--", label=f"DU precoding, {M} streams")
        ax.axvline(stream_rate_gbps(K), c="gray", ls=":", label=f"{K}-layer floor")
        ax.set_xscale("log"); ax.set_xlabel("downlink fronthaul (Gbit/s, 273 PRBs)"); ax.set_title(f"TDL-A, DS {dsn}")
    axs[0].set_ylabel("sum-rate / exact RZF"); axs[0].legend(fontsize=7)
    save(fig, "exp25_weight_granularity")


if __name__ == "__main__":
    main()
