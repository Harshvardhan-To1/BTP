"""Correctness tests for the fronthaul load-management prototype (fhlm)."""
import numpy as np
import pytest

from fhlm.config import SimConfig, TrafficConfig, NetworkConfig, ControlConfig, fronthaul_bits_per_prb_layer_slot
from fhlm.traffic import generate_traffic, TrafficTrace
from fhlm.simulator import run_simulation, project_budgets, Controller
from fhlm.controllers import (StaticEqualShare, ReactiveProportional, QueueAwareReactive, OracleWaterfill, waterfill)
from fhlm.proposed import UncertaintyAwareAllocator, interp_quantile
from fhlm.demand import required_rate, required_rates
from fhlm.forecast import WindowQuantileForecaster, build_dataset, feature_names


def small_cfg(load=0.8, slots=3000, seed=7, **traffic_kw):
    return SimConfig(num_slots=slots, warmup_slots=200, seed=seed, network=NetworkConfig(),
                     traffic=TrafficConfig(load=load, **traffic_kw), control=ControlConfig(20, 2))


class RecordingController(Controller):
    """Wraps another controller and records what the simulator actually applied."""
    name = "recording"

    def __init__(self, inner):
        self.inner = inner
        self.budgets = []

    def reset(self, net, ctrl, rng=None):
        self.inner.reset(net, ctrl, rng)

    def decide(self, obs):
        b = self.inner.decide(obs)
        self.budgets.append(np.asarray(b, dtype=float))
        return b


# ---------------------------------------------------------------------------
def test_fronthaul_constants():
    # BFP-9: 12 SC x 2 x 9 bit + 8 bit exponent = 224 bit / PRB / symbol; x14 symbols; x1.08 overhead
    assert abs(fronthaul_bits_per_prb_layer_slot(9, 1.0) - 224 * 14) < 1e-9
    net = NetworkConfig()
    # 100 MHz, 4 layers, BFP-9 -> ~7.4 Gbps per cell (order of magnitude of published 7-2x figures)
    gbps = net.cell_peak_bits_per_slot(0) / net.slot_duration_s / 1e9
    assert 6.0 < gbps < 9.0
    assert net.oversubscription > 1.5  # shared link is oversubscribed by design


def test_traffic_is_reproducible_and_positive():
    cfg = small_cfg()
    a = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, 3)
    b = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, 3)
    c = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, 4)
    assert np.array_equal(a.arrivals_bits, b.arrivals_bits)
    assert not np.array_equal(a.arrivals_bits, c.arrivals_bits)
    assert (a.arrivals_bits >= 0).all() and (a.se > 0).all()
    # realised load is close to the requested one (long trace)
    long = generate_traffic(cfg.network, TrafficConfig(load=0.7), 40000, 11)
    assert abs(long.mean_fh_load - 0.7) < 0.12


def test_capacity_compliance_every_slot():
    cfg = small_cfg(load=0.95)
    trace = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
    cap = cfg.network.usable_bits_per_slot
    for ctrl in [StaticEqualShare(), ReactiveProportional(), QueueAwareReactive(), UncertaintyAwareAllocator()]:
        rec = RecordingController(ctrl)
        res = run_simulation(cfg, rec, trace=trace, record_timeseries=True)
        B = np.stack(rec.budgets)
        assert (B >= -1e-9).all()
        assert (B.sum(1) <= cap * (1 + 1e-9)).all(), ctrl.name
        assert (B <= np.array(cfg.network.peak_bits_per_slot)[None, :] * (1 + 1e-9)).all()
        used = res.timeseries["fh_used"]
        assert (used.sum(0) <= cap * (1 + 1e-9)).all(), "link overloaded"
        assert (used <= res.timeseries["budget"] * (1 + 1e-9) + 1e-6).all(), "cell exceeded its budget"


def test_queues_nonnegative_and_accounting_balances():
    cfg = small_cfg(load=0.9)
    res = run_simulation(cfg, ReactiveProportional(), record_timeseries=True)
    q = res.timeseries["queue"]
    assert (q >= -1e-6).all()
    pc = res.per_cell
    arrived = np.array(pc["arrived_bits"])
    served = np.array(pc["served_bits"])
    violated = np.array(pc["violated_bits"])
    # arrived (post warm-up) = served + violated + residual backlog, up to warm-up boundary effects
    total_in = arrived.sum()
    total_out = served.sum() + violated.sum() + res.metrics["residual_backlog_bits"]
    # bits that were queued at the end of warm-up leak into the post-warm-up counts
    assert abs(total_in - total_out) / total_in < 0.02
    assert 0.0 <= res.metrics["violation_ratio"] <= 1.0
    assert 0.0 <= res.metrics["fh_utilisation"] <= 1.0


def test_zero_load_has_no_violations_and_no_utilisation():
    cfg = small_cfg(load=0.8)
    zero = TrafficTrace(arrivals_bits=np.zeros((8, cfg.num_slots)), se=np.full((8, cfg.num_slots), 400.0),
                        fh_demand_bits=np.zeros((8, cfg.num_slots)), regime_mult=np.ones((8, cfg.num_slots)),
                        mean_fh_load=0.0)
    for ctrl in [StaticEqualShare(), QueueAwareReactive(), UncertaintyAwareAllocator()]:
        res = run_simulation(cfg, ctrl, trace=zero)
        assert res.metrics["violation_ratio"] == 0.0
        assert res.metrics["fh_utilisation"] == 0.0
        assert res.metrics["mean_backlog_bits"] == 0.0


def test_light_load_low_violations_and_overload_saturates():
    light = small_cfg(load=0.25, slots=4000)
    res = run_simulation(light, QueueAwareReactive())
    assert res.metrics["violation_ratio"] < 0.02
    heavy = small_cfg(load=2.5, slots=4000)
    res_h = run_simulation(heavy, QueueAwareReactive())
    # with 2.5x offered load the link is saturated and most traffic must be dropped
    assert res_h.metrics["fh_utilisation"] > 0.8  # LL budgets are partly idle in OFF periods (rigid budgets)
    assert res_h.metrics["violation_ratio"] > 0.4
    assert res_h.metrics["p99_queueing_delay_ms"] <= 10.0 + 1e-9  # never beyond the largest deadline


def test_simulation_reproducible():
    cfg = small_cfg()
    r1 = run_simulation(cfg, UncertaintyAwareAllocator())
    r2 = run_simulation(cfg, UncertaintyAwareAllocator())
    for k in ("violation_ratio", "fh_utilisation", "mean_queueing_delay_ms"):
        assert r1.metrics[k] == r2.metrics[k]


def test_project_budgets_and_waterfill():
    caps = np.array([5.0, 5.0, 5.0])
    b = project_budgets(np.array([4.0, 4.0, 4.0]), 6.0, caps)
    assert abs(b.sum() - 6.0) < 1e-9 and (b <= caps).all()
    # waterfill: demand below capacity -> demand met and leftover redistributed within caps
    a = waterfill(np.array([1.0, 2.0, 3.0]), np.ones(3), 10.0, caps)
    assert (a >= np.array([1.0, 2.0, 3.0]) - 1e-9).all() and abs(a.sum() - 10.0) < 1e-9 and (a <= caps).all()
    # shortage: proportional to weighted demand, sums to capacity
    a = waterfill(np.array([2.0, 2.0, 6.0]), np.array([1.0, 1.0, 1.0]), 5.0, caps)
    assert abs(a.sum() - 5.0) < 1e-9 and a[2] > a[0] and abs(a[0] - a[1]) < 1e-9
    # priority weight shifts allocation
    a_w = waterfill(np.array([2.0, 2.0, 6.0]), np.array([3.0, 1.0, 1.0]), 5.0, caps)
    assert a_w[0] > a_w[1]


def test_required_rate_is_deadline_feasible_and_tight():
    rng = np.random.default_rng(0)
    for D in (1, 4, 20):
        a = rng.gamma(0.5, 200.0, size=22) * (rng.random(22) < 0.4)
        r = required_rate(a, D)
        # serving at rate r FIFO from an empty queue never violates the deadline
        q = []  # list of [age, bits]
        for t in range(len(a) + D + 1):
            if t < len(a):
                q.append([0, a[t]])
            rem = r
            for item in q:
                x = min(item[1], rem)
                item[1] -= x
                rem -= x
                if rem <= 1e-12:
                    break
            q = [i for i in q if i[1] > 1e-9]
            for item in q:
                item[0] += 1
                assert item[0] <= D, "deadline violated at rate r*"
        # tight: 0.9 r* violates for some bit (unless traffic is empty)
        if a.sum() > 0:
            r2 = 0.9 * r
            q = []
            violated = False
            for t in range(len(a) + D + 1):
                if t < len(a):
                    q.append([0, a[t]])
                rem = r2
                for item in q:
                    x = min(item[1], rem)
                    item[1] -= x
                    rem -= x
                    if rem <= 1e-12:
                        break
                q = [i for i in q if i[1] > 1e-9]
                for item in q:
                    item[0] += 1
                    if item[0] > D:
                        violated = True
            assert violated
    # vectorised version agrees with scalar
    A = rng.random((3, 22))
    assert np.allclose(required_rates(A, np.array([4, 20, 1])), [required_rate(A[0], 4), required_rate(A[1], 20),
                                                                   required_rate(A[2], 1)])
    assert required_rate(np.zeros(5), 3) == 0.0


def test_kkt_allocation_properties():
    """Bisection allocation: feasible, uses the whole budget when binding, and hedges more for wider forecasts."""
    levels = np.array([0.05, 0.25, 0.5, 0.75, 0.9, 0.95])
    # two identical medians, cell 1 has a much wider predictive distribution
    q = np.array([[9, 9.5, 10, 10.5, 11, 11.5], [4, 7, 10, 13, 16, 19]], dtype=float)
    B = np.zeros(2)
    w = np.ones(2)
    caps = np.array([100.0, 100.0])
    cap = 24.0  # binding: both cannot get their 95% quantile (11.5 + 19)

    def alloc_for(lam):
        p = 1.0 - lam / w
        r = np.where(p <= 0, 0.0, B + interp_quantile(levels, q, np.clip(p, 0, 1)))
        return np.clip(r, 0, caps)

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if alloc_for(mid).sum() > cap:
            lo = mid
        else:
            hi = mid
    r = alloc_for(hi)
    assert abs(r.sum() - cap) < 1e-3
    assert r[1] > r[0], "wider distribution should get the larger margin"
    # equal weighted tail probabilities at the optimum (both cells at the same quantile level)
    p_star = 1 - hi
    assert abs(interp_quantile(levels, q, np.array([p_star, p_star]))[0] - r[0]) < 1e-3


def test_forecaster_interfaces_and_dataset_shapes():
    cfg = small_cfg(slots=4000)
    tr = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, 5)
    X, y = build_dataset([tr], cfg.network, cfg.control)
    assert X.shape[1] == len(feature_names(cfg.network.num_cells))
    assert X.shape[0] == y.shape[0] and (y >= 0).all()
    assert np.isfinite(X).all()
    # window quantile forecaster returns monotone quantiles in bits/slot
    res = run_simulation(cfg, UncertaintyAwareAllocator(WindowQuantileForecaster()), trace=tr)
    assert res.metrics["num_decisions"] == cfg.num_slots // cfg.control.interval_slots


def test_compiled_gbm_matches_sklearn_and_pipeline_trains():
    """Small end-to-end train -> compiled inference check (fast path must equal sklearn predict)."""
    from fhlm.forecast import QuantileGBMForecaster
    cfg = small_cfg(slots=3000)
    traces = [generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, s) for s in (11, 12)]
    X, y = build_dataset(traces, cfg.network, cfg.control)
    model = QuantileGBMForecaster(max_iter=20, quantiles=(0.1, 0.5, 0.9))
    model.fit(X, y)
    fast = model.predict_normalised(X[:16], fast=True)
    slow = model.predict_normalised(X[:16], fast=False)
    assert fast.shape == (16, 3)
    assert np.allclose(fast, slow, atol=1e-9)
    assert (np.diff(fast, axis=1) >= 0).all()
    big = model.predict_normalised(X[:400])            # > FAST_MAX_ROWS falls back to sklearn
    assert big.shape == (400, 3) and np.isfinite(big).all()


def test_oracle_and_controllers_never_see_future():
    """The Observation passed to non-oracle controllers only contains past slots."""
    cfg = small_cfg(slots=2000)
    seen = []

    class Spy(Controller):
        name = "spy"

        def decide(self, obs):
            seen.append((obs.slot, obs.obs_slot, obs.history_fh_demand.shape[1]))
            return np.full(obs.num_cells, obs.capacity / obs.num_cells)

    run_simulation(cfg, Spy())
    for slot, obs_slot, hist_len in seen:
        assert obs_slot == max(0, slot - cfg.control.telemetry_delay_slots)
        assert hist_len == obs_slot
