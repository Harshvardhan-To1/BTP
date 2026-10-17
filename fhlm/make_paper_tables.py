"""Generate LaTeX tables and number macros for paper/main.tex from results/fhlm/*.csv.

    python -m fhlm.make_paper_tables

Every number that appears in the paper text is emitted as a macro in
paper/generated/macros.tex so that the manuscript cannot drift from the data.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from .run_experiments import RESULTS_DIR, METHOD_ORDER, PRIMARY_METRIC, paired_analysis

OUT = os.path.join("paper", "generated")
SC = ["low", "moderate", "high", "overload_bursts", "shift"]
SC_HEAD = {"low": "Low 0.50", "moderate": "Mod. 0.65", "high": "High 0.80", "overload_bursts": "Flash", "shift": "Shift"}
TEX = {
    "static_equal": "Static equal share",
    "reactive_prop": "Reactive proportional",
    "maxweight": "MaxWeight (drift)",
    "queue_aware": "Deadline-aware reactive",
    "point_forecast": "Point forecast + WF",
    "fixed_quantile": "Fixed quantile + WF",
    "proposed_window": "Proposed, window quantiles",
    "proposed": "\\textbf{Proposed (GBM + KKT)}",
    "proposed_cal": "Proposed + ACI",
    "oracle": "Oracle water-fill",
}


def _w(name: str, text: str):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        f.write(text)
    print("wrote", os.path.join(OUT, name))


def _csv(name):
    p = os.path.join(RESULTS_DIR, name)
    return pd.read_csv(p) if os.path.exists(p) else None


_DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
           "8": "eight", "9": "nine"}


def _m(key: str, val: str) -> str:
    # LaTeX macro names may only contain letters: spell digits out, drop everything else
    key = "".join(_DIGITS[ch] if ch.isdigit() else ch for ch in key if ch.isalnum())
    return f"\\newcommand{{\\{key}}}{{{val}}}\n"


def tab_main(df: pd.DataFrame) -> str:
    g = df.groupby(["scenario", "method"])[PRIMARY_METRIC].agg(["mean", "std"])
    best = {s: g.loc[s].drop(index="oracle", errors="ignore")["mean"].idxmin() for s in SC}
    lines = ["\\begin{tabular}{l" + "c" * len(SC) + "}", "\\hline",
             "Controller & " + " & ".join(SC_HEAD[s] for s in SC) + " \\\\", "\\hline"]
    for m in METHOD_ORDER:
        if m not in df.method.unique():
            continue
        cells = []
        for s in SC:
            mu, sd = g.loc[(s, m), "mean"] * 100, g.loc[(s, m), "std"] * 100
            txt = f"{mu:.2f} $\\pm$ {sd:.2f}"
            if best[s] == m:
                txt = f"\\textbf{{{txt}}}"
            cells.append(txt)
        name = TEX[m] if m != "proposed" else "Proposed (GBM + KKT)"
        if m == "oracle":
            lines.append("\\hline")
        lines.append(f"{name} & " + " & ".join(cells) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_paired(paired: pd.DataFrame, baselines) -> str:
    lines = ["\\begin{tabular}{l" + "c" * len(SC) + "}", "\\hline",
             "Proposed vs. & " + " & ".join(SC_HEAD[s] for s in SC) + " \\\\", "\\hline"]
    for b in baselines:
        cells = []
        for s in SC:
            r = paired[(paired.scenario == s) & (paired.baseline == b)]
            if not len(r):
                cells.append("--")
                continue
            r = r.iloc[0]
            p = r["wilcoxon_p_holm"]
            star = "$^{\\ast\\ast}$" if p < 0.01 else ("$^{\\ast}$" if p < 0.05 else "")
            cells.append(f"{-r.rel_reduction_pct:+.0f} [{-r.rel_ci_hi_pct:+.0f},{-r.rel_ci_lo_pct:+.0f}] "
                         f"{int(r.reference_wins)}/{int(r.n_seeds)}{star}")
        lines.append(f"{TEX[b]} & " + " & ".join(cells) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_sweep(sw: pd.DataFrame) -> str:
    g = sw.groupby(["interval_slots", "method"])[PRIMARY_METRIC].mean()
    Ts = sorted(sw.interval_slots.unique())
    methods = [m for m in METHOD_ORDER if m in sw.method.unique()]
    lines = ["\\begin{tabular}{l" + "c" * len(Ts) + "}", "\\hline",
             "Controller $\\backslash$ $T$ & " + " & ".join(f"{T * 0.5:g} ms" for T in Ts) + " \\\\", "\\hline"]
    for m in methods:
        lines.append(f"{TEX[m]} & " + " & ".join(f"{g.loc[(T, m)] * 100:.2f}" for T in Ts) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_delay(dl: pd.DataFrame) -> str:
    g = dl.groupby(["telemetry_delay_slots", "method"])[PRIMARY_METRIC].mean()
    taus = sorted(dl.telemetry_delay_slots.unique())
    methods = [m for m in METHOD_ORDER if m in dl.method.unique()]
    lines = ["\\begin{tabular}{l" + "c" * len(taus) + "}", "\\hline",
             "Controller $\\backslash$ $\\tau$ & " + " & ".join(f"{t * 0.5:g} ms" for t in taus) + " \\\\", "\\hline"]
    for m in methods:
        lines.append(f"{TEX[m]} & " + " & ".join(f"{g.loc[(t, m)] * 100:.2f}" for t in taus) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_misc(mis: pd.DataFrame) -> str:
    d = mis[mis.method == "proposed_miscal"]
    eps = sorted(d.eps.unique())
    scen = [s for s in SC if s in d.scenario.unique()]
    g = d.groupby(["scenario", "eps"])[PRIMARY_METRIC].mean()
    lines = ["\\begin{tabular}{l" + "c" * len(eps) + "}", "\\hline",
             "$\\epsilon$ & " + " & ".join(f"{e:+.1f}" for e in eps) + " \\\\", "\\hline"]
    for s in scen:
        lines.append(f"{SC_HEAD[s]} & " + " & ".join(f"{g.loc[(s, e)] * 100:.2f}" for e in eps) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_compression(comp: pd.DataFrame) -> str:
    g = comp.groupby(["mantissa_bits", "method"])[PRIMARY_METRIC].mean()
    load = comp.groupby("mantissa_bits")["realised_load"].mean()
    widths = sorted(comp.mantissa_bits.unique())
    methods = [m for m in METHOD_ORDER if m in comp.method.unique()]
    lines = ["\\begin{tabular}{l" + "c" * len(widths) + "}", "\\hline",
             "BFP mantissa bits & " + " & ".join(str(b) for b in widths) + " \\\\",
             "Offered load & " + " & ".join(f"{load[b]:.2f}" for b in widths) + " \\\\", "\\hline"]
    for m in methods:
        lines.append(f"{TEX[m]} & " + " & ".join(f"{g.loc[(b, m)] * 100:.2f}" for b in widths) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def main():
    main_df = _csv("main_runs.csv")
    macros = ""
    if main_df is not None:
        paired = paired_analysis(main_df, reference="proposed")
        paired.to_csv(os.path.join(RESULTS_DIR, "main_paired.csv"), index=False)
        _w("tab_main.tex", tab_main(main_df))
        bl = [m for m in ("reactive_prop", "maxweight", "queue_aware", "point_forecast", "fixed_quantile",
                          "proposed_window", "proposed_cal") if m in main_df.method.unique()]
        _w("tab_paired.tex", tab_paired(paired, bl))
        n = main_df.seed.nunique()
        macros += _m("nSeeds", str(n))
        macros += _m("nRuns", str(len(main_df)))
        macros += _m("nMethods", str(main_df.method.nunique()))
        g = main_df.groupby(["scenario", "method"])
        for s in SC:
            for m in METHOD_ORDER:
                if (s, m) in g.groups:
                    key = f"mean{s.replace('_', '')}{m.replace('_', '')}"
                    macros += _m(key, f"{g[PRIMARY_METRIC].mean().loc[(s, m)] * 100:.2f}")
                    for met, short in (("violation_ratio_ll", "LL"), ("violation_ratio_embb", "EMBB"),
                                       ("fh_utilisation", "Util")):
                        macros += _m(key + short, f"{g[met].mean().loc[(s, m)] * 100:.1f}")
        for _, r in paired.iterrows():
            key = f"red{r.scenario.replace('_', '')}{r.baseline.replace('_', '')}"
            macros += _m(key, f"{r.rel_reduction_pct:.0f}")
            macros += _m(key + "Wins", f"{int(r.reference_wins)}/{int(r.n_seeds)}")
            macros += _m(key + "P", f"{r.wilcoxon_p_holm:.3f}" if np.isfinite(r.wilcoxon_p_holm) else "n/a")
            macros += _m(key + "CI", f"[{r.rel_ci_lo_pct:.0f}, {r.rel_ci_hi_pct:.0f}]")
        pf = paired[paired.baseline == "point_forecast"]
        macros += _m("redPFmin", f"{pf.rel_reduction_pct.min():.0f}")
        macros += _m("redPFmax", f"{pf.rel_reduction_pct.max():.0f}")
        qa = paired[paired.baseline == "queue_aware"]
        macros += _m("redQAmin", f"{qa.rel_reduction_pct.min():.0f}")
        macros += _m("redQAmax", f"{qa.rel_reduction_pct.max():.0f}")
        dt = main_df.groupby("method")["decision_time_ms_mean"].mean()
        for m in METHOD_ORDER:
            if m in dt:
                macros += _m(f"dt{m.replace('_', '')}", f"{dt[m]:.2f}")
    sw = _csv("sweep_runs.csv")
    if sw is not None:
        _w("tab_sweep.tex", tab_sweep(sw))
        macros += _m("nSeedsSweep", str(sw.seed.nunique()))
        g = sw.groupby(["interval_slots", "method"])[PRIMARY_METRIC].mean()
        for T in sorted(sw.interval_slots.unique()):
            for b in ("queue_aware", "reactive_prop", "oracle"):
                if (T, b) in g and (T, "proposed") in g:
                    red = 100 * (g.loc[(T, b)] - g.loc[(T, "proposed")]) / g.loc[(T, b)]
                    macros += _m(f"sweepT{T}{b.replace('_', '')}", f"{red:+.0f}")
    dl = _csv("delay_runs.csv")
    if dl is not None:
        _w("tab_delay.tex", tab_delay(dl))
        macros += _m("nSeedsDelay", str(dl.seed.nunique()))
        g = dl.groupby(["telemetry_delay_slots", "method"])[PRIMARY_METRIC].mean()
        for tau in sorted(dl.telemetry_delay_slots.unique()):
            for b in ("queue_aware", "reactive_prop", "point_forecast"):
                if (tau, b) in g and (tau, "proposed") in g:
                    red = 100 * (g.loc[(tau, b)] - g.loc[(tau, "proposed")]) / g.loc[(tau, b)]
                    macros += _m(f"delayTau{tau}{b.replace('_', '')}", f"{red:.0f}")
    mis = _csv("miscalibration_runs.csv")
    if mis is not None:
        _w("tab_misc.tex", tab_misc(mis))
        macros += _m("nSeedsMisc", str(mis.seed.nunique()))
        d = mis[mis.method == "proposed_miscal"]
        g = d.groupby(["scenario", "eps"])[PRIMARY_METRIC].mean()
        for s in d.scenario.unique():
            base = g.loc[(s, 0.0)]
            worst = g.loc[s].max()
            macros += _m(f"misc{s.replace('_', '')}Base", f"{base * 100:.2f}")
            macros += _m(f"misc{s.replace('_', '')}Worst", f"{worst * 100:.2f}")
            macros += _m(f"misc{s.replace('_', '')}WorstRel", f"{100 * (worst - base) / base:.0f}")
            macros += _m(f"misc{s.replace('_', '')}Under", f"{g.loc[(s, min(g.loc[s].index))] * 100:.2f}")
            for b in ("point_forecast", "queue_aware"):
                v = mis[(mis.method == b) & (mis.scenario == s)][PRIMARY_METRIC].mean()
                macros += _m(f"misc{s.replace('_', '')}{b.replace('_', '')}", f"{v * 100:.2f}")
    comp = _csv("compression_runs.csv")
    if comp is not None:
        _w("tab_compression.tex", tab_compression(comp))
        macros += _m("nSeedsComp", str(comp.seed.nunique()))
    tun = os.path.join(RESULTS_DIR, "tuning.json")
    if os.path.exists(tun):
        sel = json.load(open(tun))["selected"]
        if "fixed_quantile" in sel:
            macros += _m("fixedQuantileLevel", f"{sel['fixed_quantile'].get('level', 0.9):.2f}")
        if "maxweight" in sel:
            mw = sel["maxweight"]
            macros += _m("maxweightParams", f"margin {mw.get('margin', 0.0):g}, head-of-line-age weight {mw.get('hol_weight', 0.0):g}")
    fc = os.path.join(RESULTS_DIR, "forecast_training_T20_d2.json")
    if os.path.exists(fc):
        r = json.load(open(fc))
        v = r["gbm_validation"]
        macros += _m("covFive", f"{100 * v['coverage_q05']:.1f}")
        macros += _m("covFifty", f"{100 * v['coverage_q50']:.1f}")
        macros += _m("covNinetyFive", f"{100 * v['coverage_q95']:.1f}")
        macros += _m("maeGBM", f"{100 * v['median_mae_rel']:.0f}")
        macros += _m("maePersist", f"{100 * r['persistence_median_mae_rel']:.0f}")
        if "train_rows" in r:
            macros += _m("nTrainRows", f"{r['train_rows']:,}")
    _w("macros.tex", macros)
    copy_figures()
    flatten()


PAPER_DIR = os.path.dirname(OUT)
FIG_SRC = os.path.join(RESULTS_DIR, "figures")


def copy_figures():
    """Copy the figures referenced by main.tex into paper/figures so the paper folder is self-contained."""
    import re
    import shutil
    tex = open(os.path.join(PAPER_DIR, "main.tex")).read()
    dst = os.path.join(PAPER_DIR, "figures")
    os.makedirs(dst, exist_ok=True)
    for name in re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", tex):
        src = os.path.join(FIG_SRC, name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, name))
            print("copied", src, "->", dst)


def flatten():
    """Write main_standalone.tex with every \\input inlined (single-file upload for Overleaf etc.)."""
    import re
    tex = open(os.path.join(PAPER_DIR, "main.tex")).read()

    def sub(m):
        path = os.path.join(PAPER_DIR, m.group(1))
        if not path.endswith(".tex"):
            path += ".tex"
        body = open(path).read().rstrip("\n")
        return f"% ---- inlined from {m.group(1)} ----\n{body}\n% ---- end {m.group(1)} ----\n"

    flat = re.sub(r"\\input\{([^}]+)\}", sub, tex)
    flat = "% AUTO-GENERATED by fhlm/make_paper_tables.py from main.tex -- edit main.tex, not this file.\n" + flat
    out = os.path.join(PAPER_DIR, "main_standalone.tex")
    open(out, "w").write(flat)
    print("wrote", out)


if __name__ == "__main__":
    main()
