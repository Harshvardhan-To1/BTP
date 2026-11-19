"""Trace-driven test (real 5G sessions) and the BPN overfitting check.

    python3 -m fhlm.hybrid cem --policy {pred_maxweight_cem,cem_policy_v2,bpn2} --family real5g --num-seeds K --tag kK
    python3 -m fhlm.exp_real5g

Every CEM-tuned controller (BPN v2 and both strongest baselines) is tuned twice on TRAINING sessions, on
K = 2 and K = 8 policy-search episodes, then all are evaluated on the same 20 test seeds drawn from the
disjoint TEST session pool. If BPN's lead came from fitting 8 parameters to the search episodes, it would
shrink or vanish with K = 2 while the 2-3-parameter baselines held up.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from .hybrid import load_params
from .run_experiments import run_jobs, RESULTS_DIR, PRIMARY_METRIC
from .scenarios import TEST_SEEDS, DEFAULT_SLOTS, DEFAULT_WARMUP

OUT = os.path.join(RESULTS_DIR, "real5g")
SCEN = ("real_moderate", "real_high")
CEM = {"pred_maxweight_cem": "pred_maxweight_cem__search", "cem_policy_v2": "cem_policy_v2__search",
       "bpn2": "bpn2__search"}


def holm(p):
    p = np.asarray(p)
    order = np.argsort(p)
    adj = np.empty_like(p)
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, (len(p) - r) * p[i])
        adj[i] = min(1.0, run)
    return adj


def main(ks=(2, 8), workers=4):
    os.makedirs(OUT, exist_ok=True)
    jobs = []
    for sc in SCEN:
        for seed in TEST_SEEDS:
            for m in ("proposed", "oracle_kkt", "static_equal"):
                jobs.append((sc, seed, m, {}, 20, 2, DEFAULT_SLOTS, DEFAULT_WARMUP, ""))
            for k in ks:
                for pol, meth in CEM.items():
                    p = dict(load_params(pol, "gbm", "real5g", f"k{k}"), _k=k)
                    jobs.append((sc, seed, meth, p, 20, 2, DEFAULT_SLOTS, DEFAULT_WARMUP, ""))
    df = run_jobs(jobs, workers)
    df["k"] = df.params.apply(lambda s: json.loads(s).get("_k", 0))
    df["label"] = df.apply(lambda r: r.method.replace("__search", "") + (f"_k{r.k}" if r.k else ""), axis=1)
    df.to_csv(os.path.join(OUT, "runs.csv"), index=False)

    rows, tests = [], []
    for sc in SCEN:
        d = df[df.scenario == sc]
        piv = d.pivot_table(index="seed", columns="label", values=PRIMARY_METRIC)
        for lab in piv.columns:
            rows.append(dict(scenario=sc, method=lab, V_w_pct=100 * piv[lab].mean(),
                             ll_pct=100 * d[d.label == lab].violation_ratio_ll.mean(),
                             embb_pct=100 * d[d.label == lab].violation_ratio_embb.mean(),
                             util_pct=100 * d[d.label == lab].fh_utilisation.mean()))
        for k in ks:
            bp = piv[f"bpn2_k{k}"]
            base = np.minimum(piv[f"pred_maxweight_cem_k{k}"].mean(), piv[f"cem_policy_v2_k{k}"].mean())
            best = f"pred_maxweight_cem_k{k}" if piv[f"pred_maxweight_cem_k{k}"].mean() == base else f"cem_policy_v2_k{k}"
            for ref in (best, "proposed"):
                diff = piv[ref] - bp
                tests.append(dict(scenario=sc, k=k, bpn=f"bpn2_k{k}", against=ref,
                                  bpn_pct=100 * bp.mean(), ref_pct=100 * piv[ref].mean(),
                                  rel_gain_pct=100 * diff.mean() / piv[ref].mean(), wins=int((diff > 0).sum()),
                                  n=len(diff), p=float(wilcoxon(diff).pvalue)))
        diff = piv["bpn2_k8"] - piv["bpn2_k2"]
        tests.append(dict(scenario=sc, k="2 vs 8", bpn="bpn2_k2", against="bpn2_k8", bpn_pct=100 * piv["bpn2_k2"].mean(),
                          ref_pct=100 * piv["bpn2_k8"].mean(), rel_gain_pct=100 * diff.mean() / piv["bpn2_k8"].mean(),
                          wins=int((diff > 0).sum()), n=len(diff), p=float(wilcoxon(diff).pvalue)))
    summ = pd.DataFrame(rows)
    t = pd.DataFrame(tests)
    t["p_holm"] = holm(t.p.values)
    summ.to_csv(os.path.join(OUT, "summary.csv"), index=False)
    t.to_csv(os.path.join(OUT, "paired_tests.csv"), index=False)
    pd.set_option("display.width", 200)
    print(summ.round(2).to_string(index=False))
    print(t.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
