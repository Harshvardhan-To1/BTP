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
    "static_equal": "#9e9e9e", "reactive_prop": "#607d8b", "maxweight": "#795548", "queue_aware": "#1f77b4",
    "point_forecast": "#ff7f0e", "fixed_quantile": "#e6b800", "proposed_window": "#8bc34a", "proposed": "#d62728",
    "proposed_cal": "#9c27b0", "oracle": "#212121", "proposed_miscal": "#d62728", "oracle_kkt": "#616161",
    "proposed_transfer": "#e91e63",
}
SHORT = {
    "static_equal": "Static equal", "reactive_prop": "Reactive prop.", "maxweight": "MaxWeight",
    "queue_aware": "Deadline-aware reactive", "point_forecast": "Point forecast", "fixed_quantile": "Fixed quantile",
    "proposed_window": "Proposed (window q.)", "proposed": "Proposed (GBM q.)", "proposed_cal": "Proposed + ACI cal.",
    "oracle": "Oracle water-fill", "proposed_miscal": "Proposed (miscalibrated)", "oracle_kkt": "Oracle + KKT rule",
    "proposed_transfer": "Proposed (transferred forecaster)",
}
TGPP_ORDER = ["tgpp_moderate", "tgpp_high"]
TGPP_LABELS = {"tgpp_moderate": "3GPP traffic, moderate\n(0.65)", "tgpp_high": "3GPP traffic, high\n(0.80)"}

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
    ax.set_title(f"Primary metric per scenario (mean ± std over {df.seed.nunique()} test seeds; lower is better)")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(ncol=5, loc="upper left", fontsize=7.5)
    _save(fig, "fig1_primary_by_scenario")


def fig_tgpp(df: pd.DataFrame):
    """Standards-based (3GPP) traffic family: primary metric and LL ratio per controller."""
    d = df[df.scenario.isin(TGPP_ORDER)]
    if d.empty:
        return
    methods = [m for m in METHOD_ORDER if m in d.method.unique()]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9))
    for ax, metric, title in zip(axes, [PRIMARY_METRIC, "violation_ratio_ll"],
                                 ["Priority-weighted violation ratio [%]", "Low-latency (XR) violation ratio [%]"]):
        x = np.arange(len(TGPP_ORDER))
        width = 0.8 / len(methods)
        for k, m in enumerate(methods):
            g = d[d.method == m].groupby("scenario")[metric]
            ax.bar(x + (k - len(methods) / 2 + 0.5) * width, g.mean().reindex(TGPP_ORDER).values * 100, width,
                   yerr=g.std().reindex(TGPP_ORDER).fillna(0).values * 100, capsize=2, color=COLORS[m],
                   label=SHORT[m], edgecolor="black", linewidth=0.3)
        ax.set_xticks(x)
        ax.set_xticklabels([TGPP_LABELS[s] for s in TGPP_ORDER])
        ax.set_ylabel(title)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(ncol=2, fontsize=7, loc="upper left")
    fig.suptitle(f"3GPP TR 38.901 UMa + FTP-3 / XR traffic (mean ± std over {d.seed.nunique()} test seeds; lower is better)",
                 y=1.02)
    _save(fig, "fig12_tgpp")


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


def fig_compression(comp: pd.DataFrame):
    """Part A lever (BFP width -> offered load) x Part B lever (allocation rule)."""
    if comp is None or comp.empty:
        return
    methods = [m for m in METHOD_ORDER if m in comp.method.unique()]
    widths = sorted(comp.mantissa_bits.unique())
    load = comp.groupby("mantissa_bits")["realised_load"].mean().reindex(widths)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9))
    for ax, metric, title in zip(axes, [PRIMARY_METRIC, "violation_ratio_ll"],
                                 ["Weighted violation ratio [%]", "Low-latency violation ratio [%]"]):
        for m in methods:
            g = comp[comp.method == m].groupby("mantissa_bits")[metric]
            ax.errorbar(widths, g.mean().reindex(widths).values * 100, yerr=g.std().reindex(widths).fillna(0).values * 100,
                        marker="o", color=COLORS[m], label=SHORT[m], capsize=2)
        ax.set_xticks(widths)
        ax.set_xticklabels([f"BFP-{b}\nload {load[b]:.2f}" for b in widths])
        ax.set_xlabel("BFP mantissa bits (Part A)  →  mean offered load")
        ax.set_ylabel(title)
        ax.set_yscale("log")
        ax.grid(alpha=0.3, which="both")
    axes[0].legend(fontsize=8, loc="lower right")
    fig.suptitle("Same user traffic, different compression: compression sets the load, allocation decides the loss", y=1.02)
    _save(fig, "fig9_compression_vs_allocation")


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


def fig_miscalibration(mis: pd.DataFrame):
    """Proposition 4 check: weighted violations vs probability-level shift of the forecast."""
    if mis is None or mis.empty:
        return
    scen = [s for s in SCENARIO_ORDER if s in mis.scenario.unique()]
    fig, axes = plt.subplots(1, len(scen), figsize=(4.2 * len(scen), 3.4), squeeze=False)
    for ax, sc in zip(axes[0], scen):
        d = mis[(mis.scenario == sc) & (mis.method == "proposed_miscal")]
        g = d.groupby("eps")[PRIMARY_METRIC]
        eps = sorted(d.eps.unique())
        ax.errorbar(eps, g.mean().reindex(eps).values * 100, yerr=g.std().reindex(eps).fillna(0).values * 100,
                    marker="o", color=COLORS["proposed"], capsize=2, label="Proposed, levels shifted by ε")
        for m, ls in (("point_forecast", "--"), ("queue_aware", ":")):
            v = mis[(mis.scenario == sc) & (mis.method == m)][PRIMARY_METRIC].mean() * 100
            if np.isfinite(v):
                ax.axhline(v, ls=ls, color=COLORS[m], label=SHORT[m])
        ax.set_xlabel("probability-level shift ε of all forecast quantiles")
        ax.set_ylabel("Weighted violation ratio [%]")
        ax.set_title(SCENARIO_LABELS.get(sc, sc))
        ax.grid(alpha=0.3)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, -0.08), frameon=False)
    fig.suptitle("Robustness to forecast miscalibration (ε < 0: under-reserve, ε > 0: over-reserve)", y=1.03)
    _save(fig, "fig10_miscalibration")


def fig_delay(dl: pd.DataFrame):
    """Sensitivity to the telemetry delay tau."""
    if dl is None or dl.empty:
        return
    methods = [m for m in METHOD_ORDER if m in dl.method.unique()]
    taus = sorted(dl.telemetry_delay_slots.unique())
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    for m in methods:
        g = dl[dl.method == m].groupby("telemetry_delay_slots")[PRIMARY_METRIC]
        ax.errorbar(np.array(taus) * 0.5, g.mean().reindex(taus).values * 100,
                    yerr=g.std().reindex(taus).fillna(0).values * 100, marker="o", color=COLORS[m], label=SHORT[m],
                    capsize=2)
    ax.set_xlabel("telemetry delay τ [ms]")
    ax.set_ylabel("Weighted violation ratio [%]")
    ax.set_title("Effect of stale state information (scenario high)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    _save(fig, "fig11_delay")


PAPER_RC = {"font.size": 7, "axes.labelsize": 7, "legend.fontsize": 6, "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5, "axes.linewidth": 0.6, "lines.linewidth": 1.0, "savefig.dpi": 300,
            "font.family": "serif", "mathtext.fontset": "cm"}
PAPER_SHORT = dict(SHORT, **{"queue_aware": "Deadline-aware react.", "proposed_window": "Proposed, window q.",
                             "proposed": "Proposed (GBM + KKT)", "proposed_cal": "Proposed + ACI",
                             "proposed_transfer": "Proposed, transferred", "oracle_kkt": "Oracle + KKT"})
PAPER_SCEN = {"low": "Low\n0.50", "moderate": "Moderate\n0.65", "high": "High\n0.80",
              "overload_bursts": "Flash\n0.80+", "shift": "Shift\n(held-out)"}
PAPER_TGPP = {"tgpp_moderate": "0.65", "tgpp_high": "0.80"}


def _grouped_bars(ax, d, scen, labels, methods, metric):
    width = 0.84 / len(methods)
    x = np.arange(len(scen))
    for k, m in enumerate(methods):
        g = d[d.method == m].groupby("scenario")[metric]
        mean = g.mean().reindex(scen).values * 100
        std = g.std().reindex(scen).fillna(0).values * 100
        ax.bar(x + (k - len(methods) / 2 + 0.5) * width, mean, width, yerr=std, capsize=1, color=COLORS[m],
               label=PAPER_SHORT[m], edgecolor="black", linewidth=0.25,
               error_kw={"lw": 0.5}, hatch="///" if m == "proposed" else None)
    ax.set_xticks(x)
    ax.set_xticklabels([labels[s] for s in scen])
    ax.grid(axis="y", alpha=0.3, lw=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(length=2, pad=1.5)


def paper_fig_overview(df: pd.DataFrame):
    """Camera-ready figure for the paper: both traffic families side by side, no in-figure title."""
    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(1, 2, figsize=(7.1, 1.85), gridspec_kw={"width_ratios": [5.0, 2.3], "wspace": 0.22})
        s = df[df.scenario.isin(SCENARIO_ORDER)]
        methods_s = [m for m in METHOD_ORDER if m in s.method.unique()]
        _grouped_bars(axes[0], s, [x for x in SCENARIO_ORDER if x in s.scenario.unique()], PAPER_SCEN, methods_s,
                      PRIMARY_METRIC)
        axes[0].set_ylabel("$V_w$ [%]")
        axes[0].set_xlabel("(a) Family S: scenario (offered load)", labelpad=2)
        g = df[df.scenario.isin(TGPP_ORDER)]
        methods_g = [m for m in METHOD_ORDER if m in g.method.unique()]
        _grouped_bars(axes[1], g, TGPP_ORDER, PAPER_TGPP, methods_g, PRIMARY_METRIC)
        axes[1].set_xlabel("(b) Family G: offered load", labelpad=2)
        handles, labels = axes[1].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=6, bbox_to_anchor=(0.5, 1.13), frameon=False,
                   handlelength=1.2, columnspacing=1.0, handletextpad=0.4)
        _save(fig, "paper_fig_overview")


def paper_fig_demo(npz_path: str, cell: int = 0, start: int = 6000, length: int = 600):
    if not os.path.exists(npz_path):
        return
    d = np.load(npz_path)
    sl = slice(start, start + length)
    t_ms = np.arange(length) * 0.5
    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(2, 1, figsize=(3.45, 2.15), sharex=True, gridspec_kw={"hspace": 0.1,
                                                                                      "height_ratios": [1.3, 1]})
        ax = axes[0]
        ax.fill_between(t_ms, 0, d["fh_demand"][cell, sl] / 1e6, color="lightgray", lw=0, label="arrivals")
        for m in ("queue_aware", "point_forecast", "proposed"):
            ax.step(t_ms, d[f"{m}_budget"][cell, sl] / 1e6, where="post", color=COLORS[m], lw=0.9,
                    label=PAPER_SHORT[m])
        ax.set_ylabel("Mbit / slot")
        ax.set_ylim(0, 1.45 * max(float(d[f"{m}_budget"][cell, sl].max()) for m in ("queue_aware", "proposed")) / 1e6)
        ax.legend(ncol=2, loc="upper left", frameon=False, handlelength=1.4)
        ax.grid(alpha=0.3, lw=0.5)
        ax.tick_params(length=2, pad=1.5)
        ax = axes[1]
        for m in ("queue_aware", "point_forecast", "proposed"):
            ax.plot(t_ms, np.cumsum(d[f"{m}_violated"][cell, sl]) / 1e6, color=COLORS[m], lw=0.9)
        ax.set_ylabel("Violated [Mbit]")
        ax.set_xlabel("time [ms]", labelpad=1)
        ax.grid(alpha=0.3, lw=0.5)
        ax.tick_params(length=2, pad=1.5)
        _save(fig, "paper_fig_demo")


def main():
    main_path = os.path.join(RESULTS_DIR, "main_runs.csv")
    if os.path.exists(main_path):
        df = pd.read_csv(main_path)
        paper_fig_overview(df)
        fig_tgpp(df)
        # the synthetic-family figures exclude the two reference-only controllers added for the paper
        df = df[~df.method.isin(["oracle_kkt", "proposed_transfer"])]
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
    comp_path = os.path.join(RESULTS_DIR, "compression_runs.csv")
    if os.path.exists(comp_path):
        fig_compression(pd.read_csv(comp_path))
    for name, fn in (("miscalibration_runs.csv", fig_miscalibration), ("delay_runs.csv", fig_delay)):
        pth = os.path.join(RESULTS_DIR, name)
        if os.path.exists(pth):
            fn(pd.read_csv(pth))
    fig_forecast_quality(os.path.join(RESULTS_DIR, "forecast_training_T20_d2.json"))
    fig_demo(os.path.join(RESULTS_DIR, "demo_timeseries.npz"))
    paper_fig_demo(os.path.join(RESULTS_DIR, "demo_timeseries.npz"))


if __name__ == "__main__":
    main()
