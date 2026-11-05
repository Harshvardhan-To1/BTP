"""Numerical validation of the Markov-fluid theory (theory.py) on the Markov-modulated family.

    python -m fhlm.theory_validation

For one LL and one eMBB cell of Family M at load 0.80 it
  1. estimates the empirical survival function of r* over the H-slot horizon from 40 000 independent
     stationary horizons of the true generator,
  2. evaluates the Chernoff-union bound U(x) and the Doob/Duffield-type bound at the same abscissae,
  3. checks the shortfall sandwich (D+1)(r*-r)^+ <= drops <= sum (a_t - r)^+ on 2000 random horizons and
     records how tight each side is,
  4. plots the effective bandwidth alpha(theta) against the mean and peak-phase rates,
and writes results/fhlm/theory_validation.json plus results/fhlm/figures/paper_fig_theory.{pdf,png}.
"""
from __future__ import annotations

import json
import os

import numpy as np

from .demand import required_rates
from .scenarios import make_config
from .theory import (chernoff_union_tail, doob_tail, effective_bandwidth, gamma_log_mgf, sandwich, theta_max)
from .traffic_markov import build_sources, sample_increments, simulate_phases

OUT_DIR = "results/fhlm"
FIG_DIR = os.path.join(OUT_DIR, "figures")


def main():
    cfg = make_config("mm_high", 3000)
    net = cfg.network
    beta = net.fh_bits_per_prb_layer
    sources = build_sources(net, cfg.traffic)
    H = cfg.control.interval_slots + cfg.control.telemetry_delay_slots
    rng = np.random.default_rng(2024)
    report = {"scenario": "mm_high", "H": H, "cells": {}}
    curves = {}
    for i in (0, 3):
        src, cell = sources[i], net.cells[i]
        scale = beta / cell.se_bits_per_prb_layer
        mean, cv, pi, D = src.mu * scale, src.cv, src.stationary(), int(cell.deadline_slots)
        M = 40000
        x = simulate_phases(rng, src, M * H + 2000)[2000:]
        d = (sample_increments(rng, src, x) * scale).reshape(M, H)
        rs = required_rates(d, np.full(M, D))
        probs = [0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001]
        xs = np.quantile(rs, 1.0 - np.array(probs))
        emp = np.array([(rs > v).mean() for v in xs])
        U = chernoff_union_tail(xs, src.P, mean, cv, pi, D, H)
        Dd = doob_tail(xs, src.P, mean, cv, pi, D, H)
        # sandwich tightness at the median budget and at the 25 % quantile budget
        lo_ratio, hi_ratio, viol = [], [], 0
        for j in rng.integers(0, M, 2000):
            r = float(np.quantile(rs, rng.choice([0.25, 0.5])))
            lo, v, hi = sandwich(d[j], r, D)
            if v > 0:
                lo_ratio.append(lo / v)
                hi_ratio.append(v / hi)
            if not (lo - 1e-6 <= v <= hi + 1e-6):
                viol += 1
        th = theta_max(mean, cv) * np.logspace(-3, np.log10(0.98), 40)
        eb = effective_bandwidth(src.P, lambda t: gamma_log_mgf(t, mean, cv), th)
        cells = report["cells"][cell.name] = {
            "deadline_slots": D, "mean_rate": float(pi @ mean), "peak_phase_rate": float(mean.max()),
            "quantile_probs": probs, "x": xs.tolist(), "empirical_tail": emp.tolist(),
            "chernoff_union_bound": U.tolist(), "doob_bound": Dd.tolist(),
            "bound_over_empirical": (U / np.maximum(emp, 1e-12)).tolist(),
            "sandwich_violations": viol, "sandwich_lower_over_drops_mean": float(np.mean(lo_ratio)),
            "sandwich_drops_over_upper_mean": float(np.mean(hi_ratio)),
            "rstar_over_mean_median": float(np.median(rs) / (pi @ mean)),
        }
        curves[cell.name] = dict(xs=xs, emp=emp, U=U, Dd=Dd, th=th, eb=eb, mean=float(pi @ mean), peak=float(mean.max()),
                                 D=D, rs=rs)
        print(json.dumps({cell.name: {k: v for k, v in cells.items() if not isinstance(v, list)}}, indent=1))
        print("  tail probs  ", probs)
        print("  empirical   ", emp.round(4).tolist())
        print("  union bound ", U.round(4).tolist())
        print("  doob bound  ", Dd.round(4).tolist())
    os.makedirs(FIG_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "theory_validation.json"), "w") as f:
        json.dump(report, f, indent=1)
    _plot(curves, net)


def _plot(curves, net):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "legend.fontsize": 7, "font.family": "serif",
                         "mathtext.fontset": "cm"})
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.2))
    cap = net.usable_bits_per_slot
    for name, c in curves.items():
        ls = "-" if c["D"] <= 10 else "--"
        lab = f"{name} ($D$={c['D']})"
        axes[0].semilogy(c["xs"] / cap, c["emp"], ls, color="k", label=f"empirical, {lab}")
        axes[0].semilogy(c["xs"] / cap, c["U"], ls, color="C3", label=f"Chernoff-union bound, {lab}")
    axes[0].set_xlabel(r"$x / C$")
    axes[0].set_ylabel(r"$P(r^\ast > x)$")
    axes[0].set_ylim(5e-4, 1.5)
    axes[0].legend(loc="lower left", frameon=False)
    axes[0].set_title("(a) tail of $r^\\ast$ and its bound", fontsize=8)
    for name, c in curves.items():
        ls = "-" if c["D"] <= 10 else "--"
        axes[1].plot(c["th"] * c["mean"], c["eb"] / c["mean"], ls, color="C0", label=name)
        axes[1].axhline(c["peak"] / c["mean"], color="0.6", lw=0.6, ls=ls)
    axes[1].set_xscale("log")
    axes[1].set_ylim(0.8, 1.3 * max(c["peak"] / c["mean"] for c in curves.values()))
    axes[1].set_xlabel(r"$\theta \cdot$ mean rate")
    axes[1].set_ylabel(r"$\alpha(\theta)$ / mean rate")
    axes[1].legend(frameon=False)
    axes[1].set_title("(b) effective bandwidth", fontsize=8)
    for name, c in curves.items():
        ls = "-" if c["D"] <= 10 else "--"
        h, edges = np.histogram(c["rs"] / c["mean"], bins=60, density=True)
        axes[2].plot(0.5 * (edges[1:] + edges[:-1]), h, ls, color="C2", label=name)
    axes[2].set_xlabel(r"$r^\ast$ / mean rate")
    axes[2].set_ylabel("density")
    axes[2].legend(frameon=False)
    axes[2].set_title("(c) distribution of $r^\\ast$", fontsize=8)
    fig.tight_layout(pad=0.4)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIG_DIR, f"paper_fig_theory.{ext}"), dpi=200)
    print("figure ->", os.path.join(FIG_DIR, "paper_fig_theory.pdf"))


if __name__ == "__main__":
    main()
