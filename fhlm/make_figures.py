"""Generate the comparison figures used in the presentation from saved results.

    python -m fhlm.make_figures

Reads results/fhlm/{main_runs.csv, sweep_runs.csv, demo_timeseries.npz,
forecast_training_T20_d2.json} and writes PNG/PDF figures to results/fhlm/figures/.
"""
from __future__ import annotations

import json
import os

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .run_experiments import RESULTS_DIR, METHOD_ORDER, METHOD_LABELS, PRIMARY_METRIC

FIG_DIR = os.path.join(RESULTS_DIR, "figures")
SCENARIO_ORDER = ["low", "moderate", "high", "overload_bursts", "shift"]
SCENARIO_LABELS = {"low": "Low\n(0.50)", "moderate": "Moderate\n(0.65)", "high": "High\n(0.80)",
                   "overload_bursts": "Flash crowds\n(0.80 + bursts)", "shift": "Shift\n(held-out, burstier)"}
COLORS = {
    "static_equal": "#9e9e9e", "reactive_prop": "#607d8b", "queue_aware": "#1f77b4", "point_forecast": "#ff7f0e",
    "proposed_window": "#8bc34a", "proposed": "#d62728", "proposed_cal": "#9c27b0", "oracle": "#212121",
}
SHORT = {
    "static_equal": "Static equal", "reactive_prop": "Reactive prop.", "queue_aware": "Deadline-aware reactive",
    "point_forecast": "Point forecast", "proposed_window": "Proposed (window q.)", "proposed": "Proposed (GBM q.)",
    "proposed_cal": "Proposed + ACI cal.", "oracle": "Oracle water-fill",
}

plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10, "legend.fontsize": 8.5,
                     "figure.dpi": 150, "savefig.dpi": 200})


def _save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"), bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.join(FIG_DIR, name + ".png"))


def fig_primary_by_scenario(df: pd.DataFrame):
    methods = [m for m in METHOD_ORDER if m in df.method.unique()]
    scen = [s for s in SCENARIO_ORDER if s in df.scenario.unique()]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    width = 0.8 / len(methods)
    x = np.arange(len(scen))
    for k, m in enumerate(methods):
        g = df[df.method == m].groupby("scenario")[PRIMARY_METRIC]
        mean = g.mean().reindex(scen).values * 100
        std = g.std().reindex(scen).fillna(0).values * 100
        ax.bar(x + (k - len(methods) / 2 + 0.5) * width, mean, width, yerr=std, capsize=2, color=COLORS[m],
               label=SHORT[m], edgecolor="black", linewidth=0.3)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in scen])
    ax.set_ylabel("Priority-weighted deadline-violation ratio [%]")
    ax.set_title("Primary metric per scenario (mean ± std over 5 test seeds; lower is better)")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(ncol=4, loc="upper left")
    _save(fig, "fig1_primary_by_scenario")


def fig_class_breakdown(df: pd.DataFrame, scenario: str = "high"):
    d = df[df.scenario == scenario]
    methods = [m for m in METHOD_ORDER if m in d.method.unique()]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, metric, title in zip(axes, ["violation_ratio_ll", "violation_ratio_embb", "fh_utilisation"],
                                 ["Low-latency cells: violation ratio [%]", "eMBB cells: violation ratio [%]",
                                  "Fronthaul link utilisation [%]"]):
        g = d.groupby("method")[metric]
        mean = g.mean().reindex(methods).values * 100
        std = g.std().reindex(methods).fillna(0).values * 100
        ax.barh(range(len(methods)), mean, xerr=std, color=[COLORS[m] for m in methods], edgecolor="black",
                linewidth=0.3, capsize=2)
        ax.set_yticks(range(len(methods)))
        ax.set_yticklabels([SHORT[m] for m in methods] if ax is axes[0] else [])
        ax.invert_yaxis()
        ax.set_title(title)
        ax.grid(axis="x", alpha=0.3)
    fig.suptitle(f"Scenario '{scenario}': per-class trade-off (mean ± std over seeds)", y=1.02)
    _save(fig, f"fig2_class_breakdown_{scenario}")


def fig_tradeoff(df: pd.DataFrame):
    scen = [s for s in ["moderate", "high", "shift"] if s in df.scenario.unique()]
    fig, axes = plt.subplots(1, len(scen), figsize=(4.2 * len(scen), 3.8), sharey=False)
    if len(scen) == 1:
        axes = [axes]
    for ax, s in zip(axes, scen):
        d = df[df.scenario == s]
        for m in METHOD_ORDER:
            g = d[d.method == m]
            if g.empty:
                continue
            ax.errorbar(g["fh_utilisation"].mean() * 100, g[PRIMARY_METRIC].mean() * 100,
                        xerr=g["fh_utilisation"].std() * 100, yerr=g[PRIMARY_METRIC].std() * 100, fmt="o",
                        color=COLORS[m], label=SHORT[m], markersize=7, capsize=2,
                        markeredgecolor="black", markeredgewidth=0.4)
        ax.set_xlabel("Fronthaul utilisation [%]")
        ax.set_ylabel("Weighted violation ratio [%]")
        ax.set_title(f"'{s}'")
        ax.grid(alpha=0.3)
    axes[-1].legend(fontsize=7.5, loc="best")
    fig.suptitle("Violation vs utilisation (lower-right is better)", y=1.02)
    _save(fig, "fig3_tradeoff")


def fig_sweep(sweep: pd.DataFrame):
    if sweep is None or sweep.empty:
        return
    methods = [m for m in METHOD_ORDER if m in sweep.method.unique()]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, metric, title in zip(axes, [PRIMARY_METRIC, "violation_ratio_ll"],
                                 ["Weighted violation ratio [%]", "Low-latency violation ratio [%]"]):
        for m in methods:
            g = sweep[sweep.method == m].groupby("interval_slots")[metric]
            T = np.array(sorted(g.groups.keys()))
            ax.errorbar(T * 0.5, g.mean().reindex(T).values * 100, yerr=g.std().reindex(T).fillna(0).values * 100,
                        marker="o", color=COLORS[m], label=SHORT[m], capsize=2)
        ax.set_xlabel("Control interval T [ms]  (budgets fixed for T)")
        ax.set_ylabel(title)
        ax.set_xscale("log")
        ax.set_xticks([2, 5, 10, 20])
        ax.set_xticklabels(["2", "5", "10", "20"])
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.grid(alpha=0.3, which="both")
    axes[0].legend(fontsize=8)
    fig.suptitle("Effect of the control interval (scenario 'high'): when does prediction matter?", y=1.02)
    _save(fig, "fig4_interval_sweep")


def fig_forecast_quality(report_path: str):
    if not os.path.exists(report_path):
        return
    with open(report_path) as f:
        rep = json.load(f)
    q = np.array(rep["quantiles"])
    cov_gbm = np.array([rep["gbm_validation"][f"coverage_q{int(round(a * 100)):02d}"] for a in q])
    cov_win = np.array([rep["window_quantile_validation"][f"coverage_q{int(round(a * 100)):02d}"] for a in q])
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    ax = axes[0]
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect calibration")
    ax.plot(q, cov_gbm, "o-", color=COLORS["proposed"], label="GBM quantile forecaster")
    ax.plot(q, cov_win, "s-", color=COLORS["proposed_window"], label="window empirical quantiles")
    ax.set_xlabel("nominal quantile level")
    ax.set_ylabel("empirical coverage (validation)")
    ax.set_title("Calibration of r* forecasts")
    ax.grid(alpha=0.3)
    ax.legend()
    ax = axes[1]
    names = ["persistence\n(last horizon r*)", "window median", "GBM median"]
    vals = [rep["persistence_median_mae_rel"], rep["window_quantile_validation"]["median_mae_rel"],
            rep["gbm_validation"]["median_mae_rel"]]
    ax.bar(names, np.array(vals) * 100, color=["#607d8b", COLORS["proposed_window"], COLORS["proposed"]],
           edgecolor="black", linewidth=0.3)
    ax.set_ylabel("relative MAE of point forecast [%]")
    ax.set_title("Point-forecast error (validation)")
    ax.grid(axis="y", alpha=0.3)
    for i, v in enumerate(vals):
        ax.text(i, v * 100 + 1, f"{v * 100:.1f}%", ha="center")
    _save(fig, "fig5_forecast_quality")


def fig_demo(npz_path: str, cell: int = 0, start: int = 6000, length: int = 600):
    if not os.path.exists(npz_path):
        return
    d = np.load(npz_path)
    T = int(d["interval"])
    sl = slice(start, start + length)
    t_ms = np.arange(start, start + length) * 0.5
    fig, axes = plt.subplots(2, 1, figsize=(10, 5.5), sharex=True)
    ax = axes[0]
    ax.fill_between(t_ms, 0, d["fh_demand"][cell, sl] / 1e6, color="lightgray", label="fronthaul demand (arrivals)")
    for m, c in [("queue_aware", COLORS["queue_aware"]), ("point_forecast", COLORS["point_forecast"]),
                 ("proposed", COLORS["proposed"])]:
        ax.step(t_ms, d[f"{m}_budget"][cell, sl] / 1e6, where="post", color=c, lw=1.4, label=f"budget: {SHORT[m]}")
    ax.set_ylabel("Mbit per slot")
    ax.set_title(f"Low-latency cell {cell}: demand vs. allocated budget (budgets fixed for {T * 0.5:.0f} ms)")
    ax.legend(ncol=2, fontsize=8)
    ax.grid(alpha=0.3)
    ax = axes[1]
    for m, c in [("queue_aware", COLORS["queue_aware"]), ("point_forecast", COLORS["point_forecast"]),
                 ("proposed", COLORS["proposed"])]:
        ax.plot(t_ms, np.cumsum(d[f"{m}_violated"][cell, sl]) / 1e6, color=c, lw=1.4, label=SHORT[m])
    ax.set_ylabel("cumulative violated bits [Mbit]")
    ax.set_xlabel("time [ms]")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    _save(fig, "fig6_demo_timeseries")


def fig_paired(df: pd.DataFrame, reference: str = "proposed"):
    """Per-seed relative reduction of the primary metric by the proposed method vs each baseline on the
    identical trace: bars = mean over seeds, whiskers = min/max over seeds, text = wins / n."""
    baselines = [m for m in ["reactive_prop", "queue_aware", "point_forecast", "proposed_window", "proposed_cal"]
                 if m in df.method.unique()]
    scen = [s for s in SCENARIO_ORDER if s in df.scenario.unique()]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    width = 0.8 / len(baselines)
    x = np.arange(len(scen))
    for k, m in enumerate(baselines):
        rel_mean, rel_lo, rel_hi, wins, ns = [], [], [], [], []
        for s in scen:
            d = df[df.scenario == s]
            ref = d[d.method == reference].set_index("seed")[PRIMARY_METRIC]
            base = d[d.method == m].set_index("seed")[PRIMARY_METRIC].reindex(ref.index)
            rel = 100 * (base - ref) / base.where(base > 0)
            rel = rel.dropna()
            rel_mean.append(rel.mean()); rel_lo.append(rel.min()); rel_hi.append(rel.max())
            wins.append(int((base - ref > 0).sum())); ns.append(int(len(ref)))
        rel_mean, rel_lo, rel_hi = map(np.array, (rel_mean, rel_lo, rel_hi))
        pos = x + (k - len(baselines) / 2 + 0.5) * width
        ax.bar(pos, rel_mean, width, color=COLORS[m], edgecolor="black", linewidth=0.3, label=f"vs {SHORT[m]}",
               yerr=[rel_mean - rel_lo, rel_hi - rel_mean], capsize=2)
        for p, h, w, n in zip(pos, rel_hi, wins, ns):
            ax.text(p, max(h, 0) + 1.5, f"{w}/{n}", ha="center", fontsize=7)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in scen])
    ax.set_ylabel("reduction of weighted violation ratio\nby proposed method [%]")
    ax.set_title("Paired per-seed comparison on identical traces (bar: mean, whiskers: min/max, text: wins/seeds)")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(ncol=3, loc="upper right", fontsize=8)
    _save(fig, "fig8_paired_reduction")


def fig_decision_time(df: pd.DataFrame):
    methods = [m for m in METHOD_ORDER if m in df.method.unique()]
    g = df.groupby("method")["decision_time_ms_mean"].mean().reindex(methods)
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(range(len(methods)), g.values, color=[COLORS[m] for m in methods], edgecolor="black", linewidth=0.3)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels([SHORT[m] for m in methods])
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("mean decision time per control epoch [ms] (Python, 4-core CPU)")
    ax.axvline(10, color="k", ls="--", lw=0.8)
    ax.text(10.5, len(methods) - 0.6, "T = 10 ms", fontsize=8)
    ax.grid(axis="x", alpha=0.3, which="both")
    _save(fig, "fig7_decision_time")


def main():
    main_path = os.path.join(RESULTS_DIR, "main_runs.csv")
    if os.path.exists(main_path):
        df = pd.read_csv(main_path)
        fig_primary_by_scenario(df)
        for s in ["high", "shift", "moderate"]:
            if s in df.scenario.unique():
                fig_class_breakdown(df, s)
        fig_tradeoff(df)
        fig_decision_time(df)
        fig_paired(df)
    sweep_path = os.path.join(RESULTS_DIR, "sweep_runs.csv")
    if os.path.exists(sweep_path):
        fig_sweep(pd.read_csv(sweep_path))
    fig_forecast_quality(os.path.join(RESULTS_DIR, "forecast_training_T20_d2.json"))
    fig_demo(os.path.join(RESULTS_DIR, "demo_timeseries.npz"))


if __name__ == "__main__":
    main()
