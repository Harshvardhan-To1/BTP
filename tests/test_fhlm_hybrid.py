"""Tests for the back-pressure newsvendor (BPN) hybrid controller."""
import numpy as np

from fhlm.config import NetworkConfig, ControlConfig, SimConfig, TrafficConfig
from fhlm.simulator import Observation, run_simulation
from fhlm.traffic import generate_traffic
from fhlm.forecast import DEFAULT_QUANTILES, WindowQuantileForecaster
from fhlm.controllers_ext import PredictiveMaxWeight
from fhlm.hybrid import BackpressureNewsvendor


class FixedForecaster:
    quantiles = DEFAULT_QUANTILES
    median_index = 2

    def __init__(self, q):
        self.q = q

    def predict_quantiles(self, obs):
        return self.q


def _obs(queue_scale, rng):
    net, ctrl = NetworkConfig(), ControlConfig(20, 2)
    n = net.num_cells
    return Observation(slot=1000, obs_slot=998, queue_bits=rng.uniform(0, 1, n) * queue_scale,
                       hol_age=rng.integers(0, 4, n).astype(float), se=np.full(n, 4.0),
                       history_fh_demand=np.zeros((n, 998)), history_arrivals=np.zeros((n, 998)),
                       prev_budgets=np.zeros(n), net=net, ctrl=ctrl)


def _quantiles(obs, frac, rng):
    base = np.array(obs.budget_caps) * frac * rng.uniform(0.5, 1.0, obs.num_cells)
    return base[:, None] * np.array([0.5, 0.8, 1.0, 1.2, 1.4, 1.5])[None]


def test_bpn_budgets_are_feasible_in_both_stages():
    rng = np.random.default_rng(0)
    for frac, qs in [(0.05, 0.0), (0.3, 2e5), (0.9, 5e6)]:
        obs = _obs(qs, rng)
        c = BackpressureNewsvendor(FixedForecaster(_quantiles(obs, frac, rng)), p0_ll=0.7, p0_embb=0.4, a=0.5)
        r = c.decide(obs)
        assert np.all(r >= -1e-9) and np.all(r <= obs.budget_caps + 1e-6)
        assert r.sum() <= obs.capacity * (1 + 1e-9)


def test_bpn_reduces_to_predictive_maxweight_when_the_base_fill_saturates_the_link():
    rng = np.random.default_rng(1)
    obs = _obs(5e6, rng)
    q = _quantiles(obs, 0.9, rng)
    pmw = PredictiveMaxWeight(FixedForecaster(q), margin=0.0, lookahead=2.0).decide(obs)
    bpn = BackpressureNewsvendor(FixedForecaster(q), p0_ll=0.5, p0_embb=0.5, v_ll=3.0, lookahead=2.0, a=1.0)
    r = bpn.decide(obs)
    assert bpn.stats["stage2_epochs"] == 0
    assert np.allclose(r, pmw)


def test_bpn_runs_closed_loop():
    cfg = SimConfig(num_slots=3000, warmup_slots=200, seed=3, network=NetworkConfig(),
                    traffic=TrafficConfig(load=0.8), control=ControlConfig(20, 2))
    tr = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
    res = run_simulation(cfg, BackpressureNewsvendor(WindowQuantileForecaster()), trace=tr)
    assert 0.0 <= res.metrics["weighted_violation_ratio"] <= 1.0
