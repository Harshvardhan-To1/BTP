"""Exp10: RU-side vs DU-side precoding -- fronthaul rate vs RZF sum-rate with weight update interval and quantisation."""
from common import *
from cmatinv.fronthaul import *
import warnings; warnings.filterwarnings("ignore")


def main(n_drops=3, T=33, M=64, K=16):
    speeds = [3, 30, 120]
    Tus = [1, 2, 4, 8, 16]
    bws = [4, 6, 8, 12]
    res = {}
    for v in speeds:
        acc = {(tu, bw): [] for tu in Tus for bw in bws}
        ref = []
        for cfg, ch, H0, al, rho in drops(n_drops, speed_kmh=v, M=M, K=K, S=91, seed0=7000):
            W_hist = {}
            for t, H in enumerate(ch.sequence(T)):
                G = gram(H, al)
                Wex = rzf_weights(H, np.linalg.inv(G), rho)
                r_ex = sum_rate(H, Wex)
                ref.append(r_ex)
                for bw in bws:
                    Wq = quantize_weights(Wex, bw)
                    for tu in Tus:
                        if t % tu == 0:
                            W_hist[(tu, bw)] = Wq
                        acc[(tu, bw)].append(sum_rate(H, W_hist[(tu, bw)]))
        base = np.mean(ref)
        res[v] = {f"Tu={tu},bw={bw}": dict(rate_ratio=float(np.mean(acc[(tu, bw)]) / base),
                                          fh_gbps=stream_rate_gbps(K) + weight_rate_gbps(M, K, bw, tu))
                  for tu in Tus for bw in bws}
        res[v]["catA_M_streams"] = dict(rate_ratio=1.0, fh_gbps=stream_rate_gbps(M))
        res[v]["K_layers_only_floor"] = dict(fh_gbps=stream_rate_gbps(K))
    dump({str(v): r for v, r in res.items()}, "exp10_fronthaul")
    fig, axs = plt.subplots(1, 3, figsize=(14, 3.9), sharey=True)
    cols = {1: "#c0392b", 2: "#e67e22", 4: "#27ae60", 8: "#2980b9", 16: "#8e44ad"}
    for ax, v in zip(axs, speeds):
        for tu in Tus:
            pts = [(res[v][f"Tu={tu},bw={bw}"]["fh_gbps"], res[v][f"Tu={tu},bw={bw}"]["rate_ratio"]) for bw in bws]
            ax.plot(*zip(*pts), "o-", color=cols[tu], label=f"weights every {tu} slot(s)")
            for (x, y), bw in zip(pts, bws):
                if tu == 1:
                    ax.annotate(f"{bw}b", (x, y), fontsize=6, xytext=(2, -8), textcoords="offset points")
        a = res[v]["catA_M_streams"]
        ax.scatter(a["fh_gbps"], a["rate_ratio"], marker="*", s=160, color="k", label=f"DU precoding, M={M} streams", zorder=5)
        ax.set_title(f"{v} km/h"); ax.set_xlabel("downlink fronthaul rate (Gbit/s)")
    axs[0].set_ylabel("sum-rate / exact RZF"); axs[0].legend(fontsize=6.5, loc="lower right")
    save(fig, "exp10_fronthaul")
    for v in speeds:
        print(v, "km/h  CatA %.1f Gbps | K-layer floor %.1f Gbps" % (res[v]["catA_M_streams"]["fh_gbps"], res[v]["K_layers_only_floor"]["fh_gbps"]))
        for k, r in res[v].items():
            if k.startswith("Tu") and k.split(",")[1] in ("bw=6", "bw=8"):
                print(f"   {k:14s} ratio={r['rate_ratio']:.3f}  FH={r['fh_gbps']:.1f} Gbps")

if __name__ == "__main__":
    main()
