"""Closed-loop test of the link-aware cross-cell quantile Transformer (LCQT) under the KKT rule.

    python3 -m fhlm.run_transformer_study [--family synthetic] [--workers 4]

Runs the LCQT controllers and a fresh GBM `proposed` run on the TEST seeds of
every scenario of the family. The other baselines are read from
results/fhlm/main_runs.csv (same traces, same code; the simulator is
deterministic, so re-running them reproduces the stored rows exactly).
Outputs: results/fhlm/transformer_runs.csv, transformer_summary.csv,
transformer_paired[_<reference>].csv (default reference = proposed_tf).
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from .scenarios import TEST_SEEDS, scenarios_of
from .run_experiments import (run_jobs, tuned_params, paired_analysis, tf_method_available, RESULTS_DIR,
                              PRIMARY_METRIC, METHOD_ORDER)

NEW_METHODS = ["proposed", "proposed_tf", "point_forecast_tf", "proposed_tf_nocross", "proposed_tf_unw",
               "proposed_tf_mc", "proposed_tf_bayes", "proposed_tf_dfl", "proposed_tf_dfl_bayes"]
STORED_BASELINES = ["static_equal", "reactive_prop", "maxweight", "queue_aware", "point_forecast", "fixed_quantile",
                    "proposed_window", "pred_maxweight", "cem_policy", "oracle", "oracle_kkt"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="synthetic")
    ap.add_argument("--scenarios", nargs="*")
    ap.add_argument("--methods", nargs="*")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--delay", type=int, default=2)
    ap.add_argument("--slots", type=int, default=20000)
    ap.add_argument("--warmup", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--reference", default="proposed_tf")
    args = ap.parse_args(argv)

    scenarios = args.scenarios or scenarios_of(args.family)
    methods = [m for m in (args.methods or NEW_METHODS)
               if m == "proposed" or tf_method_available(m, args.interval, args.delay, args.family)]
    jobs = [(sc, seed, m, tuned_params(m, sc) if m == "proposed" else {}, args.interval, args.delay, args.slots,
             args.warmup, "") for sc in scenarios for seed in TEST_SEEDS for m in methods]
    df = run_jobs(jobs, args.workers)
    path = os.path.join(RESULTS_DIR, "transformer_runs.csv")
    if os.path.exists(path):
        old = pd.read_csv(path)
        keys = set(zip(df.scenario, df.method))
        old = old[~old.apply(lambda r: (r.scenario, r.method) in keys, axis=1)]
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(path, index=False)

    stored = pd.read_csv(os.path.join(RESULTS_DIR, "main_runs.csv"))
    stored = stored[stored.scenario.isin(df.scenario.unique()) & stored.method.isin(STORED_BASELINES)
                    & (stored.interval_slots == args.interval) & (stored.telemetry_delay_slots == args.delay)]
    allruns = pd.concat([df, stored], ignore_index=True)
    metrics = [PRIMARY_METRIC, "violation_ratio", "violation_ratio_ll", "violation_ratio_embb", "fh_utilisation",
               "decision_time_ms_mean"]
    agg = allruns.groupby(["scenario", "method"])[metrics].agg(["mean", "std"])
    agg.columns = [f"{a}_{b}" for a, b in agg.columns]
    agg = agg.reset_index()
    agg["method"] = pd.Categorical(agg["method"], METHOD_ORDER, ordered=True)
    agg = agg.sort_values(["scenario", "method"])
    agg.to_csv(os.path.join(RESULTS_DIR, "transformer_summary.csv"), index=False)
    pd.set_option("display.width", 220)
    print(agg[["scenario", "method", f"{PRIMARY_METRIC}_mean", f"{PRIMARY_METRIC}_std", "violation_ratio_ll_mean",
               "violation_ratio_embb_mean", "fh_utilisation_mean", "decision_time_ms_mean_mean"]].to_string(index=False))
    paired = paired_analysis(allruns, reference=args.reference)
    suffix = "" if args.reference == "proposed_tf" else f"_{args.reference}"
    paired.to_csv(os.path.join(RESULTS_DIR, f"transformer_paired{suffix}.csv"), index=False)
    print(f"\nPaired (baseline - {args.reference}):")
    print(paired[["scenario", "baseline", "baseline_mean", "reference_mean", "rel_reduction_pct", "rel_ci_lo_pct",
                  "rel_ci_hi_pct", "reference_wins", "n_seeds", "wilcoxon_p_holm"]].to_string(index=False))


if __name__ == "__main__":
    main()
