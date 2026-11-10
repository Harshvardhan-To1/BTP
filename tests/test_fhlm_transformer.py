"""Tests for the link-aware cross-cell quantile Transformer (LCQT)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from fhlm.config import SimConfig, TrafficConfig, NetworkConfig, ControlConfig
from fhlm.traffic import generate_traffic
from fhlm.forecast import DEFAULT_QUANTILES, _scale
from fhlm.demand import required_rates
from fhlm.transformer import (build_patches, build_sequence_dataset, cell_conditioning,
                              TransformerQuantileForecaster, BayesianTransformerForecaster, mixture_quantiles)
from fhlm.decision_focused import kkt_layer
from fhlm.proposed import UncertaintyAwareAllocator, interp_quantile
from fhlm.simulator import run_simulation


def _setup(slots=3000, seed=1):
    cfg = SimConfig(num_slots=slots, warmup_slots=200, seed=seed, network=NetworkConfig(),
                    traffic=TrafficConfig(load=0.8), control=ControlConfig(20, 2))
    tr = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, seed)
    return cfg, tr


def test_patches_hold_the_most_recent_horizons_and_their_rstar():
    cfg, tr = _setup()
    net, H = cfg.network, 22
    scale = _scale(net)
    dl = np.array([c.deadline_slots for c in net.cells])
    hist = tr.fh_demand_bits[:, :1000]
    p = build_patches(hist, dl, scale, H, P=4)
    assert p.shape == (net.num_cells, 4, H + 3)
    assert np.allclose(p[:, -1, :H], hist[:, -H:] / scale[:, None])
    assert np.allclose(p[:, -1, H], required_rates(hist[:, -H:], dl) / scale)
    short = build_patches(hist[:, :30], dl, scale, H, P=4)
    assert np.all(short[:, :3] == 0) and np.any(short[:, 3] != 0)


def test_quantiles_do_not_cross_and_drive_the_kkt_rule(tmp_path):
    cfg, tr = _setup()
    Xp, Xf, Y = build_sequence_dataset([tr], cfg.network, cfg.control, P=4)
    assert Xp.shape[:2] == Y.shape and Xf.shape[:2] == Y.shape
    f = TransformerQuantileForecaster(DEFAULT_QUANTILES, d_model=16, heads=2, layers=1, patches=4)
    cond = cell_conditioning(cfg.network, cfg.control)
    prio = np.array([c.priority for c in cfg.network.cells], dtype=float)
    f.fit((Xp, Xf, Y), (Xp[:20], Xf[:20], Y[:20]), cond, prio, epochs=2, threads=1)
    q = f._predict_batch(Xp[:50], Xf[:50])
    assert np.all(np.diff(q, axis=-1) >= 0)

    path = tmp_path / "lcqt.pt"
    f.save(str(path))
    g = TransformerQuantileForecaster.load(str(path))
    assert np.allclose(g._predict_batch(Xp[:5], Xf[:5]), q[:5], atol=1e-6)

    res = run_simulation(cfg, UncertaintyAwareAllocator(g, calibrate=False), trace=tr)
    assert 0.0 <= res.metrics["violation_ratio"] <= 1.0

    bayes = BayesianTransformerForecaster([g], mc_samples=4)
    mq = bayes.predict_batch(Xp[:10], Xf[:10])
    assert mq.shape == q[:10].shape and np.all(np.diff(mq, axis=-1) >= -1e-9)


def test_mixture_quantiles_widen_with_posterior_disagreement():
    lv = np.array(DEFAULT_QUANTILES)
    base = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5])[None, None]
    same = mixture_quantiles(np.repeat(base, 4, axis=0), lv)
    spread = mixture_quantiles(np.concatenate([base - 0.0, base + 2.0]), lv)
    assert np.allclose(same[0], base[0, 0], atol=0.05)
    assert spread[0, -1] - spread[0, 0] > same[0, -1] - same[0, 0]


def _numpy_kkt(q, B, w, cap, caps, lv):
    def alloc(lam):
        p = 1 - lam / w
        r = np.where(p <= 0, 0, B + interp_quantile(lv, q, np.clip(p, 0, 1)))
        return np.clip(r, 0, caps)
    if alloc(0.0).sum() <= cap:
        return alloc(0.0)
    lo, hi = 0.0, w.max()
    for _ in range(60):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if alloc(m).sum() > cap else (lo, m)
    return alloc(hi)


def test_differentiable_kkt_layer_matches_the_allocator_and_has_implicit_gradients():
    rng = np.random.default_rng(0)
    lv = np.array(DEFAULT_QUANTILES)
    N, cap, caps = 8, 10.0, np.full(8, 4.0)
    q = np.sort(rng.gamma(2, 0.5, (N, 6)), 1)
    B = rng.uniform(0, 0.3, N)
    w = rng.choice([3.0, 1.0], N) * rng.uniform(0.25, 1, N)
    qt = torch.tensor(q[None], dtype=torch.float32, requires_grad=True)
    r = kkt_layer(qt, torch.tensor(B[None], dtype=torch.float32), torch.tensor(w[None], dtype=torch.float32),
                  cap, torch.tensor(caps, dtype=torch.float32), lv)
    assert np.allclose(r.detach().numpy()[0], _numpy_kkt(q, B, w, cap, caps, lv), atol=1e-4)
    # binding link: raising one cell's quantiles moves budget from the others, the total stays C
    g_total = torch.autograd.grad(r.sum(), qt, retain_graph=True)[0]
    assert float(g_total.abs().max()) < 1e-4
    g0 = torch.autograd.grad(r[0, 0], qt)[0]
    assert float(g0.abs().sum()) > 0
