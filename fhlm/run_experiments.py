"""Experiment runner: validation tuning, main comparison, interval sweep, demo.

    python -m fhlm.run_experiments tune      # pick safety margins on VALIDATION seeds
    python -m fhlm.run_experiments main      # all methods x test scenarios x test seeds
    python -m fhlm.run_experiments sweep     # control-interval sweep (trains per-T forecasters)
    python -m fhlm.run_experiments compression  # BFP width (Part A lever) x allocation rule (Part B lever)
    python -m fhlm.run_experiments demo      # one run with time series for the demo figure

Every method in a comparison sees exactly the same traffic trace (same seed),
the same capacity and the same delayed observations.
Raw per-run metrics are written to results/fhlm/raw/*.json, aggregates to
results/fhlm/*.csv.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
import time
from multiprocessing import Pool
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd

from .scenarios import (SCENARIOS, TEST_SEEDS, VAL_SEEDS, VAL_SCENARIOS, make_config, DEFAULT_SLOTS, DEFAULT_WARMUP)
from .traffic import generate_traffic
from .simulator import run_simulation
from .controllers import (StaticEqualShare, ReactiveProportional, QueueAwareReactive, PointForecastWaterfill,
                          OracleWaterfill,
                          MaxWeightReactive, FixedQuantileWaterfill)
from .proposed import UncertaintyAwareAllocator
from .forecast import QuantileGBMForecaster, WindowQuantileForecaster

RESULTS_DIR = "results/fhlm"
RAW_DIR = os.path.join(RESULTS_DIR, "raw")
MODEL_DIR = "models"

PRIMARY_METRIC = "weighted_violation_ratio"

# method name -> (constructor, needs_forecaster)
METHOD_ORDER = ["static_equal", "reactive_prop", "maxweight", "queue_aware", "point_forecast", "fixed_quantile",
                "proposed_window", "proposed", "proposed_cal", "oracle"]
METHOD_LABELS = {
    "static_equal": "Static equal share",
    "reactive_prop": "Reactive proportional (EWMA)",
    "maxweight": "MaxWeight / Lyapunov drift (queue-weighted greedy fill)",
    "queue_aware": "Deadline-aware reactive (persistence r*)",
    "point_forecast": "Point forecast (GBM median) + water-fill",
    "fixed_quantile": "Global fixed quantile (tuned level) + water-fill",
    "proposed_window": "Proposed rule with window quantiles (no ML)",
    "proposed": "Proposed: GBM quantiles + KKT allocation",
    "proposed_cal": "Proposed + online (ACI) calibration",
    "oracle": "Oracle water-fill (true r*, not implementable; reference, not a bound)",
}

_FORECASTER_CACHE: Dict[str, QuantileGBMForecaster] = {}


def model_path(interval: int, delay: int) -> str:
    return os.path.join(MODEL_DIR, f"fhlm_quantile_gbm_T{interval}_d{delay}.pkl")


def ensure_forecaster(interval: int, delay: int) -> QuantileGBMForecaster:
    path = model_path(interval, delay)
    if path not in _FORECASTER_CACHE:
        if not os.path.exists(path):
            print(f"[runner] training forecaster for T={interval}, tau={delay} -> {path}")
            subprocess.run([sys.executable, "-m", "fhlm.train", "--out", path, "--interval", str(interval),
                            "--delay", str(delay), "--report",
                            os.path.join(RESULTS_DIR, f"forecast_training_T{interval}_d{delay}.json")], check=True)
        _FORECASTER_CACHE[path] = QuantileGBMForecaster.load(path)
    return _FORECASTER_CACHE[path]


def build_controller(name: str, params: Dict[str, Any], interval: int, delay: int):
    p = dict(params or {})
    if name == "static_equal":
        return StaticEqualShare()
    if name == "reactive_prop":
        return ReactiveProportional(margin=p.get("margin", 0.0), ewma_window=p.get("ewma_window"))
    if name == "queue_aware":
        return QueueAwareReactive(margin=p.get("margin", 0.0), w_min=p.get("w_min", 0.25),
                                  num_horizons=p.get("num_horizons", 1))
    if name == "maxweight":
        return MaxWeightReactive(margin=p.get("margin", 0.0), ewma_window=p.get("ewma_window"),
                                 hol_weight=p.get("hol_weight", 0.0))
    if name == "fixed_quantile":
        return FixedQuantileWaterfill(ensure_forecaster(interval, delay), level=p.get("level", 0.9),
                                      w_min=p.get("w_min", 0.25))
    if name == "point_forecast":
        return PointForecastWaterfill(ensure_forecaster(interval, delay), margin=p.get("margin", 0.0),
                                      w_min=p.get("w_min", 0.25))
    if name == "proposed_window":
        return UncertaintyAwareAllocator(WindowQuantileForecaster(window=p.get("window", 30)), calibrate=False,
                                         w_min=p.get("w_min", 0.25), name="proposed_window")
    if name == "proposed":
        return UncertaintyAwareAllocator(ensure_forecaster(interval, delay), calibrate=False,
                                         w_min=p.get("w_min", 0.25), name="proposed")
    if name == "proposed_cal":
        return UncertaintyAwareAllocator(ensure_forecaster(interval, delay), calibrate=True,
                                         gamma=p.get("gamma", 0.02), w_min=p.get("w_min", 0.25), name="proposed_cal")
    if name == "proposed_miscal":
        return UncertaintyAwareAllocator(MiscalibratedForecaster(ensure_forecaster(interval, delay), p.get("eps", 0.0)),
                                         calibrate=False, w_min=p.get("w_min", 0.25), name="proposed_miscal")
    if name == "oracle":
        return OracleWaterfill(w_min=p.get("w_min", 0.25))
    raise ValueError(name)


def with_compression(cfg, trace, mantissa_bits: int):
    """Same user traffic, different BFP mantissa width (Part A lever).

    The trace is generated with the reference network (BFP-9); here the
    fronthaul bits per PRB-layer are rescaled to the new width, which changes
    the offered fronthaul load and the per-cell caps but not the user bits.
    """
    from dataclasses import replace
    from .traffic import TrafficTrace
    ref_beta = cfg.network.fh_bits_per_prb_layer
    net = replace(cfg.network, mantissa_bits=mantissa_bits)
    ratio = net.fh_bits_per_prb_layer / ref_beta
    new_trace = TrafficTrace(arrivals_bits=trace.arrivals_bits, se=trace.se,
                             fh_demand_bits=trace.fh_demand_bits * ratio, regime_mult=trace.regime_mult,
                             mean_fh_load=trace.mean_fh_load * ratio)
    return replace(cfg, network=net), new_trace


def run_one(job) -> Dict[str, Any]:
    scenario, seed, method, params, interval, delay, slots, warmup, tag = job[:9]
    mantissa = job[9] if len(job) > 9 else None
    cfg = make_config(scenario, seed, slots, warmup, interval, delay)
    trace = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
    if mantissa is not None:
        cfg, trace = with_compression(cfg, trace, mantissa)
    ctrl = build_controller(method, params, interval, delay)
    t0 = time.perf_counter()
    res = run_simulation(cfg, ctrl, trace=trace)
    row = {"scenario": scenario, "seed": seed, "method": method, "params": json.dumps(params or {}),
           "interval_slots": interval, "telemetry_delay_slots": delay, "wall_s": time.perf_counter() - t0,
           "realised_load": trace.mean_fh_load, "mantissa_bits": cfg.network.mantissa_bits}
    row.update(res.metrics)
    if hasattr(ctrl, "stats"):
        row["controller_stats"] = json.dumps(ctrl.stats)
    if tag:
        os.makedirs(RAW_DIR, exist_ok=True)
        suffix = f"_b{mantissa}" if mantissa is not None else ""
        fn = os.path.join(RAW_DIR, f"{tag}_{scenario}_s{seed}_T{interval}_{method}{suffix}.json")
        with open(fn, "w") as f:
            json.dump({"row": row, "per_cell": res.per_cell, "config": res.config,
                       "decision_times_ms": res.decision_times_ms[:200]}, f, indent=1, default=float)
    return row


def run_jobs(jobs: List[tuple], workers: int) -> pd.DataFrame:
    # make sure any required forecaster exists before forking workers
    for job in jobs:
        if job[2] in ("point_forecast", "fixed_quantile", "proposed", "proposed_cal", "proposed_miscal"):
            ensure_forecaster(job[4], job[5])
    t0 = time.perf_counter()
    if workers > 1:
        with Pool(workers) as pool:
            rows = pool.map(run_one, jobs, chunksize=1)
    else:
        rows = [run_one(j) for j in jobs]
    print(f"[runner] {len(jobs)} runs in {time.perf_counter() - t0:.0f}s")
    return pd.DataFrame(rows)


def load_tuning() -> Dict[str, Dict[str, Any]]:
    path = os.path.join(RESULTS_DIR, "tuning.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)["selected"]
    return {}


# ---------------------------------------------------------------------------
def cmd_tune(args):
    grid = {
        "reactive_prop": [{"margin": m, "ewma_window": w} for m in (0.0, 0.25, 0.5) for w in (20, 60)],
        "queue_aware": [{"margin": m, "num_horizons": k} for m in (0.0, 0.25) for k in (1, 3, 6)],
        "maxweight": [{"margin": m, "hol_weight": h} for m in (0.0, 0.25, 0.5) for h in (0.0, 1.0)],
        "point_forecast": [{"margin": m} for m in (0.0, 0.25, 0.5)],
        "fixed_quantile": [{"level": q} for q in (0.75, 0.9, 0.95)],
        "proposed_cal": [{"gamma": g} for g in (0.005, 0.01, 0.02)],
    }
    jobs = []
    for method, plist in grid.items():
        for params in plist:
            for sc in VAL_SCENARIOS:
                for seed in VAL_SEEDS:
                    jobs.append((sc, seed, method, params, args.interval, args.delay, args.slots, args.warmup, ""))
    df = run_jobs(jobs, args.workers)
    df.to_csv(os.path.join(RESULTS_DIR, "tuning_runs.csv"), index=False)
    selected, table = {}, []
    for method, g in df.groupby("method"):
        agg = g.groupby("params")[PRIMARY_METRIC].mean().sort_values()
        best = agg.index[0]
        selected[method] = json.loads(best)
        for p, v in agg.items():
            table.append({"method": method, "params": p, PRIMARY_METRIC: v})
    out = {"primary_metric": PRIMARY_METRIC, "validation_scenarios": VAL_SCENARIOS, "validation_seeds": VAL_SEEDS,
           "selected": selected, "table": table}
    with open(os.path.join(RESULTS_DIR, "tuning.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out["selected"], indent=1))
    print(pd.DataFrame(table).to_string())


def cmd_main(args):
    tuned = load_tuning()
    methods = args.methods or METHOD_ORDER
    scenarios = args.scenarios or list(SCENARIOS)
    jobs = [(sc, seed, m, tuned.get(m, {}), args.interval, args.delay, args.slots, args.warmup, "main")
            for sc in scenarios for seed in TEST_SEEDS for m in methods]
    df = run_jobs(jobs, args.workers)
    df.to_csv(os.path.join(RESULTS_DIR, "main_runs.csv"), index=False)
    metrics = [PRIMARY_METRIC, "violation_ratio", "violation_ratio_ll", "violation_ratio_embb", "fh_utilisation",
               "fh_unused_allocation_fraction", "mean_queueing_delay_ms", "p99_queueing_delay_ms",
               "jain_fairness_service_ratio", "min_cell_service_ratio", "decision_time_ms_mean", "realised_load"]
    agg = df.groupby(["scenario", "method"])[metrics].agg(["mean", "std"])
    agg.columns = [f"{a}_{b}" for a, b in agg.columns]
    agg = agg.reset_index()
    agg["method"] = pd.Categorical(agg["method"], METHOD_ORDER, ordered=True)
    agg = agg.sort_values(["scenario", "method"])
    agg.to_csv(os.path.join(RESULTS_DIR, "main_summary.csv"), index=False)
    pd.set_option("display.width", 200)
    print(agg[["scenario", "method", f"{PRIMARY_METRIC}_mean", f"{PRIMARY_METRIC}_std", "violation_ratio_ll_mean",
               "violation_ratio_embb_mean", "fh_utilisation_mean", "decision_time_ms_mean_mean"]].to_string(index=False))
    paired = paired_analysis(df, reference="proposed")
    paired.to_csv(os.path.join(RESULTS_DIR, "main_paired.csv"), index=False)
    print("\nPaired differences on identical traces (baseline - proposed), primary metric:")
    print(paired.to_string(index=False))


def paired_analysis(df: pd.DataFrame, reference: str = "proposed", metric: str = PRIMARY_METRIC,
                    n_boot: int = 10000) -> pd.DataFrame:
    """Per-seed paired comparison: every method sees the same trace as `reference`.

    For each (scenario, baseline) reports the mean paired difference
    (baseline - reference), the relative reduction with a 95 % percentile
    bootstrap CI over seeds, the number of seeds the reference wins, and a
    two-sided Wilcoxon signed-rank p-value (exact for n <= 25). p-values are
    Holm-corrected across the baselines of the same scenario. With n < 6 the
    Wilcoxon test cannot reach p < 0.05 and NaN is reported.
    """
    from scipy.stats import wilcoxon
    rng = np.random.default_rng(0)
    rows = []
    for sc, d in df.groupby("scenario"):
        ref = d[d.method == reference].set_index("seed")[metric]
        sc_rows = []
        for m in [x for x in METHOD_ORDER if x in d.method.unique() and x != reference]:
            other = d[d.method == m].set_index("seed")[metric].reindex(ref.index)
            diff = (other - ref).dropna()
            o, r = other.loc[diff.index].values, ref.loc[diff.index].values
            n = len(diff)
            rel = 100 * diff.mean() / o.mean() if o.mean() > 0 else np.nan
            if n >= 2:
                idx = rng.integers(0, n, size=(n_boot, n))
                boot = 100 * (o[idx].mean(1) - r[idx].mean(1)) / np.maximum(o[idx].mean(1), 1e-12)
                lo, hi = np.percentile(boot, [2.5, 97.5])
            else:
                lo = hi = np.nan
            if n >= 6 and np.any(diff.values != 0):
                pval = float(wilcoxon(o, r, alternative="two-sided", zero_method="wilcox").pvalue)
            else:
                pval = np.nan
            sc_rows.append({"scenario": sc, "baseline": m, "n_seeds": int(n),
                            "baseline_mean": float(o.mean()), "reference_mean": float(r.mean()),
                            "diff_mean": float(diff.mean()), "diff_std": float(diff.std(ddof=1)) if n > 1 else 0.0,
                            "rel_reduction_pct": float(rel), "rel_ci_lo_pct": float(lo), "rel_ci_hi_pct": float(hi),
                            "reference_wins": int((diff > 0).sum()), "min_diff": float(diff.min()),
                            "max_diff": float(diff.max()), "wilcoxon_p": pval})
        # Holm step-down correction within the scenario
        ps = [(i, r_["wilcoxon_p"]) for i, r_ in enumerate(sc_rows) if np.isfinite(r_["wilcoxon_p"])]
        ps.sort(key=lambda t: t[1])
        k = len(ps)
        running = 0.0
        for rank, (i, pv) in enumerate(ps):
            adj = min(1.0, (k - rank) * pv)
            running = max(running, adj)
            sc_rows[i]["wilcoxon_p_holm"] = running
        for r_ in sc_rows:
            r_.setdefault("wilcoxon_p_holm", np.nan)
        rows.extend(sc_rows)
    return pd.DataFrame(rows)


class MiscalibratedForecaster:
    """Wrapper that reports the base model's quantile at level (alpha + eps) as the level-alpha quantile.

    The reported CDF is the true one shifted by eps in probability, so the
    Kolmogorov distance between reported and base forecast is |eps| (inside
    the knot range). eps > 0 makes the controller over-reserve, eps < 0
    under-reserve. Used to test Proposition 4 (robustness to miscalibration).
    """

    def __init__(self, base, eps: float):
        self.base, self.eps = base, eps
        self.quantiles = base.quantiles

    @property
    def median_index(self):
        return self.base.median_index

    def predict_quantiles(self, obs):
        q = np.asarray(self.base.predict_quantiles(obs), dtype=float)
        levels = np.asarray(self.quantiles, dtype=float)
        shifted = np.clip(levels + self.eps, levels[0], levels[-1])
        return np.stack([np.interp(shifted, levels, q[i]) for i in range(q.shape[0])])


def cmd_miscalibration(args):
    """Robustness of the KKT rule to a miscalibrated forecast distribution (Proposition 4)."""
    eps_list = args.eps or [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3]
    seeds = TEST_SEEDS[:args.num_seeds]
    scenarios = args.scenarios or ["high", "shift"]
    tuned = load_tuning()
    jobs = []
    for sc in scenarios:
        for seed in seeds:
            for e in eps_list:
                jobs.append((sc, seed, "proposed_miscal", {"eps": e}, args.interval, args.delay, args.slots, args.warmup, ""))
            for m in ("point_forecast", "queue_aware"):
                jobs.append((sc, seed, m, tuned.get(m, {}), args.interval, args.delay, args.slots, args.warmup, ""))
    df = run_jobs(jobs, args.workers)
    df["eps"] = df.params.apply(lambda s_: json.loads(s_).get("eps", np.nan))
    df.to_csv(os.path.join(RESULTS_DIR, "miscalibration_runs.csv"), index=False)
    g = df[df.method == "proposed_miscal"].groupby(["scenario", "eps"])[PRIMARY_METRIC].agg(["mean", "std"])
    print(g.to_string())
    for m in ("point_forecast", "queue_aware"):
        print(m, df[df.method == m].groupby("scenario")[PRIMARY_METRIC].mean().to_dict())


def cmd_delay(args):
    """Sensitivity to the telemetry delay tau (slots); forecaster retrained per tau."""
    taus = args.delays or [0, 2, 5, 10]
    methods = args.methods or ["reactive_prop", "queue_aware", "point_forecast", "proposed"]
    seeds = TEST_SEEDS[:args.num_seeds]
    tuned = load_tuning()
    jobs = [(args.scenario, seed, m, tuned.get(m, {}), args.interval, tau, args.slots, args.warmup, "delay")
            for tau in taus for seed in seeds for m in methods]
    df = run_jobs(jobs, args.workers)
    df.to_csv(os.path.join(RESULTS_DIR, "delay_runs.csv"), index=False)
    agg = df.groupby(["telemetry_delay_slots", "method"])[[PRIMARY_METRIC, "violation_ratio_ll", "violation_ratio_embb"]].agg(["mean", "std"])
    print(agg.to_string())


def cmd_sweep(args):
    tuned = load_tuning()
    intervals = args.intervals or [4, 10, 20, 40]
    methods = args.methods or ["reactive_prop", "queue_aware", "point_forecast", "proposed", "oracle"]
    seeds = TEST_SEEDS[:args.num_seeds]
    jobs = [(args.scenario, seed, m, tuned.get(m, {}), T, args.delay, args.slots, args.warmup, "sweep")
            for T in intervals for seed in seeds for m in methods]
    df = run_jobs(jobs, args.workers)
    df.to_csv(os.path.join(RESULTS_DIR, "sweep_runs.csv"), index=False)
    agg = df.groupby(["interval_slots", "method"])[[PRIMARY_METRIC, "violation_ratio_ll", "violation_ratio_embb",
                                                    "fh_utilisation"]].agg(["mean", "std"])
    agg.columns = [f"{a}_{b}" for a, b in agg.columns]
    agg.reset_index().to_csv(os.path.join(RESULTS_DIR, "sweep_summary.csv"), index=False)
    print(agg.to_string())


def cmd_compression(args):
    """Bridge between the two project parts: compression width (Part A) x allocation rule (Part B).

    Same user traffic and seeds; only the BFP mantissa width changes, which
    rescales the fronthaul bits per PRB-layer (and therefore the offered load).
    """
    tuned = load_tuning()
    widths = args.mantissa or [6, 9, 12, 14]
    methods = args.methods or ["reactive_prop", "queue_aware", "point_forecast", "proposed"]
    seeds = TEST_SEEDS[:args.num_seeds]
    jobs = [(args.scenario, seed, m, tuned.get(m, {}), args.interval, args.delay, args.slots, args.warmup,
             "compression", b) for b in widths for seed in seeds for m in methods]
    df = run_jobs(jobs, args.workers)
    df.to_csv(os.path.join(RESULTS_DIR, "compression_runs.csv"), index=False)
    agg = df.groupby(["mantissa_bits", "method"])[[PRIMARY_METRIC, "violation_ratio_ll", "violation_ratio_embb",
                                                   "fh_utilisation", "realised_load"]].agg(["mean", "std"])
    agg.columns = [f"{a}_{b}" for a, b in agg.columns]
    agg.reset_index().to_csv(os.path.join(RESULTS_DIR, "compression_summary.csv"), index=False)
    print(agg.to_string())


def cmd_demo(args):
    tuned = load_tuning()
    cfg = make_config(args.scenario, TEST_SEEDS[0], args.slots, args.warmup, args.interval, args.delay)
    trace = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = {}
    for m in ["queue_aware", "point_forecast", "proposed"]:  # demo methods
        ctrl = build_controller(m, tuned.get(m, {}), args.interval, args.delay)
        res = run_simulation(cfg, ctrl, trace=trace, record_timeseries=True)
        out[m] = res
        print(f"{m:16s} {PRIMARY_METRIC}={res.metrics[PRIMARY_METRIC]:.4f}  LL={res.metrics['violation_ratio_ll']:.4f}  "
              f"eMBB={res.metrics['violation_ratio_embb']:.4f}  util={res.metrics['fh_utilisation']:.3f}  "
              f"decision={res.metrics['decision_time_ms_mean']:.1f} ms")
    np.savez_compressed(os.path.join(RESULTS_DIR, "demo_timeseries.npz"),
                        fh_demand=trace.fh_demand_bits, **{f"{m}_budget": r.timeseries["budget"] for m, r in out.items()},
                        **{f"{m}_queue": r.timeseries["queue"] for m, r in out.items()},
                        **{f"{m}_violated": r.timeseries["violated"] for m, r in out.items()},
                        capacity=cfg.network.usable_bits_per_slot, interval=args.interval)
    with open(os.path.join(RESULTS_DIR, "demo_config.json"), "w") as f:
        f.write(cfg.to_json())
    print(f"saved {RESULTS_DIR}/demo_timeseries.npz")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["tune", "main", "sweep", "compression", "miscalibration", "delay", "demo"])
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--delay", type=int, default=2)
    ap.add_argument("--slots", type=int, default=DEFAULT_SLOTS)
    ap.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument("--methods", nargs="*")
    ap.add_argument("--scenarios", nargs="*")
    ap.add_argument("--scenario", default="high")
    ap.add_argument("--intervals", nargs="*", type=int)
    ap.add_argument("--num-seeds", type=int, default=3)
    ap.add_argument("--mantissa", nargs="*", type=int, help="BFP mantissa widths for the compression sweep")
    ap.add_argument("--eps", nargs="*", type=float, help="probability-level shifts for the miscalibration sweep")
    ap.add_argument("--delays", nargs="*", type=int, help="telemetry delays (slots) for the delay sweep")
    args = ap.parse_args(argv)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    {"tune": cmd_tune, "main": cmd_main, "sweep": cmd_sweep, "compression": cmd_compression,
     "miscalibration": cmd_miscalibration, "delay": cmd_delay, "demo": cmd_demo}[args.command](args)


if __name__ == "__main__":
    main()
