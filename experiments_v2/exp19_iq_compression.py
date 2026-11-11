"""Exp19: uplink IQ compression at equal receiver quality (restores Part A Exp. 1-4 without the missing src/).

Quality is the post-MMSE-detection SINR loss versus uncompressed 16-bit IQ, measured on 38.901 UMa / TDL-A
channels with QAM users. Reported: the largest compression ratio each method reaches with <= 0.5 dB and
<= 1 dB loss, and the post-detection EVM against the 3GPP 64-QAM (8 %) and 256-QAM (3.5 %) limits.
"""
from common import *
from iqcomp.uplink import UplinkConfig, make_slot, post_detection_quality
from iqcomp.codecs import (raw_bits, bfp, svd_code, ras_code, pilot_code, dft_beamspace_code, combine_code,
                           mp_rank, dmrs_columns)
import warnings; warnings.filterwarnings("ignore")

PILOTS = dmrs_columns()


def candidates(s):
    Y = s["Y"]
    for b in range(4, 11):
        yield "O-RAN BFP", f"b={b}", lambda b=b: bfp(Y, b)
    for r in (16, 24, 32, 48):
        for b in (7, 9):
            yield "DFT beamspace (prior art)", f"r={r},b={b}", lambda r=r, b=b: dft_beamspace_code(Y, r, b)
    for m in (1.0, 1.5, 3.0):
        r = mp_rank(Y, margin=m)
        for b in (6, 7, 8, 9):
            yield "PCA / exact SVD + RMT rank", f"m={m},b={b}", lambda r=r, b=b: svd_code(Y, r, b, 8)
            yield "RAS-BFP Gaussian sketch + RMT rank", f"m={m},b={b}", \
                lambda r=r, b=b: ras_code(Y, r, b, 8, oversample=8)
            yield "RAS-BFP pilot sketch + RMT rank (ours)", f"m={m},b={b}", \
                lambda m=m, b=b: pilot_code(Y, b, 8, PILOTS, margin=m)[0]
    for b in range(5, 11):
        yield "_combine", f"b={b}", lambda b=b: combine_code(Y, s["H"], s["power"], b)


def main(n_drops=3):
    scen = {f"K={K}, SNR={snr} dB": dict(K=K, snr_db=snr) for K in (4, 8) for snr in (10, 20, 30)}
    res = {}
    for sname, kw in scen.items():
        acc = {}
        for d in range(n_drops):
            s = make_slot(UplinkConfig(n_prb=24, seed=100 + d, **kw))
            P, M, _ = s["Y"].shape
            raw = raw_bits(P, M)
            ref = post_detection_quality(s["Y"], s)
            for meth, par, f in candidates(s):
                Yh, bits = f()
                q = post_detection_quality(Yh, s, combined=meth == "_combine")
                a = acc.setdefault(meth, {}).setdefault(par, dict(cr=[], loss=[], evm=[], ref_evm=[]))
                a["cr"].append(raw / bits); a["loss"].append(ref["sinr_db"] - q["sinr_db"])
                a["evm"].append(q["evm"]); a["ref_evm"].append(ref["evm"])
        out = {}
        for meth, d in acc.items():
            pts = {par: {k: float(np.mean(v)) for k, v in a.items()} for par, a in d.items()}
            best = {}
            for lim in (0.5, 1.0):
                ok = [(p["cr"], par) for par, p in pts.items() if p["loss"] <= lim]
                best[f"cr_at_{lim}dB"] = max(ok)[0] if ok else None
                best[f"cfg_at_{lim}dB"] = max(ok)[1] if ok else None
            for lim, nm in ((0.08, "64qam"), (0.035, "256qam")):
                ok = [p["cr"] for p in pts.values() if p["evm"] <= lim]
                best[f"cr_evm_{nm}"] = max(ok) if ok else None
            out[meth.replace("_combine", "CSI-aided RU combining (reference, needs DU weights)")] = \
                dict(best=best, points=pts)
        res[sname] = out
        print(f"== {sname}  (uncompressed post-detection EVM "
              f"{100 * np.mean(next(iter(acc['O-RAN BFP'].values()))['ref_evm']):.2f} %)")
        for meth, o in out.items():
            b = o["best"]
            fmt = lambda x: f"{x:5.1f}x" if x else "  -  "
            print(f"   {meth:52s} <=0.5dB {fmt(b['cr_at_0.5dB'])}  <=1dB {fmt(b['cr_at_1.0dB'])}"
                  f"  EVM<=8% {fmt(b['cr_evm_64qam'])}  EVM<=3.5% {fmt(b['cr_evm_256qam'])}")
    dump(res, "exp19_iq_compression")

    fig, axs = plt.subplots(1, 3, figsize=(14, 3.9), sharey=True)
    cols = {"O-RAN BFP": "#7f8c8d", "DFT beamspace (prior art)": "#8e44ad", "PCA / exact SVD + RMT rank": "#2980b9",
            "RAS-BFP Gaussian sketch + RMT rank": "#e67e22", "RAS-BFP pilot sketch + RMT rank (ours)": "#c0392b",
            "CSI-aided RU combining (reference, needs DU weights)": "#27ae60"}
    for ax, snr in zip(axs, (10, 20, 30)):
        o = res[f"K=8, SNR={snr} dB"]
        for meth, c in cols.items():
            pts = sorted((p["cr"], p["loss"]) for p in o[meth]["points"].values())
            front, best = [], 1e9
            for cr, l in sorted(pts, key=lambda t: -t[0]):
                if l < best:
                    front.append((cr, l)); best = l
            ax.plot(*zip(*sorted(front)), "o-", color=c, label=meth, ms=4)
        ax.axhline(0.5, ls=":", color="k", lw=1); ax.axhline(1.0, ls="--", color="k", lw=1)
        ax.set_yscale("log"); ax.set_ylim(0.01, 30); ax.set_xlabel("compression ratio vs 16-bit IQ")
        ax.set_title(f"K = 8 users, M = 64, per-antenna SNR {snr} dB")
    axs[0].set_ylabel("post-detection SINR loss (dB)"); axs[0].legend(fontsize=6.5, loc="upper left")
    save(fig, "exp19_iq_compression")


if __name__ == "__main__":
    main()
