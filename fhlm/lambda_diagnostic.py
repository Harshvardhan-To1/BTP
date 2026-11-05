"""Diagnostic for the extended study: how hard does the link constraint bind under the KKT rule?

    python -m fhlm.lambda_diagnostic

For the high-load scenario of each family it records, over all decision epochs of a few test seeds, the
distribution of the common weighted tail probability lambda* of the KKT rule, the fraction of epochs in which
the constraint binds (lambda* > 0) and the fraction in which lambda* >= w_eMBB, i.e. the eMBB cells are cut
to their lowest forecast quantile (plus a proportional share of the slack). Output:
results/fhlm/lambda_diagnostic.json (used by make_extended_tables for the text macros).
"""
from __future__ import annotations

import json
import os

import numpy as np

from .run_experiments import RESULTS_DIR, build_controller, tuned_params
from .scenarios import make_config, TEST_SEEDS
from .simulator import run_simulation
from .traffic import generate_traffic


def main(num_seeds: int = 3, slots: int = 8000, warmup: int = 500):
    out = {}
    for sc, fam in (("high", "synthetic"), ("tgpp_high", "3gpp"), ("mm_high", "markov")):
        lams = []
        for seed in TEST_SEEDS[:num_seeds]:
            cfg = make_config(sc, seed, slots, warmup)
            tr = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
            ctrl = build_controller("proposed", tuned_params("proposed", sc), 20, 2, fam)
            rec = []
            orig = ctrl.decide

            def decide(obs, _o=orig, _c=ctrl, _r=rec):
                b = _o(obs)
                _r.append(float(getattr(_c, "last_lambda", 0.0)))
                return b
            ctrl.decide = decide
            run_simulation(cfg, ctrl, trace=tr)
            lams.extend(rec[warmup // 20:])
        lam = np.array(lams)
        w_embb = 1.0
        out[sc] = {
            "family": fam, "epochs": int(len(lam)), "frac_binding": float(np.mean(lam > 0)),
            "frac_embb_at_floor": float(np.mean(lam >= w_embb - 1e-9)),
            "lambda_median": float(np.median(lam)), "lambda_q25": float(np.percentile(lam, 25)),
            "lambda_q75": float(np.percentile(lam, 75)),
            "ll_level_at_median_lambda": float(1 - min(np.median(lam), 3.0) / 3.0),
        }
        print(sc, json.dumps(out[sc]))
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "lambda_diagnostic.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
