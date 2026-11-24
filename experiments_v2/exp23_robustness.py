"""Exp23: RMT-WS tracking under imperfect CSI and user re-scheduling, 12 drops with 95 % bootstrap CIs.

* CSI error: the DU only sees H_est = H + E (per-user NMSE -20 / -10 dB, fresh estimation noise every slot).
  The precoder is built from H_est; rates are evaluated on the true H. The loss is relative to the exact
  inverse of the *estimated* Gram, i.e. it isolates the inverter.
* Scheduling churn: a pool of 24 users, 16 scheduled; every slot `swap` scheduled users are replaced.
  'naive' warm-starts from the previous inverse as is; 'reset rows' sets the rows/columns of the swapped
  users to diag(1 / G_kk); 'Schur swap update' downdates the removed users and appends the new ones with a
  block inverse (WarmStartTracker.reschedule) before the usual certificate + warm Newton-Schulz step.
"""
from common import *
from cmatinv.tracker import WarmStartTracker

M, K, POOL, T, N_DROPS = 64, 16, 24, 18, 12


def ci(x, B=2000, seed=0):
    x = np.asarray(x, float)
    bs = np.random.default_rng(seed).choice(x, (B, x.size)).mean(1)
    return float(x.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def run_drop(drop_seed, speed, nmse_db=None, swap=0, aware=False, snr=10.0):
    cfg = ChannelConfig(seed=drop_seed, M=M, K=POOL if swap else K, speed_kmh=speed)
    ch = MassiveMIMOChannel(cfg)
    rho = snr_to_rho(snr); al = K / rho
    rng = np.random.default_rng(drop_seed + 1)
    sched = np.arange(K)
    trk = WarmStartTracker(al, "adaptive")
    L, C = [], []
    for t, Hfull in enumerate(ch.sequence(T)):
        if swap and t > 0:
            out = rng.choice(K, swap, replace=False)
            new = rng.choice(np.setdiff1d(np.arange(POOL), sched), swap, replace=False)
            sched = sched.copy(); sched[out] = new
            if aware == "reset" and trk.Ginv is not None:
                Gi = trk.Ginv.copy()
                Gi[:, out, :] = 0; Gi[:, :, out] = 0
                trk.Ginv = Gi
        H = Hfull[:, sched, :]
        He = H
        if nmse_db is not None:
            pw = np.mean(np.abs(H) ** 2, axis=(0, 2), keepdims=True)
            e = (rng.standard_normal(H.shape) + 1j * rng.standard_normal(H.shape)) / np.sqrt(2)
            He = H + np.sqrt(pw * 10 ** (nmse_db / 10)) * e
        G = gram(He, al)
        extra = 0.0
        if aware == "reset" and swap and t > 0:
            d = np.real(np.diagonal(G, axis1=-2, axis2=-1))
            trk.Ginv[:, out, out] = 1.0 / d[:, out]
        elif aware == "schur" and swap and t > 0:
            extra = trk.reschedule(G, out)
        Gi, c = trk.update(G)
        c = c + extra
        if t >= 2:
            r_ex = sum_rate(H, rzf_weights(He, np.linalg.inv(G), rho))
            r = sum_rate(H, rzf_weights(He, Gi, rho))
            l = 100 * (1 - r / r_ex)
            L.append(l if np.isfinite(l) else 100.0); C.append(c.mean())
    return float(np.mean(L)), float(np.mean(C)), trk.stats["refresh"] / max(trk.stats["total"], 1)


def main():
    cases = {
        "perfect CSI": dict(),
        "CSI NMSE -20 dB": dict(nmse_db=-20),
        "CSI NMSE -10 dB": dict(nmse_db=-10),
        "swap 1 user/slot, naive": dict(swap=1),
        "swap 1 user/slot, reset rows": dict(swap=1, aware="reset"),
        "swap 1 user/slot, Schur swap update": dict(swap=1, aware="schur"),
        "swap 4 users/slot, naive": dict(swap=4),
        "swap 4 users/slot, reset rows": dict(swap=4, aware="reset"),
        "swap 4 users/slot, Schur swap update": dict(swap=4, aware="schur"),
    }
    res = {}
    for v in (3, 30, 120):
        print("--", v, "km/h")
        for name, kw in cases.items():
            out = [run_drop(5000 + i, v, **kw) for i in range(N_DROPS)]
            l, c, f = map(np.array, zip(*out))
            res[f"{v} | {name}"] = dict(loss_pct=ci(l), gemms=ci(c), refresh_frac=float(f.mean()))
            lm, lo, hi = ci(l); cm, clo, chi = ci(c)
            print(f"  {name:36s} loss {lm:6.3f}% [{lo:6.3f},{hi:6.3f}]  GEMM-eq {cm:5.2f} [{clo:5.2f},{chi:5.2f}]"
                  f"  refresh {100 * f.mean():5.1f}%")
    dump(res, "exp23_robustness")


if __name__ == "__main__":
    main()
