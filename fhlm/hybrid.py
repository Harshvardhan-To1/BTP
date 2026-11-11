"""Back-pressure newsvendor (BPN): one policy class that contains predictive MaxWeight and the KKT rule.

    python3 -m fhlm.hybrid cem --policy bpn [--forecaster gbm|lcqt] [--family synthetic]

Diagnosis behind it (Family S, high load, 20 test seeds): the KKT rule protects the
2-ms cells (LL violations 3.4 %) by reserving their upper quantiles, but a budget is
a per-cell cap, so reserved-but-unused capacity is lost (link utilisation 72.2 %
vs 74.9 % for predictive MaxWeight) and the eMBB cells starve (12.3 % vs 7.4 %).
Predictive MaxWeight fills the link in back-pressure order with median demands and
wastes less, but it ignores deadlines and forecast uncertainty.

BPN decides in two stages per control epoch:

  1. Base, in back-pressure order. b_i = a Q_i / T + (1 - a) B_i mixes the drain-the-
     queue rate of MaxWeight with the deadline-aware backlog rate of the KKT rule.
     Each cell asks for d_i = b_i + F_i^{-1}(p0_c) at a class level p0_c, and the link
     is filled greedily by the score s_i = v_c (Q_i + l H m_i) (queue plus l horizons
     of forecast median m_i: the predictive back-pressure weight).
  2. Margin, by the KKT rule. Leftover capacity raises cells towards their upper
     quantiles at equal weighted risk: r_i = max(base_i, b_i + F_i^{-1}(1 - lambda / omega_c)),
     with lambda found by bisection so that sum r_i = C.

Special cases: a = 1, p0 = 0.5, l = lookahead, v_LL = priority -> predictive MaxWeight
(margin 0); p0 -> 0 with a = 0 -> the KKT rule with class weights omega. The six
parameters theta = (p0_LL, p0_eMBB, log v_LL, l, log omega_LL, a) are learned by the
cross-entropy method on TRAINING seeds only; predictive MaxWeight gets the same
search over its own parameters ("pred_maxweight_cem") so that tuning effort is equal.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, Any

import numpy as np

from .simulator import Controller, Observation
from .controllers import waterfill, backlog_rate_obs, backlog_fh_bits
from .controllers_ext import PredictiveMaxWeight, cem_search
from .proposed import interp_quantile


ETA_GREEDY = 6.0     # eta at the top of its search range means strict back-pressure (greedy) order


class BackpressureNewsvendor(Controller):
    name = "bpn"

    def __init__(self, forecaster, p0_ll: float = 0.5, p0_embb: float = 0.5, v_ll: float = 3.0,
                 lookahead: float = 1.0, omega_ll: float = 3.0, a: float = 1.0, eta: float = ETA_GREEDY,
                 mu: float = 0.0, name: str = "bpn"):
        self.forecaster = forecaster
        self.p0_ll, self.p0_embb, self.v_ll = float(p0_ll), float(p0_embb), float(v_ll)
        self.lookahead, self.omega_ll, self.a = float(lookahead), float(omega_ll), float(a)
        self.eta, self.mu = float(eta), float(mu)
        self.name = name
        self.stats = {"decisions": 0, "stage2_epochs": 0}

    def reset(self, net, ctrl, rng=None) -> None:
        self.stats = {"decisions": 0, "stage2_epochs": 0}

    def decide(self, obs: Observation) -> np.ndarray:
        T = obs.ctrl.interval_slots
        H = T + obs.ctrl.telemetry_delay_slots
        q = np.asarray(self.forecaster.predict_quantiles(obs), dtype=float)
        levels = np.asarray(self.forecaster.quantiles, dtype=float)
        caps, C, n = obs.budget_caps, obs.capacity, obs.num_cells
        is_ll = obs.deadlines <= 10
        Q = backlog_fh_bits(obs)
        back = self.a * Q / T + (1.0 - self.a) * backlog_rate_obs(obs)
        med = q[:, self.forecaster.median_index]
        self.stats["decisions"] += 1

        base_dem = np.minimum(back + (1.0 + self.mu) * interp_quantile(
            levels, q, np.where(is_ll, self.p0_ll, self.p0_embb)), caps)
        v = np.where(is_ll, self.v_ll, 1.0)
        pressure = Q + self.lookahead * H * med
        if base_dem.sum() > C and self.eta < ETA_GREEDY:
            # shortage shared in proportion to v_c (pressure / mean pressure)^eta: eta = 0 is the class-weighted
            # water-fill of the class-level policy, eta -> infinity the strict back-pressure order
            rel = pressure / max(float(pressure.mean()), 1e-9)
            return waterfill(base_dem, v * np.power(np.maximum(rel, 1e-9), self.eta), C, caps,
                             distribute_leftover=False)
        score = v * pressure
        alloc = np.zeros(n)
        remaining = C
        for i in np.argsort(-score):
            give = min(base_dem[i], remaining)
            alloc[i] = give
            remaining -= give
            if remaining <= 0:
                break
        if remaining <= 1e-9:
            return alloc

        self.stats["stage2_epochs"] += 1
        omega = np.where(is_ll, self.omega_ll, 1.0)

        def r_of(lam: float) -> np.ndarray:
            p = 1.0 - lam / omega
            tgt = np.where(p <= 0.0, 0.0, back + interp_quantile(levels, q, np.clip(p, 0.0, 1.0)))
            return np.maximum(alloc, np.minimum(tgt, caps))

        r0 = r_of(0.0)
        if r0.sum() <= C:
            return waterfill(r0, np.ones(n), C, caps)
        lo, hi = 0.0, float(omega.max())
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            if r_of(mid).sum() > C:
                lo = mid
            else:
                hi = mid
        r = r_of(hi)
        return waterfill(r, np.ones(n), C, caps)


# ---------------------------------------------------------------------------
# parameter spaces for the cross-entropy search
# ---------------------------------------------------------------------------
def _bpn_params(th) -> Dict[str, float]:
    return {"p0_ll": float(th[0]), "p0_embb": float(th[1]), "v_ll": float(np.exp(th[2])),
            "lookahead": float(th[3]), "omega_ll": float(np.exp(th[4])), "a": float(th[5])}


def _bpn2_params(th) -> Dict[str, float]:
    return dict(_bpn_params(th[:6]), eta=float(th[6]), mu=float(th[7]))


def _cls_params(th) -> Dict[str, float]:
    return {"p_ll": float(th[0]), "p_embb": float(th[1]), "w_ll": float(np.exp(th[2]))}


def _pmw_params(th) -> Dict[str, float]:
    return {"margin": float(th[0]), "lookahead": float(th[1])}


SPACES = {
    # mean0 starts BPN at predictive MaxWeight's tuned point (margin 0.25 ~ level 0.6, lookahead 2)
    "bpn": dict(to_params=_bpn_params,
                mean0=np.array([0.6, 0.6, np.log(3.0), 2.0, np.log(3.0), 1.0]),
                std0=np.array([0.15, 0.15, 0.6, 0.8, 0.6, 0.3]),
                lo=np.array([0.05, 0.05, np.log(0.3), 0.0, np.log(0.3), 0.0]),
                hi=np.array([0.99, 0.99, np.log(30.0), 6.0, np.log(30.0), 1.0])),
    "pred_maxweight_cem": dict(to_params=_pmw_params,
                               mean0=np.array([0.25, 2.0]), std0=np.array([0.2, 0.8]),
                               lo=np.array([-0.5, 0.0]), hi=np.array([1.5, 6.0])),
    # BPN v2: adds the sharing exponent eta and the median-margin mu, so that it contains BOTH tuned baselines:
    # predictive MaxWeight (a=1, p0=0.5, mu=margin, eta=greedy) and the class-level policy (a=0, p0=class
    # levels, v_LL=w_LL, eta=0). The search is started from each baseline's own CEM optimum (see starts_for).
    "bpn2": dict(to_params=_bpn2_params,
                 mean0=np.array([0.6, 0.6, np.log(3.0), 2.0, np.log(3.0), 1.0, ETA_GREEDY, 0.0]),
                 std0=np.array([0.1, 0.1, 0.4, 0.5, 0.4, 0.2, 1.5, 0.1]),
                 lo=np.array([0.05, 0.05, np.log(0.3), 0.0, np.log(0.3), 0.0, 0.0, -0.5]),
                 hi=np.array([0.99, 0.99, np.log(30.0), 6.0, np.log(30.0), 1.0, ETA_GREEDY, 1.5])),
    # the extended study's class-level policy, re-searched with the same budget as BPN
    "cem_policy_v2": dict(to_params=_cls_params,
                          mean0=np.array([0.85, 0.5, np.log(3.0)]), std0=np.array([0.1, 0.15, 0.5]),
                          lo=np.array([0.05, 0.05, np.log(0.5)]), hi=np.array([0.995, 0.995, np.log(20.0)])),
}


def starts_for(policy: str, forecaster: str, family: str, sp) -> list:
    """Search starts: the default mean, and for bpn2 the CEM optima of the two baselines it contains."""
    if policy != "bpn2":
        return [("default", sp["mean0"])]
    starts = []
    try:
        pm = load_params("pred_maxweight_cem", forecaster, family)
        starts.append(("pred_maxweight_cem", np.array([0.5, 0.5, np.log(3.0), pm["lookahead"], np.log(3.0), 1.0,
                                                       ETA_GREEDY, pm["margin"]])))
    except FileNotFoundError:
        pass
    try:
        cl = load_params("cem_policy_v2", forecaster, family)
        starts.append(("cem_policy_v2", np.array([cl["p_ll"], cl["p_embb"], np.log(cl["w_ll"]), 1.0, np.log(3.0),
                                                  0.0, 0.0, 0.0])))
    except FileNotFoundError:
        pass
    return starts or [("default", sp["mean0"])]


def params_path(policy: str, forecaster: str, family: str) -> str:
    from .run_experiments import RESULTS_DIR, _fam_suffix
    fc = "" if forecaster == "gbm" else f"_{forecaster}"
    return os.path.join(RESULTS_DIR, f"hybrid_{policy}{fc}{_fam_suffix(family)}.json")


def load_params(policy: str, forecaster: str, family: str) -> Dict[str, Any]:
    path = params_path(policy, forecaster, family)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path}: run python3 -m fhlm.hybrid cem --policy {policy} --forecaster {forecaster}")
    with open(path) as f:
        return json.load(f)["selected"]


def build(policy: str, forecaster, params: Dict[str, Any], name: str):
    if policy in ("bpn", "bpn2"):
        return BackpressureNewsvendor(forecaster, name=name, **params)
    if policy == "cem_policy_v2":
        from .controllers_ext import ClassLevelPolicy
        c = ClassLevelPolicy(forecaster, **params)
        c.name = name
        return c
    if policy == "pred_maxweight_cem":
        c = PredictiveMaxWeight(forecaster, margin=params["margin"], lookahead=params["lookahead"])
        c.name = name
        return c
    raise ValueError(policy)


def cmd_cem(args):
    from .scenarios import TRAIN_SEEDS, TRAIN_LOADS
    from .run_experiments import run_jobs, PRIMARY_METRIC, ensure_forecaster
    sp = SPACES[args.policy]
    method = {"gbm": "", "lcqt": "_tf"}[args.forecaster]
    method = f"{args.policy}{method}__search"
    if args.forecaster == "gbm":
        ensure_forecaster(args.interval, args.delay, args.family)
    episodes = [(TRAIN_SEEDS[k], TRAIN_LOADS[k % len(TRAIN_LOADS)]) for k in range(len(TRAIN_SEEDS))
                if TRAIN_LOADS[k % len(TRAIN_LOADS)] in (0.65, 0.8)][:args.num_seeds]

    def evaluate(thetas):
        jobs = []
        for j, th in enumerate(thetas):
            params = dict(sp["to_params"](th), _cem=j)
            for seed, load in episodes:
                jobs.append(("__train__", seed, method, params, args.interval, args.delay, args.slots, args.warmup, "",
                             None, None, load, args.family))
        df = run_jobs(jobs, args.workers)
        df["j"] = df.params.apply(lambda s_: json.loads(s_)["_cem"])
        return df.groupby("j")[PRIMARY_METRIC].mean().reindex(range(len(thetas))).values

    starts = starts_for(args.policy, args.forecaster, args.family, sp)
    cands, hists = [], []
    for k, (label, m0) in enumerate(starts):
        print(f"[cem] start {label}: {np.round(m0, 3).tolist()}", flush=True)
        theta, hist = cem_search(evaluate, mean0=m0, std0=sp["std0"], lo=sp["lo"], hi=sp["hi"],
                                 iters=args.iters, pop=args.pop, elite=args.elite, seed=k)
        cands += [theta, np.array(hist[-1]["mean"])]
        hists.append({"start": label, "mean0": m0.tolist(), "history": hist})
    # final pick: re-evaluate every candidate (best sample and final mean of each start) on the same episodes
    costs = evaluate(np.stack(cands))
    chosen = cands[int(np.argmin(costs))]
    out = {"policy": args.policy, "forecaster": args.forecaster, "family": args.family,
           "selected": sp["to_params"](chosen), "train_cost": float(np.min(costs)), "episodes": episodes,
           "slots": args.slots, "starts": hists}
    path = params_path(args.policy, args.forecaster, args.family)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out["selected"], indent=1), "->", path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["cem"])
    ap.add_argument("--policy", default="bpn", choices=list(SPACES))
    ap.add_argument("--forecaster", default="gbm", choices=["gbm", "lcqt"])
    ap.add_argument("--family", default="synthetic")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--delay", type=int, default=2)
    ap.add_argument("--slots", type=int, default=10000)
    ap.add_argument("--warmup", type=int, default=1000)
    ap.add_argument("--num-seeds", type=int, default=8)
    ap.add_argument("--iters", type=int, default=10)
    ap.add_argument("--pop", type=int, default=20)
    ap.add_argument("--elite", type=int, default=5)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    if args.command == "cem":
        cmd_cem(args)


if __name__ == "__main__":
    main()
