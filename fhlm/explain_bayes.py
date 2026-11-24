"""Uncertainty and explainability analysis of the Bayesian LCQT forecaster (B2).

    python3 -m fhlm.explain_bayes

Uses the three trained LCQT members (ensemble x MC dropout, 3 x 8 posterior
samples) on validation seeds (in-distribution) and on the held-out 'shift'
scenario (first 4 test seeds, diagnostic only). Reports

  * uncertainty: epistemic spread (posterior disagreement on the median) and
    aleatoric width (mean 5-95 % interval of a single sample), in-distribution
    vs shift, and the q95 coverage of the mixture when rows are split by
    epistemic spread;
  * explainability: the cross-cell attention map (stored only; it is close to
    uniform), gradient x input attribution of the LL q95 forecast over the 16
    history patches, and a counterfactual that swaps a cell's deadline/priority
    conditioning (FiLM) between the LL and eMBB classes.

Writes results/fhlm/bayes_explain.json and report/figures/fig_bayes_explain.png.
"""
from __future__ import annotations

import json
import os

import numpy as np

from .scenarios import VAL_SEEDS, TEST_SEEDS, make_config, VAL_SCENARIOS_BY_FAMILY
from .traffic import generate_traffic
from .transformer import TransformerQuantileForecaster, BayesianTransformerForecaster, build_sequence_dataset
from .run_experiments import tf_model_path, RESULTS_DIR

FIG_DIR = os.path.join(os.path.dirname(__file__), "..", "report", "figures")
LEVELS = np.array([0.05, 0.25, 0.5, 0.75, 0.9, 0.95])


def _dataset(cfgs):
    traces = [generate_traffic(c.network, c.traffic, c.num_slots, c.seed) for c in cfgs]
    return build_sequence_dataset(traces, cfgs[0].network, cfgs[0].control)


def _uncertainty(bayes, Xp, Xf, Y, ll):
    samp = np.concatenate([bayes._samples(Xp[s:s + 64], Xf[s:s + 64]) for s in range(0, len(Xp), 64)], axis=1)
    from .transformer import mixture_quantiles
    mix = mixture_quantiles(samp, bayes.quantiles)                       # [B, N, K]
    med = samp[..., 2]
    epi = med.std(0) / np.maximum(med.mean(0), 1e-6)                     # [B, N]
    alea = ((samp[..., 5] - samp[..., 0]) / np.maximum(samp[..., 2], 1e-6)).mean(0)
    cover = Y <= mix[..., 5]
    hi = epi >= np.median(epi)
    return {
        "epistemic_mean": float(epi.mean()), "epistemic_ll": float(epi[:, ll].mean()),
        "aleatoric_mean": float(alea.mean()),
        "q95_cov_low_epistemic": float(cover[~hi].mean()), "q95_cov_high_epistemic": float(cover[hi].mean()),
        "width90_low_epistemic": float(((mix[..., 4] - mix[..., 0]) / np.maximum(mix[..., 2], 1e-6))[~hi].mean()),
        "width90_high_epistemic": float(((mix[..., 4] - mix[..., 0]) / np.maximum(mix[..., 2], 1e-6))[hi].mean()),
    }, mix, epi


def _attention_and_saliency(member, Xp, Xf, ll):
    import torch
    net = member.net
    net.eval()
    store = []
    layer = net.cross.layers[0]
    orig = layer.self_attn.forward

    def fwd(*a, **k):
        k["need_weights"] = True
        k["average_attn_weights"] = True
        out = orig(*a, **k)
        store.append(out[1].detach())
        return out

    layer.self_attn.forward = fwd
    c = torch.from_numpy(member._cond)
    xp = torch.from_numpy(Xp).requires_grad_(True)
    xf = torch.from_numpy(Xf).requires_grad_(True)
    q = net(xp, xf, c.expand(len(xp), -1, -1))
    layer.self_attn.forward = orig
    attn = store[0].mean(0).numpy()                                      # [N, N]
    q[:, ll, 5].sum().backward()
    gx = (xp.grad * xp).detach().abs().sum(-1)[:, ll].mean((0, 1)).numpy()   # [P]
    gs = float((xf.grad * xf).detach().abs().sum(-1)[:, ll].mean())
    sal = np.concatenate([[gs], gx])
    return attn, sal / sal.sum()


def _film_counterfactual(member, Xp, Xf, ll):
    import torch
    c = member._cond.copy()
    i_ll, i_e = int(np.where(ll)[0][0]), int(np.where(~ll)[0][0])
    swapped = c.copy()
    swapped[[i_ll, i_e]] = c[[i_e, i_ll]]
    with torch.no_grad():
        tp, tf = torch.from_numpy(Xp), torch.from_numpy(Xf)
        base = member.net(tp, tf, torch.from_numpy(c).expand(len(tp), -1, -1)).numpy()
        cf = member.net(tp, tf, torch.from_numpy(swapped).expand(len(tp), -1, -1)).numpy()
    rel = lambda a, b: float((b.mean() - a.mean()) / a.mean())
    return {"ll_cell_as_embb_q95_change": rel(base[:, i_ll, 5], cf[:, i_ll, 5]),
            "embb_cell_as_ll_q95_change": rel(base[:, i_e, 5], cf[:, i_e, 5])}


def main():
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(0)
    paths = [tf_model_path(20, 2, "synthetic", v) for v in ("", "_s1", "_s2")]
    members = [TransformerQuantileForecaster.load(p, threads=4) for p in paths]
    bayes = BayesianTransformerForecaster(members, mc_samples=8)
    val_cfgs = [make_config(sc, s, 16000, 0, 20, 2) for s in VAL_SEEDS for sc in VAL_SCENARIOS_BY_FAMILY["synthetic"]]
    shift_cfgs = [make_config("shift", s, 16000, 0, 20, 2) for s in TEST_SEEDS[:4]]
    ll = np.array([c.deadline_slots <= 10 for c in val_cfgs[0].network.cells])

    res = {}
    Vp, Vf, VY = _dataset(val_cfgs)
    Sp, Sf, SY = _dataset(shift_cfgs)
    res["validation"], _, _ = _uncertainty(bayes, Vp, Vf, VY, ll)
    res["shift"], smix, sepi = _uncertainty(bayes, Sp, Sf, SY, ll)
    attn, sal = _attention_and_saliency(members[0], Vp[:512], Vf[:512], ll)
    res["cross_cell_attention"] = attn.tolist()
    res["attn_ll_to_ll"] = float(attn[np.ix_(ll, ll)].mean())
    res["attn_ll_to_embb"] = float(attn[np.ix_(ll, ~ll)].mean())
    res["attn_embb_to_embb"] = float(attn[np.ix_(~ll, ~ll)].mean())
    res["attn_self"] = float(np.diag(attn).mean())
    res["saliency_summary_token"] = float(sal[0])
    res["saliency_patches_oldest_to_newest"] = sal[1:].tolist()
    res["saliency_last4_patches"] = float(sal[-4:].sum())
    res["film_counterfactual"] = _film_counterfactual(members[0], Vp[:512], Vf[:512], ll)
    with open(os.path.join(RESULTS_DIR, "bayes_explain.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "cross_cell_attention"}, indent=1))
    _figure(res, attn, sal, smix, sepi, SY, ll)


def _figure(res, attn, sal, mix, epi, Y, ll):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9})
    fig, ax = plt.subplots(1, 4, figsize=(15, 3.3), gridspec_kw={"width_ratios": [1.9, 1, 1.15, 1.25]})

    i = int(np.where(ll)[0][0])
    rows = slice(0, 50)
    t = np.arange(50) * 10
    a = ax[0]
    a.fill_between(t, mix[rows, i, 0], mix[rows, i, 5], color="tab:blue", alpha=0.18, label="5-95 % (mixture)")
    a.plot(t, mix[rows, i, 2], color="tab:blue", lw=1.2, label="median forecast")
    a.plot(t, Y[rows, i], color="k", lw=0.9, label="true $r^*$")
    a2 = a.twinx()
    a2.plot(t, epi[rows, i], color="tab:red", lw=0.9, alpha=0.8)
    a2.set_ylabel("epistemic spread", color="tab:red")
    a.set_xlabel("time [ms]")
    a.set_ylabel("$r^*$ / peak")
    a.set_title("(a) LL cell under held-out shift", fontsize=9)
    a.legend(loc="upper left", fontsize=7, frameon=False)

    a = ax[1]
    v, s = res["validation"], res["shift"]
    x = np.arange(2)
    a.bar(x - 0.18, [v["epistemic_mean"], v["epistemic_ll"]], 0.36, color="tab:gray", label="in-distribution")
    a.bar(x + 0.18, [s["epistemic_mean"], s["epistemic_ll"]], 0.36, color="tab:red", label="held-out shift")
    a.set_xticks(x, ["all cells", "LL cells"])
    a.set_ylabel("epistemic spread")
    a.set_title("(b) the model knows when it is unsure", fontsize=9)
    a.legend(fontsize=7, frameon=False)

    a = ax[2]
    cf = res["film_counterfactual"]
    vals = [100 * cf["ll_cell_as_embb_q95_change"], 100 * cf["embb_cell_as_ll_q95_change"]]
    a.bar([0, 1], vals, color=["tab:blue", "tab:orange"])
    a.axhline(0, color="k", lw=0.6)
    a.set_xticks([0, 1], ["LL cell\nlabelled eMBB", "eMBB cell\nlabelled LL"], fontsize=7)
    a.set_ylabel("change of $q_{95}$ [%]")
    a.set_title("(c) counterfactual: swap deadline/priority", fontsize=9)

    a = ax[3]
    lab = ["sum."] + [str(k) for k in range(-len(sal) + 1, 0)]
    a.bar(range(len(sal)), sal, color=["tab:orange"] + ["tab:blue"] * (len(sal) - 1))
    a.set_xticks(range(len(sal)), lab, fontsize=6, rotation=90)
    a.set_xlabel("input token (patch age, oldest left)")
    a.set_title("(d) attribution of LL $q_{95}$", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig_bayes_explain.png"), dpi=200)


if __name__ == "__main__":
    main()
