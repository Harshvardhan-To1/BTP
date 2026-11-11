"""Decision-focused training of the LCQT through a differentiable KKT allocation layer (DF-LCQT).

    python3 -m fhlm.decision_focused [--out models/fhlm_lcqt_T20_d2_dfl.pt]

A quantile forecaster trained on pinball loss is accurate *per cell*, but the
link is lost or won by how the KKT rule trades the cells' tails against each
other. Here the allocation rule of proposed.py becomes the last layer of the
network and the Transformer is fine-tuned on the cost the rule actually pays:

    q_i      = LCQT(history)                                  (quantiles, bits/slot)
    r_i(l)   = clip(B_i + Q_i(1 - l / w_i), 0, cap_i)         (KKT rule, Q_i piecewise linear in q_i)
    l*       : sum_i r_i(l*) = C                              (bisection, no gradient)
    loss     = sum_i p_i (D_i + 1) (B_i + r*_i - r_i(l*))^+ / (C H)   +  beta * pinball(q, r*)

The first term is the pathwise lower bound on violated volume from the
shortfall sandwich, (D+1)(r* - r)^+ <= dropped bits, weighted by operator
priority p_i like V_w. Gradients pass through l* by the implicit-function
theorem on the binding constraint g(l, q) = sum_i r_i(l, q) - C = 0:

    dl*/dq = - (dg/dq) / (dg/dl),

implemented as one Newton step from the detached root, which has exactly this
derivative. The pinball term keeps q interpretable as quantiles.

Contexts (backlog rate B, weights w) depend on the controller, so they are
logged by running the KKT rule closed-loop on the TRAINING seeds (behaviour
policy = the pretrained LCQT, then one DAgger round with the fine-tuned
model); early stopping uses the same surrogate on logged VALIDATION seeds.
TEST seeds are never touched.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Dict, List

import numpy as np

from .scenarios import TRAIN_SEEDS, VAL_SEEDS, TRAIN_LOADS, train_config, make_config, VAL_SCENARIOS_BY_FAMILY
from .traffic import generate_traffic
from .simulator import run_simulation, Controller, Observation
from .controllers import deadline_weights, backlog_rate_obs
from .demand import required_rates
from .forecast import build_features, forecast_metrics, _scale
from .proposed import UncertaintyAwareAllocator
from .transformer import TransformerQuantileForecaster, build_patches


class LoggingController(Controller):
    """Runs `inner` unchanged and records the context of every KKT decision."""

    def __init__(self, inner: UncertaintyAwareAllocator, patches: int):
        self.inner = inner
        self.name = inner.name
        self.patches = patches
        self.rows: Dict[str, List[np.ndarray]] = {k: [] for k in ("xp", "xf", "B", "w", "slot", "obs_slot")}

    def reset(self, net, ctrl, rng=None) -> None:
        self.inner.reset(net, ctrl, rng)

    def decide(self, obs: Observation) -> np.ndarray:
        H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
        scale = _scale(obs.net)
        self.rows["xp"].append(build_patches(obs.history_fh_demand, obs.deadlines, scale, H, self.patches))
        self.rows["xf"].append(build_features(obs.history_fh_demand, obs.se, obs.net, obs.ctrl).astype(np.float32))
        self.rows["B"].append(backlog_rate_obs(obs))
        self.rows["w"].append(deadline_weights(obs, self.inner.w_min))
        self.rows["slot"].append(obs.slot)
        self.rows["obs_slot"].append(obs.obs_slot)
        return self.inner.decide(obs)


def collect(cfgs, model: TransformerQuantileForecaster, min_hist: int) -> Dict[str, np.ndarray]:
    out: Dict[str, List[np.ndarray]] = {k: [] for k in ("xp", "xf", "B", "w", "y")}
    for cfg in cfgs:
        tr = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
        log = LoggingController(UncertaintyAwareAllocator(model, calibrate=False, name="dfl_behaviour"),
                                model.hp["patches"])
        run_simulation(cfg, log, trace=tr)
        dl = np.array([c.deadline_slots for c in cfg.network.cells])
        T = cfg.control.interval_slots
        for k, (t, o) in enumerate(zip(log.rows["slot"], log.rows["obs_slot"])):
            if o < min_hist or t + T > tr.num_slots:
                continue
            for key in ("xp", "xf", "B", "w"):
                out[key].append(log.rows[key][k])
            out["y"].append(required_rates(tr.fh_demand_bits[:, o:t + T], dl))
    return {k: np.stack(v).astype(np.float32) for k, v in out.items()}


def kkt_layer(q, B, w, cap: float, caps, levels, iters: int = 40):
    """Differentiable KKT rule. q [b,N,K], B/w [b,N] (bits/slot), caps [N]. Returns r [b,N]."""
    import torch
    lv = torch.as_tensor(levels, dtype=q.dtype)
    K = lv.shape[0]

    def alloc(lam):
        p = 1.0 - lam[:, None] / w
        idx = torch.clamp(torch.searchsorted(lv, p.clamp(0.0, 1.0).contiguous()), 1, K - 1)
        lo_l, hi_l = lv[idx - 1], lv[idx]
        frac = ((p - lo_l) / (hi_l - lo_l)).clamp(min=0.0)
        qlo = torch.gather(q, -1, (idx - 1).unsqueeze(-1)).squeeze(-1)
        qhi = torch.gather(q, -1, idx.unsqueeze(-1)).squeeze(-1)
        Q = torch.clamp(qlo + frac * (qhi - qlo), min=0.0)
        r = torch.where(p <= 0.0, torch.zeros_like(Q), B + Q)
        return torch.minimum(torch.clamp(r, min=0.0), caps)

    with torch.no_grad():
        binding = alloc(torch.zeros(q.shape[0], dtype=q.dtype)).sum(-1) > cap
        lo = torch.zeros(q.shape[0], dtype=q.dtype)
        hi = w.max(-1).values.clone()
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            over = alloc(mid).sum(-1) > cap
            lo = torch.where(over, mid, lo)
            hi = torch.where(over, hi, mid)
        lam0 = torch.where(binding, hi, torch.zeros_like(hi))
    if not torch.is_grad_enabled():
        return alloc(lam0)
    lam_v = lam0.clone().requires_grad_(True)
    g = alloc(lam_v).sum(-1) - cap
    dg = torch.autograd.grad(g.sum(), lam_v, retain_graph=True)[0].detach()
    ok = binding & (dg.abs() > 1e-9)
    newton = lam0 - torch.where(ok, g / torch.where(ok, dg, torch.ones_like(dg)), torch.zeros_like(g))
    return alloc(newton)


def finetune(model: TransformerQuantileForecaster, train: Dict[str, np.ndarray], val: Dict[str, np.ndarray],
             net, ctrl, epochs: int = 12, lr: float = 3e-4, beta: float = 1.0, batch: int = 64, patience: int = 4,
             seed: int = 0, threads: int = 4):
    import torch
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    scale = torch.tensor(_scale(net), dtype=torch.float32)
    caps = torch.tensor(np.array(net.peak_bits_per_slot), dtype=torch.float32)
    cap = float(net.usable_bits_per_slot)
    H = ctrl.interval_slots + ctrl.telemetry_delay_slots
    prio = torch.tensor([c.priority for c in net.cells], dtype=torch.float32)
    vol = torch.tensor([c.deadline_slots + 1.0 for c in net.cells], dtype=torch.float32)
    levels = torch.tensor(model.quantiles, dtype=torch.float32)
    cond = torch.tensor(model._cond)
    T = {k: torch.from_numpy(v) for k, v in train.items()}
    V = {k: torch.from_numpy(v) for k, v in val.items()}

    def losses(d, idx, train_mode):
        model.net.train(train_mode)
        qn = model.net(d["xp"][idx], d["xf"][idx], cond.expand(len(idx), -1, -1))
        q = qn * scale[:, None]
        r = kkt_layer(q, d["B"][idx], d["w"][idx], cap, caps, levels)
        short = torch.clamp(d["B"][idx] + d["y"][idx] - r, min=0.0)
        dfl = (short * prio * vol).sum(-1).mean() / (cap * H)
        yn = d["y"][idx] / scale
        e = yn.unsqueeze(-1) - qn
        pin = torch.maximum(levels * e, (levels - 1) * e).mean()
        return dfl, pin

    def evaluate(d):
        dfl_s, pin_s, n = 0.0, 0.0, len(d["y"])
        with torch.no_grad():
            for s in range(0, n, 256):
                idx = torch.arange(s, min(s + 256, n))
                a, b = losses(d, idx, False)
                dfl_s += float(a) * len(idx)
                pin_s += float(b) * len(idx)
        return dfl_s / n, pin_s / n

    opt = torch.optim.AdamW(model.net.parameters(), lr=lr, weight_decay=1e-4)
    base = evaluate(V)
    best, bad = base[0] + beta * base[1], 0
    init_state = {k: v.detach().clone() for k, v in model.net.state_dict().items()}
    best_state = None
    hist = [{"epoch": -1, "val_dfl": base[0], "val_pinball": base[1]}]
    print(f"[dfl] pretrained  val dfl {base[0]:.5f} pinball {base[1]:.5f}", flush=True)
    t0 = time.perf_counter()
    for ep in range(epochs):
        perm = torch.randperm(len(T["y"]))
        tot = 0.0
        for s in range(0, len(perm), batch):
            idx = perm[s:s + batch]
            dfl, pin = losses(T, idx, True)
            loss = dfl + beta * pin
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.net.parameters(), 1.0)
            opt.step()
            tot += loss.item() * len(idx)
        vd, vp = evaluate(V)
        hist.append({"epoch": ep, "train_loss": tot / len(perm), "val_dfl": vd, "val_pinball": vp})
        print(f"[dfl] epoch {ep:2d} train {tot / len(perm):.5f} val dfl {vd:.5f} pinball {vp:.5f}", flush=True)
        if vd + beta * vp < best - 1e-7:
            best, bad = vd + beta * vp, 0
            best_state = {k: v.detach().clone() for k, v in model.net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    model.net.load_state_dict(best_state if best_state is not None else init_state)
    model.net.eval()
    return {"history": hist, "train_time_s": time.perf_counter() - t0, "pretrained_val": base,
            "improved": best_state is not None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", default="models/fhlm_lcqt_T20_d2.pt")
    ap.add_argument("--out", default="models/fhlm_lcqt_T20_d2_dfl.pt")
    ap.add_argument("--report", default="results/fhlm/forecast_training_lcqt_T20_d2_dfl.json")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--delay", type=int, default=2)
    ap.add_argument("--slots", type=int, default=16000)
    ap.add_argument("--family", default="synthetic", choices=["synthetic", "3gpp", "markov"])
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--beta", type=float, default=1.0, help="weight of the pinball regulariser")
    ap.add_argument("--dagger", type=int, default=1, help="re-log contexts with the fine-tuned model and refit")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--cache", default=None, help="npz cache of the first-round logged contexts")
    args = ap.parse_args(argv)

    model = TransformerQuantileForecaster.load(args.init, threads=args.threads)
    t0 = time.perf_counter()
    tr_cfgs = [train_config(TRAIN_LOADS[k % len(TRAIN_LOADS)], s, args.slots, args.interval, args.delay, args.family)
               for k, s in enumerate(TRAIN_SEEDS)]
    va_cfgs = [make_config(sc, s, args.slots, 0, args.interval, args.delay)
               for s in VAL_SEEDS for sc in VAL_SCENARIOS_BY_FAMILY[args.family]]
    net, ctrl = tr_cfgs[0].network, tr_cfgs[0].control
    H = args.interval + args.delay
    min_hist = model.hp["patches"] * H
    rounds = []
    cache = args.cache or f"/tmp/fhlm_dfl_contexts_T{args.interval}_d{args.delay}_{args.family}.npz"
    if os.path.exists(cache):
        z = np.load(cache)
        train = {k[3:]: z[k] for k in z.files if k.startswith("tr_")}
        val = {k[3:]: z[k] for k in z.files if k.startswith("va_")}
    else:
        train = collect(tr_cfgs, model, min_hist)
        val = collect(va_cfgs, model, min_hist)
        np.savez(cache, **{f"tr_{k}": v for k, v in train.items()}, **{f"va_{k}": v for k, v in val.items()})
    print(f"logged contexts: train {train['y'].shape}, val {val['y'].shape} ({time.perf_counter() - t0:.0f}s)",
          flush=True)
    for rnd in range(1 + args.dagger):
        info = finetune(model, train, val, net, ctrl, epochs=args.epochs, lr=args.lr, beta=args.beta,
                        threads=args.threads, seed=rnd)
        rounds.append(info)
        if rnd < args.dagger:
            new = collect(tr_cfgs, model, min_hist)
            train = {k: np.concatenate([train[k], new[k]]) for k in train}
            val = collect(va_cfgs, model, min_hist)
            print(f"[dagger {rnd + 1}] train contexts {train['y'].shape}", flush=True)

    model.meta.update({"decision_focused": True, "beta": args.beta, "init": args.init})
    model.save(args.out)
    from .forecast import DEFAULT_QUANTILES
    from .transformer import build_sequence_dataset
    vt = [generate_traffic(c.network, c.traffic, c.num_slots, c.seed) for c in va_cfgs]
    Vp, Vf, VY = build_sequence_dataset(vt, net, ctrl)
    report = {"init": args.init, "beta": args.beta, "lr": args.lr, "dagger_rounds": args.dagger,
              "rounds": [{"history": r["history"], "train_time_s": r["train_time_s"], "improved": r["improved"]}
                         for r in rounds],
              "validation_forecast": forecast_metrics(model._predict_batch(Vp, Vf).reshape(-1, len(DEFAULT_QUANTILES)),
                                                      VY.reshape(-1), model.quantiles)}
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w") as f:
        json.dump(report, f, indent=2)
    print(f"saved model -> {args.out}\nreport -> {args.report}")


if __name__ == "__main__":
    main()
