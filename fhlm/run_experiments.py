"""Experiment runner: validation tuning, main comparison, interval sweep, demo.

    python -m fhlm.run_experiments tune      # pick safety margins on VALIDATION seeds
    python -m fhlm.run_experiments main      # all methods x test scenarios x test seeds
    python -m fhlm.run_experiments sweep     # control-interval sweep (trains per-T forecasters)
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
                          OracleWaterfill)
from .proposed import UncertaintyAwareAllocator
from .forecast import QuantileGBMForecaster, WindowQuantileForecaster

RESULTS_DIR = "results/fhlm"
RAW_DIR = os.path.join(RESULTS_DIR, "raw")
MODEL_DIR = "models"

PRIMARY_METRIC = "weighted_violation_ratio"

# method name -> (constructor, needs_forecaster)
METHOD_ORDER = ["static_equal", "reactive_prop", "queue_aware", "point_forecast", "proposed_window",
                "proposed", "proposed_cal", "oracle"]
METHOD_LABELS = {
    "static_equal": "Static equal share",
    "reactive_prop": "Reactive proportional (EWMA)",
    "queue_aware": "Deadline-aware reactive (persistence r*)",
    "point_forecast": "Point forecast (GBM median) + water-fill",
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
    if name == "oracle":
        return OracleWaterfill(w_min=p.get("w_min", 0.25))
    raise ValueError(name)


def run_one(job: Tuple[str, int, str, Dict[str, Any], int, int, int, int, str]) -> Dict[str, Any]:
    scenario, seed, method, params, interval, delay, slots, warmup, tag = job
    cfg = make_config(scenario, seed, slots, warmup, interval, delay)
    trace = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
    ctrl = build_controller(method, params, interval, delay)
    t0 = time.perf_counter()
    res = run_simulation(cfg, ctrl, trace=trace)
    row = {"scenario": scenario, "seed": seed, "method": method, "params": json.dumps(params or {}),
           "interval_slots": interval, "telemetry_delay_slots": delay, "wall_s": time.perf_counter() - t0,
           "realised_load": trace.mean_fh_load}
    row.update(res.metrics)
    if hasattr(ctrl, "stats"):
        row["controller_stats"] = json.dumps(ctrl.stats)
    if tag:
        os.makedirs(RAW_DIR, exist_ok=True)
        fn = os.path.join(RAW_DIR, f"{tag}_{scenario}_s{seed}_T{interval}_{method}.json")
        with open(fn, "w") as f:
            json.dump({"row": row, "per_cell": res.per_cell, "config": res.config,
                       "decision_times_ms": res.decision_times_ms[:200]}, f, indent=1, default=float)
    return row


def run_jobs(jobs: List[tuple], workers: int) -> pd.DataFrame:
    # make sure any required forecaster exists before forking workers
    for job in jobs:
        if job[2] in ("point_forecast", "proposed", "proposed_cal"):
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
        "point_forecast": [{"margin": m} for m in (0.0, 0.25, 0.5)],
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


def paired_analysis(df: pd.DataFrame, reference: str = "proposed", metric: str = PRIMARY_METRIC) -> pd.DataFrame:
    """Per-seed paired comparison: every method sees the same trace as `reference`.

    Reports mean/std of (baseline - reference), relative reduction, wins out of
    n seeds, and a paired-sign statement. No distributional assumption is made
    (5 seeds are too few for a meaningful t-test); the win count is the honest
    summary.
    """
    rows = []
    for sc, d in df.groupby("scenario"):
        ref = d[d.method == reference].set_index("seed")[metric]
        for m in [x for x in METHOD_ORDER if x in d.method.unique() and x != reference]:
            other = d[d.method == m].set_index("seed")[metric].reindex(ref.index)
            diff = (other - ref).dropna()
            rows.append({"scenario": sc, "baseline": m, "n_seeds": int(len(diff)),
                         "baseline_mean": float(other.mean()), "reference_mean": float(ref.mean()),
                         "diff_mean": float(diff.mean()), "diff_std": float(diff.std(ddof=1)) if len(diff) > 1 else 0.0,
                         "rel_reduction_pct": float(100 * diff.mean() / other.mean()) if other.mean() > 0 else np.nan,
                         "reference_wins": int((diff > 0).sum()), "min_diff": float(diff.min()),
                         "max_diff": float(diff.max())})
    return pd.DataFrame(rows)


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
    ap.add_argument("command", choices=["tune", "main", "sweep", "demo"])
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
    args = ap.parse_args(argv)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    {"tune": cmd_tune, "main": cmd_main, "sweep": cmd_sweep, "demo": cmd_demo}[args.command](args)


if __name__ == "__main__":
    main()
