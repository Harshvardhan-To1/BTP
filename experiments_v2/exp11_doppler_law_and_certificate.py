"""Exp11: (a) Doppler-to-warm-start law, (b) tail bound of the randomised certificate, (c) safety audit."""
from common import *
from cmatinv.channel import doppler_rho
import warnings; warnings.filterwarnings("ignore")

SPEEDS = [1, 3, 5, 10, 20, 30, 50, 80, 120]


def aged_pairs(speed, n_drops=6, **kw):
    """Yield (Gh_t, X0 = rescaled inverse of previous slot) for all subcarriers."""
    for cfg, ch, H0, al, rho in drops(n_drops, speed_kmh=speed, seed0=9000, **kw):
        Gp = gram(H0, al)
        Hn = ch.step()
        Gn = gram(Hn, al)
        Gh, s = equilibrate(Gn)
        X0 = np.linalg.inv(Gp) / (s[:, :, None] * s[:, None, :])
        yield cfg, Gh, X0


def doppler_law():
    out = {}
    for name, kw in {"K=16, 10 dB": dict(M=64, K=16), "K=16, 25 dB": dict(M=64, K=16, snr_db=25.0),
                     "K=8, 10 dB": dict(M=64, K=8)}.items():
        r0 = []
        for v in SPEEDS:
            vals = [residual(Gh, X0) for cfg, Gh, X0 in aged_pairs(v, **kw)]
            r0.append(float(np.median(np.concatenate(vals))))
        out[name] = r0
    return out


def main():
    law = doppler_law()
    one_m_rho = np.array([1 - doppler_rho(ChannelConfig(speed_kmh=v)) for v in SPEEDS])
    # (a) log-log slope of r0 vs sqrt(1-rho) (should be ~1 if r0 ~ c sqrt(1-rho) ~ v)
    fits = {}
    for n, r in law.items():
        sl, ic = np.polyfit(np.log(np.sqrt(one_m_rho[:6])), np.log(r[:6]), 1)
        fits[n] = dict(slope_low_speed=float(sl), c=float(np.exp(ic)), r0=r)
    # (b) tail bound of certificate: P(r_hat^2 <= (1-d) r^2) <= exp(-p d^2 s / 2), s = stable rank of R
    rng = np.random.default_rng(5)
    d = 0.5
    tail = {}
    for p in (1, 2, 4):
        emp, bnd = [], []
        for v in (10, 30):
            for cfg, Gh, X0 in aged_pairs(v, n_drops=2, M=64, K=16):
                R = np.eye(16) - Gh @ X0
                sv = np.linalg.svd(R, compute_uv=False) ** 2
                srank = sv.sum(-1) ** 2 / (sv ** 2).sum(-1)
                true = np.sqrt(sv.sum(-1) / 16)
                miss = np.zeros(len(R))
                for _ in range(300):
                    miss += probe_residual(Gh, X0, p, rng) ** 2 <= (1 - d) * true ** 2
                emp.append(miss / 300); bnd.append(np.minimum(1, np.exp(-p * d * d * srank / 2)))
        tail[p] = dict(empirical_miss=float(np.concatenate(emp).mean()), bound=float(np.concatenate(bnd).mean()))
    # (c) safety audit: accept warm start if r_hat <= tau; failure = spectral radius of R >= 1
    audit = {}
    taus = [0.1, 0.177, 0.25, 0.3, 0.4, 0.5]
    rows = {t: [0, 0, 0] for t in taus}
    for v in (3, 10, 30, 60, 120):
        for cfg, Gh, X0 in aged_pairs(v, n_drops=4, M=64, K=16):
            R = np.eye(16) - Gh @ X0
            rho_R = np.abs(np.linalg.eigvals(R)).max(-1)
            rh = probe_residual(Gh, X0, 2, rng)
            for t in taus:
                acc = rh <= t
                rows[t][0] += acc.sum(); rows[t][1] += (acc & (rho_R >= 1)).sum(); rows[t][2] += len(rh)
    audit = {str(t): dict(accept_frac=a / n, unsafe_accepts=int(u), n=int(n)) for t, (a, u, n) in rows.items()}
    dump(dict(doppler_law=fits, certificate_tail=tail, safety_audit=audit), "exp11_doppler_certificate")

    fig, ax = plt.subplots(1, 3, figsize=(14, 3.8))
    for n, r in law.items():
        ax[0].loglog(SPEEDS, r, "o-", label=n)
    ax[0].loglog(SPEEDS, 0.5 * np.array(SPEEDS) / 30, "k:", label="slope 1 reference")
    ax[0].axhline(0.3, c="r", ls="--", lw=.8); ax[0].text(1, 0.33, "refresh threshold", fontsize=7, color="r")
    ax[0].set_xlabel("speed (km/h)"); ax[0].set_ylabel("residual of previous-slot inverse"); ax[0].legend(fontsize=7)
    ax[0].set_title("(a) warm-start error grows linearly with speed")
    ps = list(tail)
    ax[1].semilogy(ps, [tail[p]["empirical_miss"] + 1e-6 for p in ps], "o-", label="empirical")
    ax[1].semilogy(ps, [tail[p]["bound"] for p in ps], "s--", label="bound exp(-p d^2 s/2)")
    ax[1].set_xlabel("probes p"); ax[1].set_ylabel("P(certificate under-reads by >50% in r$^2$)"); ax[1].legend(fontsize=7)
    ax[1].set_title("(b) certificate tail bound")
    ax[2].plot([float(t) for t in audit], [a["accept_frac"] for a in audit.values()], "o-", label="accepted warm starts")
    ax[2].plot([float(t) for t in audit], [a["unsafe_accepts"] / a["n"] for a in audit.values()], "rs-", label="accepted but not contractive")
    ax[2].set_xlabel("acceptance threshold tau"); ax[2].legend(fontsize=7); ax[2].set_title("(c) safety audit (p=2 probes)")
    save(fig, "exp11_doppler_certificate")
    for n, f in fits.items():
        print(n, "slope(low speed)=%.2f c=%.2f" % (f["slope_low_speed"], f["c"]), ["%.3f" % x for x in f["r0"]])
    print("tail", tail); print("audit", audit)

if __name__ == "__main__":
    main()
