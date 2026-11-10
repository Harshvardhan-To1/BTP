"""Exp8: robustness to low-precision arithmetic (RU / accelerator / FPGA-style GEMM units)."""
from common import *
from cmatinv.tracker import WarmStartTracker, cold_start
import warnings; warnings.filterwarnings("ignore")

BITS = [4, 5, 6, 8, 10, 12, 16, 24]


def static(scn, n_drops):
    out = {"Direct Gauss-Jordan (all ops rounded)": [], "Cheb-MP + 2 NS, 6 GEMMs": [], "Cheb-MP + 3 NS, 9 GEMMs": []}
    for b in BITS:
        acc = {k: [] for k in out}
        for cfg, ch, H, al, rho in drops(n_drops, **scn):
            G = gram(H, al); Gh, s = equilibrate(G)
            r_ex = rate_with(H, np.linalg.inv(G), rho)
            X = gauss_jordan_lowprec(Gh, b)
            acc["Direct Gauss-Jordan (all ops rounded)"].append(100 * (1 - rate_with(H, unequilibrate(X, s), rho) / r_ex))
            for name, st in (("Cheb-MP + 2 NS, 6 GEMMs", 2), ("Cheb-MP + 3 NS, 9 GEMMs", 3)):
                X = cold_start(G, Gh, al, Ctx(b), 3, st)
                acc[name].append(100 * (1 - rate_with(H, unequilibrate(X, s), rho) / r_ex))
        for k in out:
            v = np.array(acc[k]); v[~np.isfinite(v)] = 100
            out[k].append(float(np.mean(v)))
    return out


def tracking(b, n_drops=3, T=14, speed=30):
    losses, gem = [], []
    for cfg, ch, H0, al, rho in drops(n_drops, speed_kmh=speed, M=64, K=16):
        trk = WarmStartTracker(al, "adaptive", bits=b)
        for t, H in enumerate(ch.sequence(T)):
            G = gram(H, al)
            Gi, c = trk.update(G)
            if t >= 2:
                r_ex = sum_rate(H, rzf_weights(H, np.linalg.inv(G), rho))
                l = 100 * (1 - sum_rate(H, rzf_weights(H, Gi, rho)) / r_ex)
                losses.append(l if np.isfinite(l) else 100); gem.append(c.mean())
    return float(np.mean(losses)), float(np.mean(gem))


def main(n_drops=6):
    scns = {"M=64,K=16, AS 12deg, 10 dB": dict(M=64, K=16),
            "ill-conditioned: AS 3deg, 25 dB": dict(M=64, K=16, angular_spread_deg=3, snr_db=25.0)}
    fig, axs = plt.subplots(1, 3, figsize=(14, 3.8))
    res = {}
    for ax, (sn, kw) in zip(axs, scns.items()):
        r = static(kw, n_drops)
        res[sn] = r
        for (name, v), c in zip(r.items(), ["#7f8c8d", "#c0392b", "#27ae60"]):
            ax.semilogy(BITS, np.maximum(v, 1e-3), "o-", color=c, label=name)
        ax.set_title(sn); ax.set_xlabel("mantissa bits"); ax.axhline(1, c="k", ls=":", lw=.8)
    axs[0].set_ylabel("sum-rate loss vs fp64 exact (%)"); axs[0].legend(fontsize=7)
    tr = {b: tracking(b) for b in [6, 8, 10, 12, 24]}
    res["tracking 30 km/h (RMT-WS adaptive)"] = {str(b): dict(rate_loss_pct=l, gemms=g) for b, (l, g) in tr.items()}
    axs[2].semilogy(list(tr), [max(v[0], 1e-3) for v in tr.values()], "*-", color="#c0392b", ms=10)
    axs[2].set_title("RMT-WS tracking, 30 km/h"); axs[2].set_xlabel("mantissa bits"); axs[2].axhline(1, c="k", ls=":", lw=.8)
    save(fig, "exp8_low_precision")
    dump(res, "exp8_low_precision")
    for sn, r in res.items():
        print(sn)
        if isinstance(r, dict) and sn in scns:
            for k, v in r.items():
                print("  %-40s" % k, " ".join(f"{b}b:{x:7.3f}" for b, x in zip(BITS, v)))
        else:
            print("  ", r)

if __name__ == "__main__":
    main()
