"""Exp12: validate the closed-form Doppler law for the warm-start residual across (M, K)."""
from exp11_doppler_law_and_certificate import *
from cmatinv.tracker import predicted_warm_residual, max_warm_speed_kmh


def main():
    rows = []
    scen = {"i.i.d., equal gains": dict(angular_spread_deg=0, shadow_db=0, min_dist_m=499, max_dist_m=500),
            "38.901 near-far + 12 deg spread": dict()}
    for sn, kw in scen.items():
        for M, K in [(64, 4), (64, 8), (64, 16), (64, 32), (128, 16), (128, 32), (128, 64)]:
            for v in (3, 10):
                r = np.median(np.concatenate([residual(Gh, X0) for cfg, Gh, X0 in aged_pairs(v, n_drops=5, M=M, K=K, **kw)]))
                omr = 1 - doppler_rho(ChannelConfig(speed_kmh=v))
                rows.append(dict(scenario=sn, M=M, K=K, speed=v, measured=float(r),
                                 predicted=float(predicted_warm_residual(K, M, omr)), beta=K / M))
    dump(dict(rows=rows, vmax_kmh={f"M={M},K={K}": max_warm_speed_kmh(K, M, corr=1.3)
                                   for M, K in [(64, 8), (64, 16), (128, 16), (128, 32), (64, 32)]}), "exp12_doppler_law")
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    for sn, c in zip(scen, ["#27ae60", "#c0392b"]):
        rr = [r for r in rows if r["scenario"] == sn]
        ax.loglog([r["predicted"] for r in rr], [r["measured"] for r in rr], "o", color=c, label=sn)
    xs = np.logspace(-2.2, -0.2, 10); ax.plot(xs, xs, "k:", label="y = x"); ax.plot(xs, 1.3 * xs, "k--", lw=.7, label="y = 1.3x")
    ax.set_xlabel("closed-form prediction"); ax.set_ylabel("measured residual of previous inverse"); ax.legend(fontsize=7)
    save(fig, "exp12_doppler_law")
    for sn in scen:
        rr = [r for r in rows if r["scenario"] == sn]
        ratio = np.array([r["measured"] / r["predicted"] for r in rr])
        print(sn, "measured/predicted: median %.2f  range %.2f-%.2f" % (np.median(ratio), ratio.min(), ratio.max()))
    print({f"M={M},K={K}": round(max_warm_speed_kmh(K, M, corr=1.3), 1) for M, K in [(64, 8), (64, 16), (128, 16), (128, 32), (64, 32)]})

if __name__ == "__main__":
    main()
