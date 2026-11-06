"""Exp13: headline tracking comparison with 95% bootstrap confidence intervals over user drops."""
from exp7_tracking import *
import warnings; warnings.filterwarnings("ignore")


def per_drop(name, make, speed, n):
    out = []
    for i in range(n):
        out.append(run_strategy(name, make, dict(M=64, K=16), speed, 1, 18, seed0=20000 + i)[:2])
    return np.array(out)


def ci(x, rng=np.random.default_rng(0)):
    b = [rng.choice(x, len(x)).mean() for _ in range(2000)]
    return float(x.mean()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def main(n=16):
    strat = {"cold d0=3,ns=2": None, "warm NS x1": lambda al: WarmStartTracker(al, "fixed", steps=1),
             "warm NS x2": lambda al: WarmStartTracker(al, "fixed", steps=2),
             "Proposed RMT-WS (adaptive)": lambda al: WarmStartTracker(al, "adaptive")}
    res = {}
    for v in (3, 30, 120):
        for k, mk in strat.items():
            a = per_drop(k, mk, v, n)
            res[f"{v} km/h | {k}"] = dict(loss_pct=ci(a[:, 0]), gemms=ci(a[:, 1]))
            l, g = res[f"{v} km/h | {k}"]["loss_pct"], res[f"{v} km/h | {k}"]["gemms"]
            print(f"{v:4d} km/h {k:28s} loss {l[0]:7.3f}% [{l[1]:.3f}, {l[2]:.3f}]  GEMMs {g[0]:.2f} [{g[1]:.2f}, {g[2]:.2f}]")
    dump(res, "exp13_confidence")

if __name__ == "__main__":
    main()
