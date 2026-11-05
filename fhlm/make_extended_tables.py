"""Generate the tables, macros and figure copies for the extended manuscript (paper/extended/main.tex).

    python -m fhlm.make_extended_tables

The extended study keeps every run of the NCC manuscript and adds the Markov-modulated family, the
model-based and predictive-MaxWeight controllers and the theory validation. All numbers quoted in the
extended text come from the macros written here (prefix \\x to avoid clashes with paper/generated/macros.tex).
"""
from __future__ import annotations

import json
import os
import re
import shutil

import numpy as np
import pandas as pd

from .run_experiments import RESULTS_DIR, METHOD_ORDER, PRIMARY_METRIC, paired_analysis, REFERENCE_METHODS
from .make_paper_tables import TEX, SC, SC_HEAD, TGPP, TGPP_HEAD, _sgn, _num, _m, _csv, SHORT_TEX

OUT = os.path.join("paper", "extended", "generated")
PAPER_DIR = os.path.join("paper", "extended")
FIG_SRC = os.path.join(RESULTS_DIR, "figures")
MM = ["mm_moderate", "mm_high", "mm_shift"]
MM_HEAD = {"mm_moderate": "Mod. 0.65", "mm_high": "High 0.80", "mm_shift": "Shift 0.80"}
FAMILY_SCEN = {"S": SC, "G": TGPP, "M": MM}
ALL_SCEN = SC + TGPP + MM
REF = set(REFERENCE_METHODS) | {"proposed_transfer"}
TEX = {**TEX, "proposed": "Proposed (GBM + KKT)"}
NAME = {**TEX, **{k: v for k, v in SHORT_TEX.items() if k != "proposed"}}


def _w(name: str, text: str):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        f.write(text)
    print("wrote", os.path.join(OUT, name))


def _mkey(s: str) -> str:
    return s.replace("_", "")


def _star(p):
    return "$^{\\ast\\ast}$" if p < 0.01 else ("$^{\\ast}$" if p < 0.05 else "")


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------
def tab_family(df: pd.DataFrame, scen, head, paired=None, paired_scen=None, metric=PRIMARY_METRIC) -> str:
    """V_w (mean +- std) per scenario for every controller; optional paired column vs the proposed rule."""
    d = df[df.scenario.isin(scen)]
    g = d.groupby(["scenario", "method"])[metric].agg(["mean", "std"])
    methods = [m for m in METHOD_ORDER if all((s, m) in g.index for s in scen)]
    ncol = len(scen) + (1 if paired is not None else 0)
    lines = ["\\begin{tabular}{l" + "c" * ncol + "}", "\\hline",
             "Controller & " + " & ".join(head[s] for s in scen) +
             (f" & $\\Delta$ (wins)" if paired is not None else "") + " \\\\", "\\hline"]
    for m in methods:
        cells = [f"{g.loc[(s, m), 'mean'] * 100:.2f}$\\pm${g.loc[(s, m), 'std'] * 100:.2f}" for s in scen]
        if paired is not None:
            r = paired[(paired.scenario == paired_scen) & (paired.baseline == m)]
            if len(r):
                r = r.iloc[0]
                cells.append(f"{_sgn(-r.rel_reduction_pct)} ({int(r.reference_wins)}){_star(r.wilcoxon_p_holm)}")
            else:
                cells.append("--")
        if m in ("markov_oracle_kkt", "oracle") and methods.index(m) > 0 and methods[methods.index(m) - 1] not in REF:
            lines.append("\\hline")
        lines.append(f"{NAME[m]} & " + " & ".join(cells) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_head_to_head(df: pd.DataFrame, a: str = "proposed", others=("pred_maxweight", "cem_policy", "markov_kkt")) -> str:
    """The proposed rule against the strongest new comparators on every scenario of the three families."""
    others = [b for b in others if b in df.method.unique()]
    paired = paired_analysis(df[df.method.isin([a] + others)], reference=a)
    heads = {**{k: "S " + v for k, v in SC_HEAD.items()}, **{k: "G " + v for k, v in TGPP_HEAD.items()},
             **{k: "M " + v for k, v in MM_HEAD.items()}}
    impl = df[~df.method.isin(REF)].groupby(["scenario", "method"])[PRIMARY_METRIC].mean()
    lines = ["\\begin{tabular}{lc" + "cc" * len(others) + "l}", "\\hline",
             "Scenario & " + NAME[a] + " & " + " & ".join(f"\\multicolumn{{2}}{{c}}{{{NAME[b]}}}" for b in others) +
             " & best implementable \\\\",
             " & $V_w$ & " + " & ".join("$V_w$ & $\\Delta$ [95\\,\\% CI], wins" for _ in others) + " & \\\\", "\\hline"]
    for s in ALL_SCEN:
        if s not in impl.index.get_level_values(0):
            continue
        ra = paired[(paired.scenario == s) & (paired.baseline == others[0])]
        if not len(ra):
            continue
        cells = [f"{ra.iloc[0].reference_mean * 100:.2f}"]
        for b in others:
            r = paired[(paired.scenario == s) & (paired.baseline == b)]
            if not len(r):
                cells += ["--", "--"]
                continue
            r = r.iloc[0]
            cells += [f"{r.baseline_mean * 100:.2f}",
                      f"{_sgn(-r.rel_reduction_pct)} [{_sgn(-r.rel_ci_hi_pct)}, {_sgn(-r.rel_ci_lo_pct)}]{_star(r.wilcoxon_p_holm)} "
                      f"{int(r.reference_wins)}/{int(r.n_seeds)}"]
        best = impl.loc[s].idxmin()
        cells.append(NAME[best])
        lines.append(f"{heads[s]} & " + " & ".join(cells) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_sweep_ext(sw: pd.DataFrame) -> str:
    g = sw.groupby(["interval_slots", "method"])[PRIMARY_METRIC].mean()
    Ts = sorted(sw.interval_slots.unique())
    methods = [m for m in METHOD_ORDER if all((T, m) in g.index for T in Ts)]
    lines = ["\\begin{tabular}{l" + "c" * len(Ts) + "}", "\\hline",
             "Controller $\\backslash$ $T$ & " + " & ".join(f"{T * 0.5:g} ms" for T in Ts) + " \\\\", "\\hline"]
    for m in methods:
        if m == "oracle":
            lines.append("\\hline")
        lines.append(f"{NAME[m]} & " + " & ".join(f"{g.loc[(T, m)] * 100:.2f}" for T in Ts) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_weights_ext(wt: pd.DataFrame, scenarios) -> str:
    """LL-weight sweep for several scenarios side by side."""
    g = wt.groupby(["scenario", "ll_priority", "method"])[PRIMARY_METRIC].mean()
    ws = sorted(wt.ll_priority.unique())
    scen = [s for s in scenarios if s in wt.scenario.unique()]
    methods = [m for m in METHOD_ORDER if all((s, w, m) in g.index for s in scen for w in ws)]
    heads = {**SC_HEAD, **TGPP_HEAD, **MM_HEAD}
    fam = {**{s: "S" for s in SC}, **{s: "G" for s in TGPP}, **{s: "M" for s in MM}}
    lines = ["\\begin{tabular}{l" + ("|" + "c" * len(ws)) * len(scen) + "}", "\\hline",
             "& " + " & ".join(f"\\multicolumn{{{len(ws)}}}{{c}}{{Family {fam[s]}, {heads[s]}}}" for s in scen) + " \\\\",
             "Controller $\\backslash$ $w_{\\mathrm{LL}}$ & " + " & ".join(" & ".join(f"{w:g}" for w in ws) for _ in scen) + " \\\\",
             "\\hline"]
    for m in methods:
        if m == "oracle":
            lines.append("\\hline")
        cells = [f"{g.loc[(s, w, m)] * 100:.2f}" for s in scen for w in ws]
        lines.append(f"{NAME[m]} & " + " & ".join(cells) + " \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def tab_theory(rep: dict) -> str:
    lines = ["\\begin{tabular}{lccccc}", "\\hline",
             "Cell ($D$ slots) & tail prob. $p$ & $x_p/\\bar d$ & union bound $U(x_p)$ & $U(x_p)/p$ & $\\ell$/drops, drops/$u$ \\\\",
             "\\hline"]
    for name, c in rep["cells"].items():
        probs = c["quantile_probs"]
        shown = [p for p in (0.1, 0.01, 0.001) if p in probs]
        for i, p in enumerate(shown):
            j = probs.index(p)
            lab = f"{name} ({c['deadline_slots']})" if i == 0 else ""
            sand = (f"{c['sandwich_lower_over_drops_mean']:.2f} / {c['sandwich_drops_over_upper_mean']:.2f}" if i == 0 else "")
            lines.append(f"{lab} & {p:g} & {c['x'][j] / c['mean_rate']:.2f} & {c['chernoff_union_bound'][j]:.3f} & "
                         f"{c['bound_over_empirical'][j]:.0f} & {sand} \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def _epoch_metrics(fcs: dict, traces, net, ctrl):
    """Forecast-quality metrics of several forecasters on the decision epochs of `traces` (same protocol as
    ``WindowQuantileForecaster.evaluate_on_traces``)."""
    from .forecast import forecast_metrics, NUM_LAG_INTERVALS, _scale
    from .simulator import Observation
    from .demand import required_rates
    T, tau = ctrl.interval_slots, ctrl.telemetry_delay_slots
    deadlines = np.array([c.deadline_slots for c in net.cells])
    scale = _scale(net)
    Q = {k: [] for k in fcs}
    Y = []
    for tr in traces:
        for t in range((NUM_LAG_INTERVALS + 1) * (T + tau) + tau, tr.num_slots - T, 2 * T):
            o = t - tau
            obs = Observation(slot=t, obs_slot=o, queue_bits=np.zeros(net.num_cells), hol_age=np.zeros(net.num_cells),
                              se=tr.se[:, o], history_fh_demand=tr.fh_demand_bits[:, :o],
                              history_arrivals=tr.arrivals_bits[:, :o], prev_budgets=np.zeros(net.num_cells),
                              net=net, ctrl=ctrl)
            for k, f in fcs.items():
                Q[k].append(f.predict_quantiles(obs) / scale[:, None])
            Y.append(required_rates(tr.fh_demand_bits[:, o:t + T], deadlines) / scale)
    y = np.concatenate(Y)
    return {k: forecast_metrics(np.vstack(Q[k]), y, fcs[k].quantiles) for k in fcs}


def forecast_quality_table(macros: str):
    """Forecast quality of the learned, window, Markov-fitted and (Family M) Markov-oracle forecasters on the
    validation seeds of every family."""
    from .scenarios import VAL_SEEDS, VAL_SCENARIOS_BY_FAMILY, make_config
    from .traffic import generate_traffic
    from .forecast import WindowQuantileForecaster, QuantileGBMForecaster
    from .markov import MarkovChainForecaster, MarkovOracleForecaster
    from .traffic_markov import build_sources
    from .run_experiments import model_path
    rows = []
    for fam, label in (("synthetic", "S"), ("3gpp", "G"), ("markov", "M")):
        mp = model_path(20, 2, fam)
        if not os.path.exists(mp):
            continue
        tun_path = os.path.join(RESULTS_DIR, f"tuning{'' if fam == 'synthetic' else '_' + fam}.json")
        tun = json.load(open(tun_path))["selected"] if os.path.exists(tun_path) else {}
        mk = tun.get("markov_kkt", {})
        acc = {}
        for sc in VAL_SCENARIOS_BY_FAMILY[fam]:
            for seed in VAL_SEEDS:
                cfg = make_config(sc, seed)
                tr = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
                fcs = {"GBM (learned)": QuantileGBMForecaster.load(mp), "window quantiles": WindowQuantileForecaster(),
                       "fitted Markov chain": MarkovChainForecaster(K=mk.get("K", 3), window=mk.get("window", 2000),
                                                                    n_paths=200)}
                if fam == "markov":
                    fcs["true Markov model"] = MarkovOracleForecaster(build_sources(cfg.network, cfg.traffic),
                                                                       cfg.network, n_paths=200)
                res = _epoch_metrics(fcs, [tr], cfg.network, cfg.control)
                for k, m in res.items():
                    acc.setdefault(k, []).append(m)
        for k, ms in acc.items():
            m = {key: float(np.mean([x[key] for x in ms])) for key in ms[0]}
            rows.append({"family": label, "forecaster": k, **m})
            key = f"xfq{label}" + re.sub(r"[^A-Za-z]", "", k)
            macros += _m(key + "Pinball", f"{m['pinball_mean'] * 100:.2f}")
            macros += _m(key + "Cov", f"{100 * m['coverage_q05']:.0f}/{100 * m['coverage_q50']:.0f}/{100 * m['coverage_q95']:.0f}")
            macros += _m(key + "Mae", f"{100 * m['median_mae_rel']:.0f}")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS_DIR, "forecast_quality_ext.csv"), index=False)
    lines = ["\\begin{tabular}{llcccc}", "\\hline",
             "Family & Forecaster & pinball$\\times$100 & cov. 5/50/95 & 90\\,\\% PI cov. & med. rel. err. (\\%) \\\\",
             "\\hline"]
    for fam in ("S", "G", "M"):
        d = df[df.family == fam]
        for i, (_, r) in enumerate(d.iterrows()):
            lines.append(f"{fam if i == 0 else ''} & {r.forecaster} & {r.pinball_mean * 100:.2f} & "
                         f"{100 * r.coverage_q05:.0f}/{100 * r.coverage_q50:.0f}/{100 * r.coverage_q95:.0f} & "
                         f"{100 * r.interval90_coverage:.0f} & {100 * r.median_mae_rel:.0f} \\\\")
        if len(d):
            lines.append("\\hline")
    lines.append("\\end{tabular}")
    return "\n".join(lines) + "\n", macros


# ---------------------------------------------------------------------------
def main(with_forecast_quality: bool = True):
    macros = ""
    main_df = _csv("main_runs.csv")
    if main_df is not None:
        paired = paired_analysis(main_df, reference="proposed")
        paired.to_csv(os.path.join(RESULTS_DIR, "main_paired_ext.csv"), index=False)
        for fam, scen in FAMILY_SCEN.items():
            if not main_df.scenario.isin(scen).any():
                continue
            d = main_df[main_df.scenario.isin(scen)]
            hs = {**SC_HEAD, **TGPP_HEAD, **MM_HEAD}
            high = {"S": "high", "G": "tgpp_high", "M": "mm_high"}[fam]
            _w(f"tab_main_{fam}.tex", tab_family(main_df, scen, hs, paired, high))
            macros += _m(f"xnSeeds{fam}", str(d.seed.nunique()))
            macros += _m(f"xnMethods{fam}", str(d.method.nunique()))
            macros += _m(f"xnRuns{fam}", str(len(d)))
            for s in scen:
                macros += _m(f"xload{_mkey(s)}", f"{d[d.scenario == s].realised_load.mean():.2f}")
        _w("tab_head_to_head.tex", tab_head_to_head(main_df))
        g = main_df.groupby(["scenario", "method"])
        gm = g[PRIMARY_METRIC].mean()
        for s in ALL_SCEN:
            for m in METHOD_ORDER:
                if (s, m) in gm.index:
                    key = f"xmean{_mkey(s)}{_mkey(m)}"
                    macros += _m(key, f"{gm.loc[(s, m)] * 100:.2f}")
                    for met, short in (("violation_ratio_ll", "LL"), ("violation_ratio_embb", "EMBB"),
                                       ("fh_utilisation", "Util"), ("violation_ratio", "Unw"),
                                       ("fh_unused_allocation_fraction", "Unused")):
                        macros += _m(key + short, f"{g[met].mean().loc[(s, m)] * 100:.1f}")
        for _, r in paired.iterrows():
            key = f"xred{_mkey(r.scenario)}{_mkey(r.baseline)}"
            macros += _m(key, f"{r.rel_reduction_pct:.0f}")
            macros += _m(key + "Wins", f"{int(r.reference_wins)}/{int(r.n_seeds)}")
            macros += _m(key + "P", f"{r.wilcoxon_p_holm:.3f}" if np.isfinite(r.wilcoxon_p_holm) else "n/a")
            macros += _m(key + "CI", f"[{r.rel_ci_lo_pct:.0f}, {r.rel_ci_hi_pct:.0f}]")
        # best implementable controller per scenario and how often each wins
        impl = main_df[~main_df.method.isin(REF)]
        best = impl.groupby(["scenario", "method"])[PRIMARY_METRIC].mean()
        wins = {}
        for s in ALL_SCEN:
            if s in best.index.get_level_values(0):
                b = best.loc[s].idxmin()
                macros += _m(f"xbest{_mkey(s)}", NAME[b])
                wins[b] = wins.get(b, 0) + 1
        for m, k in wins.items():
            macros += _m(f"xwins{_mkey(m)}", str(k))
        macros += _m("xnScenarios", str(sum(s in best.index.get_level_values(0) for s in ALL_SCEN)))
        # gap to the Markov oracle on Family M
        for s in MM:
            if (s, "markov_oracle_kkt") in gm.index and (s, "proposed") in gm.index:
                a, b = gm.loc[(s, "proposed")], gm.loc[(s, "markov_oracle_kkt")]
                macros += _m(f"xgapMarkovOracle{_mkey(s)}", f"{100 * (a - b) / a:.0f}")
            if (s, "oracle_kkt") in gm.index and (s, "proposed") in gm.index:
                a, b = gm.loc[(s, "proposed")], gm.loc[(s, "oracle_kkt")]
                macros += _m(f"xgapKKT{_mkey(s)}", f"{100 * (a - b) / a:.0f}")
        dt = main_df.groupby("method")["decision_time_ms_mean"].mean()
        for m in METHOD_ORDER:
            if m in dt:
                macros += _m(f"xdt{_mkey(m)}", f"{dt[m]:.1f}")
    sw = _csv("sweep_runs.csv")
    if sw is not None:
        _w("tab_sweep.tex", tab_sweep_ext(sw))
        g = sw.groupby(["interval_slots", "method"])[PRIMARY_METRIC].mean()
        macros += _m("xnSeedsSweep", str(sw.seed.nunique()))
        for T in sorted(sw.interval_slots.unique()):
            for m in METHOD_ORDER:
                if (T, m) in g.index:
                    macros += _m(f"xsweepT{T}{_mkey(m)}", f"{g.loc[(T, m)] * 100:.2f}")
            if (T, "pred_maxweight") in g.index and (T, "proposed") in g.index:
                red = 100 * (g.loc[(T, "pred_maxweight")] - g.loc[(T, "proposed")]) / g.loc[(T, "pred_maxweight")]
                macros += _m(f"xsweepT{T}predRed", _num(red))
    dl = _csv("delay_runs.csv")
    if dl is not None:
        g = dl.groupby(["telemetry_delay_slots", "method"])[PRIMARY_METRIC].mean()
        for tau in sorted(dl.telemetry_delay_slots.unique()):
            for m in METHOD_ORDER:
                if (tau, m) in g.index:
                    macros += _m(f"xdelayTau{tau}{_mkey(m)}", f"{g.loc[(tau, m)] * 100:.2f}")
    comp = _csv("compression_runs.csv")
    if comp is not None:
        g = comp.groupby(["mantissa_bits", "method"])[PRIMARY_METRIC].mean()
        for b in sorted(comp.mantissa_bits.unique()):
            for m in METHOD_ORDER:
                if (b, m) in g.index:
                    macros += _m(f"xcompB{b}{_mkey(m)}", f"{g.loc[(b, m)] * 100:.2f}")
    wt = _csv("weights_runs.csv")
    if wt is not None:
        _w("tab_weights.tex", tab_weights_ext(wt, ["high", "tgpp_high", "mm_high"]))
        g = wt.groupby(["scenario", "ll_priority", "method"])[PRIMARY_METRIC].mean()
        macros += _m("xnSeedsWeights", str(wt.seed.nunique()))
        for (s, w, m), v in g.items():
            macros += _m(f"xwt{_mkey(s)}W{w:g}{_mkey(m)}", f"{v * 100:.2f}")
    tv = os.path.join(RESULTS_DIR, "theory_validation.json")
    if os.path.exists(tv):
        rep = json.load(open(tv))
        _w("tab_theory.tex", tab_theory(rep))
        for name, c in rep["cells"].items():
            k = "xth" + re.sub(r"[^A-Za-z]", "", name)
            probs = c["quantile_probs"]
            for p, lab in ((0.01, "One"), (0.001, "Tenth")):
                j = probs.index(p)
                macros += _m(k + "Ratio" + lab, f"{c['bound_over_empirical'][j]:.0f}")
                macros += _m(k + "Bound" + lab, f"{c['chernoff_union_bound'][j]:.3f}")
            macros += _m(k + "SandLo", f"{c['sandwich_lower_over_drops_mean']:.2f}")
            macros += _m(k + "SandHi", f"{c['sandwich_drops_over_upper_mean']:.2f}")
            macros += _m(k + "RstarMean", f"{c['rstar_over_mean_median']:.2f}")
    lamd = os.path.join(RESULTS_DIR, "lambda_diagnostic.json")
    if os.path.exists(lamd):
        for sc, suf in (("high", "S"), ("tgpp_high", "G"), ("mm_high", "M")):
            d = json.load(open(lamd)).get(sc)
            if d:
                macros += _m(f"xlamFloor{suf}", f"{100 * d['frac_embb_at_floor']:.0f}")
                macros += _m(f"xlamBind{suf}", f"{100 * d['frac_binding']:.0f}")
                macros += _m(f"xlamLLlevel{suf}", f"{100 * d['ll_level_at_median_lambda']:.0f}")
    for fam, suf in (("", "S"), ("_3gpp", "G"), ("_markov", "M")):
        fc = os.path.join(RESULTS_DIR, f"forecast_training_T20_d2{fam}.json")
        if os.path.exists(fc):
            r = json.load(open(fc))
            v = r["gbm_validation"]
            macros += _m(f"xcov{suf}", f"{100 * v['coverage_q05']:.0f}/{100 * v['coverage_q50']:.0f}/{100 * v['coverage_q95']:.0f}")
            macros += _m(f"xmae{suf}", f"{100 * v['median_mae_rel']:.0f}")
            macros += _m(f"xmaePersist{suf}", f"{100 * r['persistence_median_mae_rel']:.0f}")
            macros += _m(f"xnTrainRows{suf}", f"{r['train_rows']:,}")
        cem = os.path.join(RESULTS_DIR, f"cem_policy{fam}.json")
        if os.path.exists(cem):
            c = json.load(open(cem))["selected"]
            macros += _m(f"xcem{suf}", f"$p_{{\\rm LL}}={c['p_ll']:.2f}$, $p_{{\\rm eMBB}}={c['p_embb']:.2f}$, $w_{{\\rm LL}}={c['w_ll']:.1f}$")
        tun = os.path.join(RESULTS_DIR, f"tuning{fam}.json")
        if os.path.exists(tun):
            sel = json.load(open(tun))["selected"]
            if "pred_maxweight" in sel:
                macros += _m(f"xpmwParams{suf}", f"margin {sel['pred_maxweight'].get('margin', 0):g}, lookahead {sel['pred_maxweight'].get('lookahead', 1):g}")
            if "proposed_tw" in sel:
                macros += _m(f"xtw{suf}", f"{sel['proposed_tw'].get('ll_weight', 3.0):g}")
            if "markov_kkt" in sel:
                macros += _m(f"xmkParams{suf}", f"$K={sel['markov_kkt'].get('K', 3)}$, window {sel['markov_kkt'].get('window', 2000) // 2} ms")
    if with_forecast_quality:
        tab, macros = forecast_quality_table(macros)
        _w("tab_forecast.tex", tab)
    _w("macros_ext.tex", macros)
    copy_figures()
    flatten()


def copy_figures():
    tex_path = os.path.join(PAPER_DIR, "main.tex")
    if not os.path.exists(tex_path):
        return
    tex = open(tex_path).read()
    dst = os.path.join(PAPER_DIR, "figures")
    names = re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", tex)
    os.makedirs(dst, exist_ok=True)
    for name in names:
        candidates = [name] if os.path.splitext(name)[1] else [name + ".pdf", name + ".png"]
        for cand in candidates:
            src = os.path.join(FIG_SRC, cand)
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(dst, cand))


def flatten():
    tex_path = os.path.join(PAPER_DIR, "main.tex")
    if not os.path.exists(tex_path):
        return
    tex = open(tex_path).read()

    def sub(m):
        path = os.path.join(PAPER_DIR, m.group(1))
        if not path.endswith(".tex"):
            path += ".tex"
        body = open(path).read().rstrip("\n")
        return f"% ---- inlined from {m.group(1)} ----\n{body}\n% ---- end {m.group(1)} ----\n"

    flat = re.sub(r"\\input\{([^}]+)\}", sub, tex)
    flat = "% AUTO-GENERATED by fhlm/make_extended_tables.py from main.tex -- edit main.tex, not this file.\n" + flat
    open(os.path.join(PAPER_DIR, "main_standalone.tex"), "w").write(flat)


if __name__ == "__main__":
    main()
