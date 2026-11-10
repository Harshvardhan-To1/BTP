"""Forecast quality of the Bayesian LCQT variants (single, MC dropout, deep ensemble, ensemble x MC).

    python3 -m fhlm.eval_bayes_forecast

Validation seeds (in-distribution) and the held-out 'shift' scenario on the
first 4 test seeds (out-of-distribution; diagnostic only, nothing is selected
on it). Writes results/fhlm/bayes_forecast_quality.csv.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .scenarios import VAL_SEEDS, TEST_SEEDS, make_config, VAL_SCENARIOS_BY_FAMILY
from .traffic import generate_traffic
from .forecast import forecast_metrics
from .transformer import TransformerQuantileForecaster, BayesianTransformerForecaster, build_sequence_dataset
from .run_experiments import tf_model_path, RESULTS_DIR


def main():
    import torch
    torch.set_num_threads(2)
    paths = [tf_model_path(20, 2, "synthetic", v) for v in ("", "_s1", "_s2")]
    members = [TransformerQuantileForecaster.load(p, threads=2) for p in paths]
    dfl_path = tf_model_path(20, 2, "synthetic", "_dfl")
    variants = {
        "LCQT": BayesianTransformerForecaster(members[:1], mc_samples=1),
        "LCQT + MC dropout (16)": BayesianTransformerForecaster(members[:1], mc_samples=16),
        "Deep ensemble (3)": BayesianTransformerForecaster(members, mc_samples=1),
        "Ensemble x MC (3x8)": BayesianTransformerForecaster(members, mc_samples=8),
    }
    if os.path.exists(dfl_path):
        dfl = TransformerQuantileForecaster.load(dfl_path, threads=2)
        variants["DF-LCQT"] = BayesianTransformerForecaster([dfl], mc_samples=1)
        variants["DF-LCQT + MC dropout (16)"] = BayesianTransformerForecaster([dfl], mc_samples=16)
    sets = {"validation": [make_config(sc, s, 16000, 0, 20, 2) for s in VAL_SEEDS
                           for sc in VAL_SCENARIOS_BY_FAMILY["synthetic"]],
            "shift (test, OOD)": [make_config("shift", s, 16000, 0, 20, 2) for s in TEST_SEEDS[:4]]}
    rows = []
    for set_name, cfgs in sets.items():
        traces = [generate_traffic(c.network, c.traffic, c.num_slots, c.seed) for c in cfgs]
        Xp, Xf, Y = build_sequence_dataset(traces, cfgs[0].network, cfgs[0].control)
        ll = np.array([c.deadline_slots <= 10 for c in cfgs[0].network.cells])
        for name, f in variants.items():
            q = f.predict_batch(Xp, Xf)
            m = forecast_metrics(q.reshape(-1, 6), Y.reshape(-1), f.quantiles)
            mll = forecast_metrics(q[:, ll].reshape(-1, 6), Y[:, ll].reshape(-1), f.quantiles)
            rows.append({"set": set_name, "model": name, "pinball": m["pinball_mean"],
                         "pinball_ll": mll["pinball_mean"], "cov90": m["interval90_coverage"],
                         "width90_rel": m["interval90_width_rel"], "cov95": m["coverage_q95"],
                         "cov95_ll": mll["coverage_q95"]})
            print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS_DIR, "bayes_forecast_quality.csv"), index=False)
    print(df.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
