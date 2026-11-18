"""Priced adaptive compression vs fixed / static / load-reactive bitwidth policies (paired seeds).

Each family has one knob (bitwidth, loss tolerance eps, or price exchange rate mu); sweeping it gives a
violation vs air-loss trade-off curve. For every seed the baseline family's lower envelope is
interpolated at the air loss PAC achieved on that seed, and the paired differences are tested.
"""
from __future__ import annotations

import json
import os
import sys
from multiprocessing import Pool

import numpy as np

from .adaptive_compression import (FixedBitwidth, StaticSNRAware, LoadReactive, LoadReactiveSNR,
                                   PricedAdaptiveCompression, simulate, sqnr_db, BITWIDTHS)
from .config import SimConfig, TrafficConfig
from .traffic import generate_traffic

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "fhlm", "adaptive_compression")
EPS = (0.001, 0.003, 0.01, 0.03, 0.1)
MUS = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
FAMILIES = {
    "fixed": [lambda b=b: FixedBitwidth(b) for b in BITWIDTHS],
    "static-snr": [lambda e=e: StaticSNRAware(e) for e in EPS],
    "reactive": [lambda b=b: LoadReactive(b) for b in (8, 7, 6, 5, 4)],
    "reactive-snr": [lambda e=e: LoadReactiveSNR(e) for e in EPS],
    "pac": [lambda m=m: PricedAdaptiveCompression(m) for m in MUS],
}


def _run(args):
    load, seed, slots = args
    cfg = SimConfig(num_slots=slots, seed=seed, traffic=TrafficConfig(load=load))
    tr = generate_traffic(cfg.network, cfg.traffic, slots, seed)
    rows = []
    for fam, makers in FAMILIES.items():
        for mk in makers:
            r = simulate(cfg, mk(), tr)
            r.update(family=fam, load=load, seed=seed)
            rows.append(r)
    return rows


def envelope_at(points, x):
    """Lower envelope of (loss, violation) points, linearly interpolated at x (clamped at the ends)."""
    pts = sorted(points)
    env = []
    best = np.inf
    for lx, vy in pts:
        if vy < best:
            env.append((lx, vy))
            best = vy
    xs, ys = zip(*env)
    return float(np.interp(x, xs, ys))


def analyse(rows, metric="weighted_violation_ratio"):
    from scipy.stats import wilcoxon
    out = {}
    for load in sorted({r["load"] for r in rows}):
        R = [r for r in rows if r["load"] == load]
        seeds = sorted({r["seed"] for r in R})
        out[load] = {}
        for r_mu in MUS:
            name = f"pac-{r_mu:g}"
            res = {}
            for fam in ("fixed", "static-snr", "reactive", "reactive-snr"):
                d = []
                for s in seeds:
                    p = next(r for r in R if r["seed"] == s and r["controller"] == name)
                    pts = [(r["air_loss"], r[metric]) for r in R if r["seed"] == s and r["family"] == fam]
                    d.append(envelope_at(pts, p["air_loss"]) - p[metric])
                d = np.array(d)
                ci = 1.96 * d.std(ddof=1) / np.sqrt(len(d))
                pval = float(wilcoxon(d).pvalue) if np.any(d != 0) else 1.0
                res[fam] = dict(mean_gain=float(d.mean()), ci95=float(ci), wins=int((d > 0).sum()), n=len(d), p=pval)
            P = [r for r in R if r["controller"] == name]
            res["pac"] = dict(air_loss=float(np.mean([r["air_loss"] for r in P])),
                              violation=float(np.mean([r[metric] for r in P])),
                              mean_bitwidth=float(np.mean([r["mean_bitwidth"] for r in P])))
            out[load][name] = res
    return out


def plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    loads = sorted({r["load"] for r in rows})
    fig, axs = plt.subplots(1, len(loads), figsize=(4.6 * len(loads), 3.8))
    style = {"fixed": ("s-", "#7f8c8d"), "static-snr": ("^-", "#2980b9"), "reactive": ("v-", "#e67e22"),
             "reactive-snr": ("d-", "#8e44ad"), "pac": ("o-", "#c0392b")}
    for ax, load in zip(np.atleast_1d(axs), loads):
        R = [r for r in rows if r["load"] == load]
        for fam, (mk, col) in style.items():
            names = list(dict.fromkeys(r["controller"] for r in R if r["family"] == fam))
            xy = sorted((np.mean([r["air_loss"] for r in R if r["controller"] == n]) * 100,
                         np.mean([r["weighted_violation_ratio"] for r in R if r["controller"] == n]) * 100)
                        for n in names)
            ax.plot(*zip(*xy), mk, color=col, label=fam, ms=4)
        ax.set_xscale("symlog", linthresh=0.1)
        ax.set_yscale("log")
        ax.set_title(f"offered load {load:g}")
        ax.set_xlabel("air-resource loss from quantisation (%)")
        ax.grid(alpha=0.3)
    np.atleast_1d(axs)[0].set_ylabel("weighted deadline violations (%)")
    np.atleast_1d(axs)[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path + ".png", dpi=140)
    fig.savefig(path + ".pdf")


def main(loads=(0.7, 0.9, 1.1), seeds=10, slots=10000):
    os.makedirs(OUT, exist_ok=True)
    jobs = [(l, s, slots) for l in loads for s in range(100, 100 + seeds)]
    with Pool(4) as pool:
        rows = [r for chunk in pool.map(_run, jobs) for r in chunk]
    with open(os.path.join(OUT, "runs.json"), "w") as f:
        json.dump(rows, f, indent=1)
    summary = {"sqnr_db": {b: sqnr_db(b) for b in BITWIDTHS}, "paired": analyse(rows)}
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=float)
    plot(rows, os.path.join(OUT, "tradeoff"))
    for load, d in summary["paired"].items():
        print(f"\nload {load}")
        for name, res in d.items():
            p = res["pac"]
            line = f"  {name:9s} loss={p['air_loss']*100:6.2f}% viol={p['violation']*100:6.2f}% b={p['mean_bitwidth']:.2f} |"
            for fam in ("fixed", "static-snr", "reactive", "reactive-snr"):
                g = res[fam]
                line += f" {fam}:{g['mean_gain']*100:+.2f}±{g['ci95']*100:.2f}({g['wins']}/{g['n']})"
            print(line)


def _run_policies(args):
    load, seed, makers = args
    cfg = SimConfig(num_slots=10000, seed=seed, traffic=TrafficConfig(load=load))
    tr = generate_traffic(cfg.network, cfg.traffic, 10000, seed)
    rows = []
    for mk in makers:
        r = simulate(cfg, mk(), tr)
        r.update(load=load, seed=seed)
        rows.append(r)
    return rows


def _static_makers():
    return [lambda e=e: StaticSNRAware(e) for e in EPS]


def tuning(loads=(0.7, 0.9, 1.1), seeds=range(100, 110)):
    """PAC on a static SNR-aware floor: grid over (mu, eps) on the tuning seeds."""
    from .adaptive_compression import PACOnStatic
    makers = _static_makers() + [lambda m=m, e=e: PACOnStatic(m, e) for m in (1.0, 3.0, 10.0) for e in EPS]
    with Pool(4) as pool:
        rows = [r for ch in pool.map(_run_policies, [(l, s, makers) for l in loads for s in seeds]) for r in ch]
    with open(os.path.join(OUT, "tuning_runs.json"), "w") as f:
        json.dump(rows, f, indent=1)
    return rows


def holdout(loads=(0.7, 0.9, 1.0, 1.1), seeds=range(200, 220), mu=3.0, eps=0.01):
    """Fixed (mu, eps) picked on the tuning seeds, evaluated on unseen seeds against both baseline envelopes."""
    from scipy.stats import wilcoxon
    from .adaptive_compression import PACOnStatic
    makers = _static_makers() + [lambda b=b: FixedBitwidth(b) for b in BITWIDTHS] + [lambda: PACOnStatic(mu, eps)]
    with Pool(4) as pool:
        rows = [r for ch in pool.map(_run_policies, [(l, s, makers) for l in loads for s in seeds]) for r in ch]
    summary = {}
    for load in loads:
        R = [r for r in rows if r["load"] == load]
        P = [r for r in R if r["controller"].startswith("pac")]
        summary[load] = {"pac_air_loss": float(np.mean([r["air_loss"] for r in P])),
                         "pac_violation": float(np.mean([r["weighted_violation_ratio"] for r in P]))}
        for fam in ("static", "fixed"):
            d, base = [], []
            for s in seeds:
                p = next(r for r in P if r["seed"] == s)
                pts = [(r["air_loss"], r["weighted_violation_ratio"]) for r in R
                       if r["seed"] == s and r["controller"].startswith(fam)]
                e = envelope_at(pts, p["air_loss"])
                d.append(e - p["weighted_violation_ratio"])
                base.append(e)
            d = np.array(d)
            summary[load][fam] = dict(baseline_violation=float(np.mean(base)), gain_pp=float(d.mean() * 100),
                                      ci95_pp=float(1.96 * d.std(ddof=1) / np.sqrt(len(d)) * 100),
                                      relative=float(d.mean() / max(np.mean(base), 1e-12)),
                                      wins=int((d > 0).sum()), n=len(d),
                                      p=float(wilcoxon(d).pvalue) if np.any(d) else 1.0)
    with open(os.path.join(OUT, "holdout_runs.json"), "w") as f:
        json.dump(rows, f, indent=1)
    with open(os.path.join(OUT, "holdout_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    return summary


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    stage = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    if stage == "sweep":
        main()
    elif stage == "tuning":
        tuning()
    else:
        print(json.dumps(holdout(), indent=1))
