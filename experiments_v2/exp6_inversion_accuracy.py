"""Exp6: inversion accuracy and RZF sum-rate loss vs GEMM budget (cold start, static channel)."""
from common import *


def methods(Gh, G, alpha, cfg_unused=None):
    a, b = interval(G, Gh, alpha)
    out = {}

    def run(fn):
        ctx = Ctx()
        X = fn(ctx)
        return ctx.gemms, X

    for n in range(2, 10):
        out.setdefault("Neumann w=1 (Prabhu'13, Wu'13)", []).append(run(lambda c: neumann(Gh, c, n, 1.0)))
        out.setdefault("Neumann, MP-optimal w", []).append(run(lambda c: neumann(Gh, c, n, float(np.mean(2 / (a + b))))))
        out.setdefault("Joint Newton-Neumann (Shao'16)", []).append(run(lambda c: jnn(Gh, c, n)))
    for st in range(1, 6):
        out.setdefault("Newton-Schulz, classical init", []).append(
            run(lambda c: newton_schulz(Gh, c, classical_ns_init(Gh), st)))
        out.setdefault("Newton-Schulz, MP-scalar init (ours)", []).append(
            run(lambda c: ns_optimal_scalar(Gh, c, a, b, st)))
    for d in range(2, 14):
        out.setdefault("Chebyshev-MP (ours)", []).append(run(lambda c: chebyshev_inverse(Gh, c, a, b, d)))
    grid = [(d0, st) for d0 in range(0, 9) for st in range(0, 4)]
    out["_grid"] = [((d0, st),) + run(lambda c: cheb_ns(Gh, c, a, b, d0, st)) for d0, st in grid if (d0 + st) > 0]
    return out


def collect(n_drops, seed0, **kw):
    agg = {}
    for cfg, ch, H, al, rho in drops(n_drops, seed0=seed0, **kw):
        G = gram(H, al)
        Gh, s = equilibrate(G)
        r_ex = rate_with(H, np.linalg.inv(G), rho)
        for name, lst in methods(Gh, G, al).items():
            for i, item in enumerate(lst):
                key = (name, item[0] if name == "_grid" else i)
                g, X = (item[1], item[2]) if name == "_grid" else item
                rate = rate_with(H, unequilibrate(X, s), rho)
                rec = agg.setdefault(key, dict(g=g, res=[], loss=[]))
                rec["res"].append(residual(Gh, X).mean())
                rec["loss"].append(100 * (1 - rate / r_ex))
    return agg


def main(n_drops=12):
    pts = {"M=64, K=16": dict(M=64, K=16), "M=128, K=16": dict(M=128, K=16), "M=64, K=32": dict(M=64, K=32)}
    fig, axs = plt.subplots(2, 3, figsize=(14, 7), sharex="col")
    table = {}
    style = {"Neumann w=1 (Prabhu'13, Wu'13)": ("#888", "s--"), "Neumann, MP-optimal w": ("#2980b9", "^--"),
             "Joint Newton-Neumann (Shao'16)": ("#8e44ad", "v--"), "Newton-Schulz, classical init": ("#e67e22", "x--"),
             "Newton-Schulz, MP-scalar init (ours)": ("#16a085", "o-"), "Chebyshev-MP (ours)": ("#27ae60", "D-"),
             "Proposed: Chebyshev-MP init + NS": ("#c0392b", "*-")}
    for j, (pn, kw) in enumerate(pts.items()):
        val = collect(max(n_drops // 2, 4), 1000, **kw)       # validation drops pick the proposed config
        test = collect(n_drops, 5000, **kw)
        # proposed: per integer GEMM budget, choose the (d0, steps) with lowest validation residual
        by_g = {}
        for (name, cfgk), rec in val.items():
            if name == "_grid":
                by_g.setdefault(int(rec["g"]), []).append((np.mean(rec["res"]), cfgk))
        series = {}
        for (name, k), rec in test.items():
            if name != "_grid":
                series.setdefault(name, []).append((rec["g"], np.mean(rec["res"]), np.mean(rec["loss"])))
        prop = []
        for g in sorted(by_g):
            best = min(by_g[g])[1]
            rec = test[("_grid", best)]
            prop.append((rec["g"], np.mean(rec["res"]), np.mean(rec["loss"]), best))
        series["Proposed: Chebyshev-MP init + NS"] = [p[:3] for p in prop]
        table[pn] = {n: [dict(gemms=g, residual=r, rate_loss_pct=l) for g, r, l in v] for n, v in series.items()}
        table[pn]["proposed_configs"] = {int(p[0]): p[3] for p in prop}
        for name, v in series.items():
            v = sorted(v)
            c, m = style[name]
            axs[0, j].semilogy([x[0] for x in v], [x[1] for x in v], m, color=c, label=name)
            axs[1, j].semilogy([x[0] for x in v], np.maximum([x[2] for x in v], 1e-4), m, color=c)
        axs[0, j].set_title(pn + f"  (beta=K/M={kw['K']/kw['M']:.3f})")
        axs[1, j].set_xlabel("complex K$^3$-MAC GEMMs")
        axs[1, j].axhline(1.0, c="k", ls=":", lw=0.8)
        axs[0, j].set_xlim(0, 14); axs[1, j].set_xlim(0, 14)
    axs[0, 0].set_ylabel("normalised residual ||I-GX||$_F$/sqrt(K)")
    axs[1, 0].set_ylabel("RZF sum-rate loss vs exact (%)")
    axs[0, 0].legend(fontsize=7)
    axs[0, 0].set_ylim(1e-6, 5); axs[0, 1].set_ylim(1e-6, 5); axs[0, 2].set_ylim(1e-6, 5)
    save(fig, "exp6_inversion_accuracy")
    dump(table, "exp6_inversion_accuracy")
    print("GEMMs needed for <=1% sum-rate loss / residual<=1e-2:")
    for pn, t in table.items():
        for n, v in t.items():
            if n == "proposed_configs":
                continue
            ok = [x["gemms"] for x in v if x["rate_loss_pct"] <= 1.0]
            ok2 = [x["gemms"] for x in v if x["residual"] <= 1e-2]
            print(f"  {pn:12s} {n:42s} 1%-loss: {min(ok) if ok else '>'+str(max(x['gemms'] for x in v)):>5}   res<=1e-2: {min(ok2) if ok2 else 'n/a'}")

if __name__ == "__main__":
    main()
