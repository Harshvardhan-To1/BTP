"""Train the quantile forecaster on TRAINING seeds and evaluate on VALIDATION seeds.

    python -m fhlm.train [--out models/fhlm_quantile_gbm.pkl] [--interval 20] [--delay 2]

The traffic is exogenous, so training data are generated directly from the
traffic model (no closed-loop simulation needed) and are independent of any
controller. Test seeds are never touched here.
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np

from .scenarios import TRAIN_SEEDS, VAL_SEEDS, TRAIN_LOADS, train_config, make_config, VAL_SCENARIOS
from .traffic import generate_traffic
from .forecast import QuantileGBMForecaster, WindowQuantileForecaster, build_dataset, feature_names, DEFAULT_QUANTILES


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/fhlm_quantile_gbm.pkl")
    ap.add_argument("--report", default="results/fhlm/forecast_training.json")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--delay", type=int, default=2)
    ap.add_argument("--slots", type=int, default=16000)
    ap.add_argument("--max-iter", type=int, default=300)
    args = ap.parse_args(argv)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(os.path.dirname(args.report), exist_ok=True)

    t0 = time.perf_counter()
    train_traces = []
    for k, seed in enumerate(TRAIN_SEEDS):
        cfg = train_config(TRAIN_LOADS[k % len(TRAIN_LOADS)], seed, args.slots, args.interval, args.delay)
        train_traces.append(generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed))
    net, ctrl = cfg.network, cfg.control
    X, y = build_dataset(train_traces, net, ctrl)

    val_traces = []
    for seed in VAL_SEEDS:
        for sc in VAL_SCENARIOS:
            vcfg = make_config(sc, seed, args.slots, 0, args.interval, args.delay)
            val_traces.append(generate_traffic(vcfg.network, vcfg.traffic, vcfg.num_slots, vcfg.seed))
    Xv, yv = build_dataset(val_traces, net, ctrl)
    print(f"dataset: train {X.shape}, val {Xv.shape}  ({time.perf_counter() - t0:.1f}s)")

    model = QuantileGBMForecaster(max_iter=args.max_iter)
    info = model.fit(X, y, Xv, yv)
    print(f"trained {len(model.quantiles)} quantile models in {info['train_time_s']:.1f}s")
    print("validation:", json.dumps(info["val"], indent=1))

    # non-ML reference on the same validation epochs
    window = WindowQuantileForecaster(window=30)
    win_val = window.evaluate_on_traces(val_traces, net, ctrl)
    # persistence (last horizon r*) as a point-forecast reference
    names = feature_names(net.num_cells)
    rstar_lag1 = Xv[:, names.index("rstar_lag_1")]
    persist_mae = float(np.mean(np.abs(yv - rstar_lag1)))
    report = {
        "interval_slots": args.interval, "telemetry_delay_slots": args.delay,
        "train_rows": int(len(y)), "val_rows": int(len(yv)), "quantiles": list(model.quantiles),
        "gbm_params": model.params, "gbm_validation": info["val"],
        "window_quantile_validation": win_val,
        "persistence_median_mae": persist_mae,
        "persistence_median_mae_rel": persist_mae / float(np.mean(yv)),
        "train_time_s": info["train_time_s"],
        "feature_names": names,
    }
    model.meta.update({"interval_slots": args.interval, "telemetry_delay_slots": args.delay})
    model.save(args.out)
    with open(args.report, "w") as f:
        json.dump(report, f, indent=2)
    print(f"saved model -> {args.out}\nreport -> {args.report}")
    print(f"window-quantile val pinball {win_val['pinball_mean']:.4f} vs GBM {info['val']['pinball_mean']:.4f}; "
          f"median MAE: persistence {persist_mae:.4f}, window {win_val['median_mae']:.4f}, GBM {info['val']['median_mae']:.4f}")


if __name__ == "__main__":
    main()
