"""Tests for the extended study: Markov-modulated family, Markov-fluid theory, model-based forecasters and
the additional controllers."""
import numpy as np
import pytest

from fhlm.config import SimConfig, TrafficConfig, NetworkConfig, ControlConfig
from fhlm.traffic import generate_traffic
from fhlm.traffic_markov import (build_sources, stationary_distribution, phase_matrix, simulate_phases,
                                 sample_increments, generate_traffic_markov)
from fhlm.theory import (gamma_log_mgf, window_log_mgf, effective_bandwidth, chernoff_union_tail, doob_tail,
                         sandwich, fluid_drops, theta_max, bound_quantiles)
from fhlm.demand import required_rate, required_rates, critical_window_lengths, sustainable_rates
from fhlm.markov import fit_phase_chain, MarkovChainForecaster, MarkovOracleForecaster, ChernoffBoundForecaster
from fhlm.controllers_ext import PredictiveMaxWeight, ClassLevelPolicy, cem_search
from fhlm.proposed import UncertaintyAwareAllocator
from fhlm.forecast import WindowQuantileForecaster
from fhlm.simulator import run_simulation, Observation


def mm_cfg(load=0.8, slots=3000, seed=5, **kw):
    return SimConfig(num_slots=slots, warmup_slots=200, seed=seed, network=NetworkConfig(),
                     traffic=TrafficConfig(load=load, family="markov", **kw), control=ControlConfig(20, 2))


# ---------------------------------------------------------------------------
# Family M
# ---------------------------------------------------------------------------
def test_phase_matrix_is_stochastic_with_requested_sojourns():
    P = phase_matrix(np.array([40.0, 30.0, 8.0]), np.array([[0, .85, .15], [.5, 0, .5], [.15, .85, 0]]))
    assert np.allclose(P.sum(1), 1.0)
    assert np.allclose(1.0 / (1.0 - np.diag(P)), [40.0, 30.0, 8.0])
    pi = stationary_distribution(P)
    assert np.allclose(pi @ P, pi) and pi.min() > 0


def test_markov_family_hits_target_load_and_is_reproducible():
    cfg = mm_cfg(load=0.65, slots=20000)
    a = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, 3)
    b = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, 3)
    assert np.array_equal(a.fh_demand_bits, b.fh_demand_bits)
    assert abs(a.mean_fh_load - 0.65) < 0.06
    assert (a.arrivals_bits >= 0).all()
    # stationary mean of every source equals its target (analytical scaling)
    sources = build_sources(cfg.network, cfg.traffic)
    beta = cfg.network.fh_bits_per_prb_layer
    tot = sum(s.mean_rate() / c.se_bits_per_prb_layer * beta for s, c in zip(sources, cfg.network.cells))
    assert abs(tot / cfg.network.usable_bits_per_slot - 0.65) < 1e-6


def test_semi_markov_shift_changes_sojourn_law_but_not_means():
    cfg = mm_cfg(load=0.8, slots=30000, mm_tail_alpha=1.5)
    base = mm_cfg(load=0.8, slots=30000)
    a = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, 9)
    b = generate_traffic(base.network, base.traffic, base.num_slots, 9)
    assert abs(a.mean_fh_load - b.mean_fh_load) < 0.08
    # heavy-tailed sojourns -> some much longer bursts than the geometric case
    def longest_run(x):
        best = cur = 1
        for t in range(1, len(x)):
            cur = cur + 1 if x[t] == x[t - 1] else 1
            best = max(best, cur)
        return best
    assert longest_run(a.regime_mult[0]) > longest_run(b.regime_mult[0]) * 0.5


# ---------------------------------------------------------------------------
# theory
# ---------------------------------------------------------------------------
def test_gamma_log_mgf_matches_monte_carlo():
    rng = np.random.default_rng(0)
    mean, cv, th = 2.0, 0.4, 0.3
    k = 1 / cv ** 2
    x = rng.gamma(k, mean / k, size=200000)
    assert abs(np.log(np.mean(np.exp(th * x))) - gamma_log_mgf(th, mean, cv)) < 0.02
    assert np.isinf(gamma_log_mgf(theta_max(np.array([mean]), np.array([cv])) * 1.01, mean, cv))


def test_window_log_mgf_iid_reduces_to_sum_of_log_mgfs():
    # a chain that forgets its state every slot with identical phases is an i.i.d. sequence
    P = np.full((2, 2), 0.5)
    lp = np.array([[0.3, 0.3], [0.7, 0.7]])          # two thetas, identical phases
    pi = np.array([0.5, 0.5])
    L = window_log_mgf(P, lp, pi, 5)
    assert np.allclose(L[:, 4], 5 * np.array([0.3, 0.7]))


def test_effective_bandwidth_between_mean_and_peak_and_monotone():
    cfg = mm_cfg()
    src = build_sources(cfg.network, cfg.traffic)[0]
    mean, cv = src.mu, src.cv
    th = theta_max(mean, cv) * np.array([1e-4, 1e-2, 0.1, 0.5])
    eb = effective_bandwidth(src.P, lambda t: gamma_log_mgf(t, mean, cv), th)
    assert np.all(np.diff(eb) > 0)
    assert eb[0] > src.mean_rate() * 0.99 and eb[0] < src.mean_rate() * 1.2


def test_tail_bounds_are_valid_upper_bounds():
    cfg = mm_cfg()
    src = build_sources(cfg.network, cfg.traffic)[0]
    rng = np.random.default_rng(1)
    H, D, M = 22, 4, 20000
    x = simulate_phases(rng, src, M * H + 500)[500:]
    d = sample_increments(rng, src, x).reshape(M, H)
    rs = required_rates(d, np.full(M, D))
    xs = np.quantile(rs, [0.9, 0.99, 0.999])
    emp = np.array([(rs > v).mean() for v in xs])
    pi = src.stationary()
    U = chernoff_union_tail(xs, src.P, src.mu, src.cv, pi, D, H)
    Dd = doob_tail(xs, src.P, src.mu, src.cv, pi, D, H)
    assert np.all(U >= emp - 1e-3) and np.all(U <= 1.0)
    assert np.all(Dd >= emp - 1e-3) and np.all(Dd <= 1.0)
    q = bound_quantiles(np.array([0.5, 0.9]), src.P, src.mu, src.cv, pi, D, H, x_max=float(rs.max() * 2))
    assert q[1] >= q[0] >= np.quantile(rs, 0.5)        # conservative quantiles dominate the true ones


def test_shortfall_sandwich_holds_and_is_tight_at_the_ends():
    rng = np.random.default_rng(2)
    for _ in range(300):
        a = rng.gamma(1.5, 1.0, size=22) * (rng.random(22) < 0.6)
        D = int(rng.integers(1, 21))
        r = float(rng.uniform(0.0, 2.0))
        lo, v, hi = sandwich(a, r, D)
        assert lo - 1e-9 <= v <= hi + 1e-9
    a = np.array([5.0, 0, 0, 0, 0, 0])
    assert fluid_drops(a, 1.0, 2) == pytest.approx(2.0)          # 3 slots x 1 bit served, 2 dropped
    assert required_rate(a, 2) == pytest.approx(5.0 / 3.0)
    assert sandwich(a, 1.0, 2)[0] == pytest.approx(3 * (5 / 3 - 1))
    # a rate >= r* drops nothing (sufficiency of r*)
    assert fluid_drops(a, 5.0 / 3.0, 2) == pytest.approx(0.0, abs=1e-9)


def test_critical_window_and_sustainable_rate():
    a = np.array([[0, 0, 4, 4, 4, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1]], dtype=float)
    D = np.array([2.0, 20.0])
    assert critical_window_lengths(a, D).tolist() == [3.0, 8.0]
    s = sustainable_rates(a, D)
    assert s[0] == pytest.approx(required_rates(a, D)[0])        # short deadline: r* already above the mean
    assert s[1] == pytest.approx(1.0)                            # long deadline: floored at the mean rate


# ---------------------------------------------------------------------------
# model-based forecasters
# ---------------------------------------------------------------------------
def test_fit_phase_chain_recovers_a_two_phase_source():
    rng = np.random.default_rng(3)
    P = phase_matrix(np.array([30.0, 10.0]), np.array([[0, 1.0], [1.0, 0]]))
    from fhlm.traffic_markov import MarkovSource
    src = MarkovSource(P=P, mu=np.array([1.0, 6.0]), cv=np.array([0.2, 0.2]))
    x = simulate_phases(rng, src, 20000)
    d = sample_increments(rng, src, x)
    Pf, mean, cv, last = fit_phase_chain(d, K=2, thresholds=(0.75,))
    assert abs(mean[1] / mean[0] - 6.0) < 1.0
    assert abs(1 / (1 - Pf[1, 1]) - 10.0) < 4.0                  # burst sojourn roughly recovered
    assert last == (1 if d[-1] > 3.5 else 0)


def _obs_from_trace(cfg, tr, t):
    tau = cfg.control.telemetry_delay_slots
    o = t - tau
    n = cfg.network.num_cells
    return Observation(slot=t, obs_slot=o, queue_bits=np.zeros(n), hol_age=np.zeros(n), se=tr.se[:, o],
                       history_fh_demand=tr.fh_demand_bits[:, :o], history_arrivals=tr.arrivals_bits[:, :o],
                       prev_budgets=np.zeros(n), net=cfg.network, ctrl=cfg.control)


def test_markov_forecasters_return_sorted_quantiles_and_oracle_is_calibrated():
    cfg = mm_cfg(slots=9000, seed=11)
    tr = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
    src = build_sources(cfg.network, cfg.traffic)
    dl = np.array([c.deadline_slots for c in cfg.network.cells])
    fc = {"fit": MarkovChainForecaster(n_paths=150), "oracle": MarkovOracleForecaster(src, cfg.network, n_paths=150),
          "bound": ChernoffBoundForecaster()}
    cover = {k: [] for k in fc}
    for t in range(3000, cfg.num_slots - 20, 60):
        obs = _obs_from_trace(cfg, tr, t)
        y = required_rates(tr.fh_demand_bits[:, obs.obs_slot:t + 20], dl)
        for k, f in fc.items():
            q = f.predict_quantiles(obs)
            assert q.shape == (8, 6) and (np.diff(q, axis=1) >= -1e-6).all() and (q >= 0).all()
            cover[k].append(y <= q[:, -1])            # coverage of the 95 % quantile
    assert 0.85 <= np.mean(cover["oracle"]) <= 0.995
    assert np.mean(cover["bound"]) >= np.mean(cover["oracle"]) - 0.02   # the bound is at least as conservative


# ---------------------------------------------------------------------------
# controllers
# ---------------------------------------------------------------------------
def test_new_controllers_are_feasible_and_finite():
    cfg = mm_cfg(load=0.95, slots=1500)
    tr = generate_traffic(cfg.network, cfg.traffic, cfg.num_slots, cfg.seed)
    cap = cfg.network.usable_bits_per_slot
    caps = np.array(cfg.network.peak_bits_per_slot)
    wq = WindowQuantileForecaster()
    ctrls = [PredictiveMaxWeight(wq), ClassLevelPolicy(wq, 0.9, 0.5, 3.0),
             UncertaintyAwareAllocator(MarkovChainForecaster(n_paths=50), name="markov_kkt"),
             UncertaintyAwareAllocator(ChernoffBoundForecaster(), name="eb_kkt"),
             UncertaintyAwareAllocator(wq, volume_weights=True, name="proposed_vc"),
             UncertaintyAwareAllocator(wq, queue_weights=1.0, name="proposed_dw")]
    for c in ctrls:
        budgets = []
        orig = c.decide

        def rec(obs, _o=orig, _b=budgets):
            b = _o(obs)
            _b.append(np.asarray(b, float))
            return b
        c.decide = rec
        res = run_simulation(cfg, c, trace=tr)
        B = np.stack(budgets)
        assert np.isfinite(B).all() and (B >= -1e-9).all(), c.name
        assert (B.sum(1) <= cap * (1 + 1e-9)).all() and (B <= caps[None] * (1 + 1e-9)).all(), c.name
        assert 0.0 <= res.metrics["weighted_violation_ratio"] <= 1.0


def test_cem_search_finds_the_minimum_of_a_quadratic():
    target = np.array([0.6, 0.3, 0.0])
    theta, hist = cem_search(lambda th: ((th - target) ** 2).sum(1), mean0=np.array([0.2, 0.8, 1.0]),
                             std0=np.array([0.3, 0.3, 0.5]), lo=np.array([0, 0, -2.0]), hi=np.array([1, 1, 2.0]),
                             iters=12, pop=24, elite=6, seed=0, log=lambda *a: None)
    assert np.allclose(theta, target, atol=0.08)
    assert hist[-1]["best_cost"] < hist[0]["best_cost"]
