import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from src.channel.tdl_a import ChannelConfig, TDLAChannel
from src.control.allocator import (
    bits_per_symbol_to_gbps,
    build_bfp_menu,
    build_csee_menu,
    greedy_allocate,
    uniform_allocate,
)
from src.encoder.csee import CSEEEncoder
from src.metrics.nmse import nmse_linear
from src.split.acafs import ACAFSController, FunctionalSplit, SplitBandwidthModel


# -- ACAFS -----------------------------------------------------------------------
def test_split_bandwidth_ordering():
    bw = SplitBandwidthModel(M=64, N=1200, bits_iq=16)
    for r in (1, 8, 32, 63):
        assert bw.split6_bits(r) < bw.beam_space_bits(r) < bw.antenna_space_bits()
    assert bw.beam_space_bits(64) > bw.antenna_space_bits()      # beam-space at full rank is worse (weights)


def test_acafs_rule_and_edges():
    c = ACAFSController(0.15, 0.55, M=64)
    assert c.select_split(0) == (FunctionalSplit.SPLIT_72x, 10)   # zero energy -> stream floor
    assert c.select_split(4) == (FunctionalSplit.SPLIT_72x, 10)   # floor = ceil(0.15*64)
    assert c.select_split(20) == (FunctionalSplit.SPLIT_72x, 20)
    assert c.select_split(40)[0] is FunctionalSplit.SPLIT_6
    assert c.select_split(64)[0] is FunctionalSplit.SPLIT_6
    assert c.select_split(200)[0] is FunctionalSplit.SPLIT_6      # clipped to M
    no6 = ACAFSController(0.15, 0.55, M=64, allow_split6=False)
    assert no6.select_split(40) == (FunctionalSplit.SPLIT_71, 64)
    assert no6.bw_reduction_for_rank(40) == 0.0
    assert 0.0 < c.bw_reduction_for_rank(20) < 1.0
    assert c.expected_bw_reduction([]) == 0.0
    dist = c.split_distribution([4, 20, 40, 64])
    assert dist == {"7.2x": 0.5, "7.1": 0.0, "6": 0.5}
    with pytest.raises(ValueError):
        ACAFSController(0.6, 0.5)
    with pytest.raises(ValueError):
        ACAFSController(M=0)


def test_prop5_is_the_uniform_average():
    c = ACAFSController(0.15, 0.55, M=16)
    manual = np.mean([c.bw_reduction_for_rank(r) for r in range(1, 17)])
    assert np.isclose(ACAFSController.theorem5_bound(16, 0.15, 0.55), manual)


# -- allocator ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def cells():
    Ys = []
    for k, snr in enumerate([0, 10, 20, 30]):
        ch = TDLAChannel(ChannelConfig(M=16, N=240, SNR_dB=snr, seed=50 + k))
        Ys.append(ch.generate_received_signal(ch.generate_H(), symbol_type="reference"))
    return np.stack(Ys)


def test_menu_rates_match_encoder(cells):
    menu = build_csee_menu(cells, [8, 24, 60], [4, 8, 12])
    assert menu.rates.shape == (9,) and menu.predicted.shape == (4, 9)
    for j, p in enumerate(menu.params):
        e = CSEEEncoder(p["K"], p["bits"])
        assert e.bits_used(e.encode(cells[0])) == menu.rates[j]
        meas = nmse_linear(cells[0], e.decode(e.encode(cells[0])))
        assert abs(10 * np.log10(meas) - 10 * np.log10(menu.predicted[0, j])) < 0.6


def test_greedy_respects_capacity_and_beats_uniform(cells):
    menu = build_csee_menu(cells, [8, 24, 60, 120, 240], [4, 6, 8, 10, 12])
    raw = 2 * 16 * 240 * 16 * 4
    for frac in (0.5, 0.2, 0.1, 0.05):
        C = raw * frac
        g = greedy_allocate(menu.rates, menu.predicted, C)
        u = uniform_allocate(menu.rates, menu.predicted, C)
        assert g.feasible and u.feasible
        assert g.total_rate <= C and u.total_rate <= C
        assert not g.dropped.any() and not u.dropped.any()
        assert g.predicted.sum() <= u.predicted.sum() + 1e-12   # greedy never worse on its objective
        assert g.utilization >= u.utilization - 1e-9
    gm = greedy_allocate(menu.rates, menu.predicted, raw * 0.1, objective="max")
    assert gm.predicted.max() <= greedy_allocate(menu.rates, menu.predicted, raw * 0.1).predicted.max() + 1e-12


def test_allocator_low_load_uses_best_option(cells):
    menu = build_csee_menu(cells, [8, 240], [4, 12])
    g = greedy_allocate(menu.rates, menu.predicted, capacity=1e12)
    assert all(menu.params[i] == {"K": 240, "bits": 12} for i in g.choice)
    assert g.utilization < 1e-3


def test_allocator_overload_drops_cells(cells):
    menu = build_csee_menu(cells, [8, 24], [4, 6])
    C = menu.rates.min() * 2.5                    # room for two cells at the cheapest point
    g = greedy_allocate(menu.rates, menu.predicted, C)
    u = uniform_allocate(menu.rates, menu.predicted, C)
    assert g.dropped.sum() == 2 and u.dropped.sum() == 2
    assert g.feasible and u.feasible
    assert np.all(g.predicted[g.dropped] == 1.0)
    assert np.all(g.choice[g.dropped] == -1)
    z = greedy_allocate(menu.rates, menu.predicted, capacity=0.0)
    assert z.dropped.all() and z.total_rate == 0.0


def test_allocator_zero_traffic_cell(cells):
    Y = cells.copy(); Y[1] = 0.0
    menu = build_csee_menu(Y, [8, 24], [4, 8])
    assert np.all(menu.predicted[1] == 0.0)
    g = greedy_allocate(menu.rates, menu.predicted, menu.rates.max() * 4)
    assert g.feasible
    # zero cell gains nothing from upgrades, so it stays at the cheapest point
    assert menu.rates[g.choice[1]] == menu.rates.min()


def test_allocator_invalid_inputs(cells):
    menu = build_csee_menu(cells, [8], [4])
    with pytest.raises(ValueError):
        greedy_allocate(menu.rates, menu.predicted, -1.0)
    with pytest.raises(ValueError):
        greedy_allocate(menu.rates, menu.predicted[:, :0], 1.0)
    with pytest.raises(ValueError):
        greedy_allocate(menu.rates, menu.predicted, 1.0, objective="median")
    with pytest.raises(ValueError):
        greedy_allocate(np.array([0.0]), menu.predicted, 1.0)


def test_bfp_menu_and_units(cells):
    m = build_bfp_menu(cells, [4, 8, 16])
    assert np.all(np.diff(m.rates) > 0)
    assert np.all(np.diff(m.predicted, axis=1) < 0)               # more bits -> less distortion
    assert np.isclose(bits_per_symbol_to_gbps(2 * 64 * 1200 * 16), 34.4064)
