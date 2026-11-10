"""Train the link-aware cross-cell quantile Transformer (LCQT) on TRAINING seeds.

    python -m fhlm.train_transformer [--out models/fhlm_lcqt_T20_d2.pt] [--no-cross] [--unweighted]

Same traces, seeds and target as fhlm.train; the GBM forecaster is evaluated on
the identical validation rows so the forecast-quality comparison is exact.
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np

from .scenarios import TRAIN_SEEDS, VAL_SEEDS, TRAIN_LOADS, train_config, make_config, VAL_SCENARIOS_BY_FAMILY
from .traffic import generate_traffic
from .forecast import QuantileGBMForecaster, forecast_metrics
from .transformer import TransformerQuantileForecaster, build_sequence_dataset, cell_conditioning


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/fhlm_lcqt_T20_d2.pt")
    ap.add_argument("--report", default="results/fhlm/forecast_training_lcqt_T20_d2.json")
    ap.add_argument("--gbm", default="models/fhlm_quantile_gbm_T20_d2.pkl")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--delay", type=int, default=2)
    ap.add_argument("--slots", type=int, default=16000)
    ap.add_argument("--family", default="synthetic", choices=["synthetic", "3gpp", "markov"])
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--d-model", type=int, default=48)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--no-cross", action="store_true", help="ablation: no cross-cell attention layer")
    ap.add_argument("--unweighted", action="store_true", help="ablation: plain (not priority-weighted) pinball loss")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(os.path.dirname(args.report), exist_ok=True)

    t0 = time.perf_counter()
    train_traces = []
    for k, seed in enumerate(TRAIN_SEEDS):
        cfg = train_config(TRAIN_LOADS[k % len(TRAIN_LOADS)], seed, args.slots, args.interval, args.delay, args.family)
        train_traces.append(generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed))
    net, ctrl = cfg.network, cfg.control
    val_traces = []
    for seed in VAL_SEEDS:
        for sc in VAL_SCENARIOS_BY_FAMILY[args.family]:
            vcfg = make_config(sc, seed, args.slots, 0, args.interval, args.delay)
            val_traces.append(generate_traffic(vcfg.network, vcfg.traffic, vcfg.num_slots, vcfg.seed))
    train = build_sequence_dataset(train_traces, net, ctrl)
    val = build_sequence_dataset(val_traces, net, ctrl)
    print(f"dataset: train {train[0].shape}, val {val[0].shape} ({time.perf_counter() - t0:.1f}s)", flush=True)

    model = TransformerQuantileForecaster(d_model=args.d_model, layers=args.layers, cross_cell=not args.no_cross,
                                          priority_weighted=not args.unweighted)
    priorities = np.array([c.priority for c in net.cells], dtype=float)
    info = model.fit(train, val, cell_conditioning(net, ctrl), priorities, epochs=args.epochs, threads=args.threads)
    model.meta.update({"interval_slots": args.interval, "telemetry_delay_slots": args.delay, "family": args.family})
    model.save(args.out)

    report = {"interval_slots": args.interval, "telemetry_delay_slots": args.delay, "family": args.family,
              "hyperparameters": model.hp, "train_rows_epochs": int(len(train[2])), "val_rows_epochs": int(len(val[2])),
              "n_params": info["n_params"], "train_time_s": info["train_time_s"], "epochs_run": info["epochs_run"],
              "lcqt_validation": info["val"], "history": info["history"]}
    ll = np.array([c.deadline_slots <= 10 for c in net.cells])
    report["lcqt_validation_ll"] = forecast_metrics(model._predict_batch(val[0], val[1])[:, ll].reshape(-1, 6),
                                                    val[2][:, ll].reshape(-1), model.quantiles)
    if os.path.exists(args.gbm):
        gbm = QuantileGBMForecaster.load(args.gbm)
        Vf = val[1].reshape(-1, val[1].shape[-1]).astype(float)
        gq = gbm.predict_normalised(Vf, fast=False)
        report["gbm_validation_same_rows"] = forecast_metrics(gq, val[2].reshape(-1), gbm.quantiles)
        gq_ll = gq.reshape(val[2].shape[0], -1, 6)[:, ll].reshape(-1, 6)
        report["gbm_validation_ll_same_rows"] = forecast_metrics(gq_ll, val[2][:, ll].reshape(-1), gbm.quantiles)
    with open(args.report, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: report[k] for k in report if k.endswith("validation") or "same_rows" in k}, indent=1))
    print(f"saved model -> {args.out}\nreport -> {args.report}")


if __name__ == "__main__":
    main()
