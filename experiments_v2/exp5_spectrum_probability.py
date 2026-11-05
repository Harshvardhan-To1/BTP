"""Exp5: Marchenko-Pastur spectral model and the probability that the zero-eigensolve interval holds."""
from common import *

def main(n_drops=30):
    # (a) histogram vs MP density, i.i.d. Rayleigh, equal gains, K/M = 0.25
    K, M = 16, 64
    ev = []
    rng = np.random.default_rng(0)
    for _ in range(400):
        H = (rng.standard_normal((K, M)) + 1j * rng.standard_normal((K, M))) / np.sqrt(2 * M)
        ev.append(np.linalg.eigvalsh(H @ H.conj().T))
    ev = np.concatenate(ev)
    b = K / M
    lo, hi = (1 - np.sqrt(b)) ** 2, (1 + np.sqrt(b)) ** 2
    x = np.linspace(lo, hi, 400)
    mp = np.sqrt((hi - x) * (x - lo)) / (2 * np.pi * b * x)

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    ax[0].hist(ev, bins=60, density=True, color="#bbb", label="empirical (K=16, M=64)")
    ax[0].plot(x, mp, "r", label="Marchenko-Pastur")
    ax[0].axvline(lo, ls=":", c="k"); ax[0].axvline(hi, ls=":", c="k")
    ax[0].set_xlabel("eigenvalue of H H$^H$/M"); ax[0].set_ylabel("density"); ax[0].legend()
    ax[0].set_title("(a) Gram spectrum follows MP law")

    # (b) coverage of [a,b] for scenarios and margins
    scen = {
        "iid, equal gain": dict(angular_spread_deg=0, shadow_db=0, min_dist_m=499, max_dist_m=500),
        "iid + UMa near-far": dict(angular_spread_deg=0),
        "AS 12deg + near-far": dict(angular_spread_deg=12),
        "AS 3deg + near-far": dict(angular_spread_deg=3),
        "Rician 6 dB + AS 12deg": dict(angular_spread_deg=12, rician_k_db=6),
    }
    settings = {"fixed-ratio MP+Weyl": (1.0, 1.0, "mp"), "moment-matched MP (0.5,1.1)": (0.5, 1.1, "mom")}
    res = {}
    for sn, kw in scen.items():
        for gn, (ml, mh, kind) in settings.items():
            cov_lo = cov_hi = tot = 0
            kappa_ratio = []
            for cfg, ch, H, al, rho in drops(n_drops, **kw):
                G = gram(H, al)
                Gh, s = equilibrate(G)
                e = np.linalg.eigvalsh(Gh)
                if kind == "mp":
                    a_, b_ = mp_interval(G, cfg.M, al, margin_hi=mh, margin_lo=ml)
                else:
                    dg = np.real(np.diagonal(G, axis1=-2, axis2=-1))
                    a_, b_ = moment_interval(Gh, al / dg, margin_hi=mh, margin_lo=ml)
                cov_lo += np.sum(e[:, 0] >= a_); cov_hi += np.sum(e[:, -1] <= b_); tot += e.shape[0]
                kappa_ratio.append(np.mean((b_ / a_) / (e[:, -1] / e[:, 0])))
            res[f"{sn} | {gn}"] = dict(P_lmin_ge_a=cov_lo / tot, P_lmax_le_b=cov_hi / tot,
                                      kappa_est_over_true=float(np.mean(kappa_ratio)))
    dump(res, "exp5_coverage")
    names = list(scen)
    w = 0.38
    xs = np.arange(len(names))
    for i, gn in enumerate(settings):
        v = [min(res[f"{n} | {gn}"]["P_lmin_ge_a"], res[f"{n} | {gn}"]["P_lmax_le_b"]) for n in names]
        ax[1].bar(xs + (i - 0.5) * w, v, w, label=gn)
    ax[1].set_xticks(xs); ax[1].set_xticklabels([n.replace(" + ", "\n+ ").replace(", ", ",\n") for n in names], fontsize=7)
    ax[1].set_ylabel("P(spectrum inside [a,b])"); ax[1].set_ylim(0, 1.05); ax[1].legend(fontsize=8)
    ax[1].set_title("(b) coverage of the zero-eigensolve interval")
    save(fig, "exp5_spectrum_probability")
    for k, v in res.items():
        print(f"{k:50s} P(lmin>=a)={v['P_lmin_ge_a']:.3f} P(lmax<=b)={v['P_lmax_le_b']:.3f} kappa_est/true={v['kappa_est_over_true']:.2f}")

if __name__ == "__main__":
    main()
