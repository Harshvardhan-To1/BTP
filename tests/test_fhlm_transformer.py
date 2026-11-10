"""Tests for the link-aware cross-cell quantile Transformer (LCQT)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from fhlm.config import SimConfig, TrafficConfig, NetworkConfig, ControlConfig
from fhlm.traffic import generate_traffic
from fhlm.forecast import DEFAULT_QUANTILES, _scale
from fhlm.demand import required_rates
from fhlm.transformer import (build_patches, build_sequence_dataset, cell_conditioning,
                              TransformerQuantileForecaster)
from fhlm.proposed import UncertaintyAwareAllocator
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
