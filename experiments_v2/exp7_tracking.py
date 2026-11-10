"""Exp7: slot-to-slot tracking of the inverse under channel aging (Clarke/Jakes AR(1)), 3 / 30 / 120 km/h."""
from common import *
from cmatinv.tracker import WarmStartTracker, cold_start
from cmatinv.precoding import rzf_weights, sum_rate


def run_strategy(name, make, kw, speed, n_drops, T, seed0=5000):
    losses, gemms, refr = [], [], []
    for cfg, ch, H0, al, rho in drops(n_drops, speed_kmh=speed, seed0=seed0, **kw):
        trk = make(al) if make else None
        last_w = None
        for t, H in enumerate(ch.sequence(T)):
            G = gram(H, al)
            r_ex = sum_rate(H, rzf_weights(H, np.linalg.inv(G), rho))
            if name.startswith("exact every"):
                N = 1 if name.endswith("slot") else int(name.split()[-1])
                if t % N == 0:
                    last_w = rzf_weights(H, np.linalg.inv(G), rho)
                    c = 1.0
                else:
                    c = 0.0
                r = sum_rate(H, last_w)
            elif name.startswith("cold"):
                Gh, s = equilibrate(G)
                ctx = Ctx(); X = cold_start(G, Gh, al, ctx, *kw_cold[name])
                r = sum_rate(H, rzf_weights(H, unequilibrate(X, s), rho)); c = ctx.gemms
            else:
                Gi, cost = trk.update(G)
                r = sum_rate(H, rzf_weights(H, Gi, rho)); c = cost.mean()
            if t >= 2:
                l = 100 * (1 - r / r_ex)
                losses.append(l if np.isfinite(l) else 100.0); gemms.append(c)
        if trk is not None and trk.stats["total"]:
            refr.append(trk.stats["refresh"] / trk.stats["total"])
    return np.mean(losses), np.mean(gemms), (np.mean(refr) if refr else 0.0)


kw_cold = {"cold d0=3,ns=1": (3, 1), "cold d0=3,ns=2": (3, 2), "cold d0=4,ns=2": (4, 2)}


def main(n_drops=4, T=22):
    speeds = [3, 30, 120]
    strat = {
        "exact every slot": None,
        "exact every 2": None, "exact every 4": None, "exact every 8": None,
        "cold d0=3,ns=1": None, "cold d0=3,ns=2": None, "cold d0=4,ns=2": None,
        "warm NS x1": lambda al: WarmStartTracker(al, "fixed", steps=1),
        "warm NS x2": lambda al: WarmStartTracker(al, "fixed", steps=2),
        "warm NS x3": lambda al: WarmStartTracker(al, "fixed", steps=3),
        "Proposed RMT-WS (adaptive)": lambda al: WarmStartTracker(al, "adaptive"),
    }
    kw = dict(M=64, K=16)
    res = {}
    for v in speeds:
        for n, mk in strat.items():
            res[(v, n)] = run_strategy(n, mk, kw, v, n_drops, T)
        print(f"-- {v} km/h")
        for n in strat:
            l, g, r = res[(v, n)]
            print(f"  {n:28s} loss={l:7.3f}%  GEMMs/slot={g:5.2f}  refresh={r:.3f}")
    dump({f"{v} km/h | {n}": dict(rate_loss_pct=l, gemms_per_slot=g, refresh_frac=r) for (v, n), (l, g, r) in res.items()},
         "exp7_tracking")
    fig, axs = plt.subplots(1, 3, figsize=(14, 3.8), sharey=False)
    mk = {"exact": ("s", "#7f8c8d"), "cold": ("^", "#2980b9"), "warm": ("o", "#16a085"), "Prop": ("*", "#c0392b")}
    for ax, v in zip(axs, speeds):
        for n in strat:
            l, g, r = res[(v, n)]
            k = [x for x in mk if n.startswith(x)][0]
            ax.scatter(g, max(l, 1e-3), marker=mk[k][0], color=mk[k][1], s=90 if k == "Prop" else 45,
                       label=k if n in ("exact every slot", "cold d0=3,ns=1", "warm NS x1", "Proposed RMT-WS (adaptive)") else None)
            ax.annotate(n.replace("Proposed RMT-WS (adaptive)", "RMT-WS").replace("exact every slot", "exact/1").replace("exact every ", "exact/")
                        .replace("cold d0=", "c").replace("warm NS ", "w"), (g, max(l, 1e-3)), fontsize=6, xytext=(3, 3), textcoords="offset points")
        ax.set_yscale("log"); ax.set_xlabel("GEMMs per slot per PRB"); ax.set_title(f"{v} km/h")
    axs[0].set_ylabel("sum-rate loss vs exact (%)"); axs[0].legend(fontsize=7)
    save(fig, "exp7_tracking")

if __name__ == "__main__":
    main()
