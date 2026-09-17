import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from src.channel.tdl_a import ChannelConfig, TDLAChannel, estimate_rank, estimate_rank_fast
from src.encoder.bfp import bfp_bits_used, bfp_decode, bfp_encode, bfp_quantization_noise_energy
from src.encoder.csee import CSEEEncoder
from src.encoder.ras_bfp import RASBFPEncoder, fwht
from src.encoder.svd_encoder import SVDEncoder
from src.metrics.nmse import compression_ratio, nmse, nmse_linear, original_bits


@pytest.fixture(scope="module")
def channel():
    cfg = ChannelConfig(M=16, N=240, SNR_dB=20.0, seed=1)
    ch = TDLAChannel(cfg)
    H = ch.generate_H()
    Y_ref, S_ref = ch.generate_received_signal(H, return_clean=True, symbol_type="reference")
    Y_dat = ch.generate_received_signal(H, symbol_type="data")
    return cfg, H, Y_ref, S_ref, Y_dat


# -- channel ---------------------------------------------------------------------
def test_channel_power_and_rank(channel):
    cfg, H, Y_ref, S_ref, Y_dat = channel
    assert H.shape == (cfg.M, cfg.N)
    assert 0.5 < np.mean(np.abs(H) ** 2) < 2.0            # E|H|^2 ~ 1 up to fading
    assert np.linalg.matrix_rank(H) <= 23                 # sum of 23 rank-one taps
    assert np.allclose(S_ref, H)                          # reference mode transports H + W'
    # spatial rank is invariant to per-subcarrier modulation
    assert estimate_rank(Y_ref) == estimate_rank(Y_dat)


def test_channel_seed_reproducible():
    cfg = ChannelConfig(M=8, N=48, SNR_dB=10.0, seed=7)
    a = TDLAChannel(cfg).generate_batch(2)[1]
    b = TDLAChannel(cfg).generate_batch(2)[1]
    assert np.array_equal(a, b)


def test_channel_invalid_config():
    with pytest.raises(ValueError):
        ChannelConfig(M=0)
    with pytest.raises(ValueError):
        ChannelConfig(rho=1.0)
    with pytest.raises(ValueError):
        TDLAChannel(ChannelConfig()).generate_received_signal(np.zeros((64, 1200)), symbol_type="bogus")


def test_rank_estimators_edge_cases():
    assert estimate_rank(np.zeros((4, 10))) == 0
    assert estimate_rank_fast(np.zeros((4, 10))) == 0
    rank1 = np.outer(np.ones(4), np.arange(1, 11)).astype(complex)
    assert estimate_rank(rank1, 0.99) == 1
    full = np.eye(4, 10)
    assert estimate_rank(full, 1.0) == 4
    with pytest.raises(ValueError):
        estimate_rank(full, 0.0)


# -- BFP -------------------------------------------------------------------------
@pytest.mark.parametrize("bits", [4, 8, 12, 16])
def test_bfp_roundtrip_error_bound(bits):
    rng = np.random.default_rng(0)
    Y = rng.standard_normal((5, 36)) + 1j * rng.standard_normal((5, 36))
    enc = bfp_encode(Y, bits=bits, block_size=12)
    Yh = bfp_decode(enc)
    assert Yh.shape == Y.shape
    # each real component is within half a quantisation step of the input
    step = np.exp2(enc["exp"].astype(float)).repeat(12, axis=-1)
    assert np.all(np.abs(Yh.real - Y.real) <= step / 2 + 1e-12)
    assert np.all(np.abs(Yh.imag - Y.imag) <= step / 2 + 1e-12)
    # bit accounting: 2*bits per sample + 4 per block
    assert bfp_bits_used(enc) == 2 * bits * Y.size + 4 * 5 * 3
    # predicted worst-case energy is an upper bound, estimate is within a factor of the truth
    err = np.linalg.norm(Y - Yh) ** 2
    assert err <= bfp_quantization_noise_energy(Y, bits, 12, worst_case=True) + 1e-12
    est = bfp_quantization_noise_energy(Y, bits, 12)
    assert 0.2 * est <= err <= 5 * est


def test_bfp_zero_block_and_padding():
    Y = np.zeros((2, 14), dtype=complex)
    Y[0, :3] = 1.0 + 1j
    enc = bfp_encode(Y, bits=6, block_size=12)          # 14 -> padded to 24
    assert enc["pad"] == 10
    Yh = bfp_decode(enc)
    assert Yh.shape == Y.shape
    assert np.allclose(Yh[1], 0) and np.allclose(Yh[0, 3:], 0)
    assert np.allclose(Yh[0, :3], Y[0, :3], atol=0.1)
    assert bfp_quantization_noise_energy(np.zeros((2, 12)), 8) == 0.0


def test_bfp_more_bits_is_monotone():
    rng = np.random.default_rng(3)
    Y = rng.standard_normal((4, 24)) + 1j * rng.standard_normal((4, 24))
    errs = [nmse(Y, bfp_decode(bfp_encode(Y, bits=b))) for b in (4, 8, 12)]
    assert errs[0] > errs[1] > errs[2]
    with pytest.raises(ValueError):
        bfp_encode(Y, bits=1)


# -- SVD / RAS-BFP ---------------------------------------------------------------
def test_svd_full_rank_is_near_lossless(channel):
    cfg, H, Y, *_ = channel
    enc = SVDEncoder(r=cfg.M, bits=14).encode(Y)
    assert nmse(Y, SVDEncoder(r=cfg.M, bits=14).decode(enc)) < -60


def test_svd_matches_eckart_young_floor(channel):
    cfg, H, Y, *_ = channel
    e = SVDEncoder(r=4, bits=16)
    enc = e.encode(Y)
    err = np.linalg.norm(Y - e.decode(enc)) ** 2
    floor = SVDEncoder.truncation_error(Y, 4)
    assert floor <= err <= floor * 1.01 + 1e-9         # only quantisation above the floor
    assert e.compression_ratio(enc) == compression_ratio(original_bits(cfg.M, cfg.N), e.bits_used(enc))


def test_fwht_matches_hadamard():
    x = np.random.default_rng(0).standard_normal((8, 3))
    Hm = np.array([[1, 1], [1, -1]])
    H8 = np.kron(np.kron(Hm, Hm), Hm)
    assert np.allclose(fwht(x), H8 @ x)
    with pytest.raises(ValueError):
        fwht(np.zeros((6, 2)))


@pytest.mark.parametrize("sketch", ["srht", "gaussian"])
def test_ras_bfp_same_payload_as_svd_and_bound(channel, sketch):
    cfg, H, Y, *_ = channel
    r = 6
    ras = RASBFPEncoder(r=r, bits=10, oversample=4, sketch=sketch)
    svd = SVDEncoder(r=r, bits=10)
    e_ras, e_svd = ras.encode(Y), svd.encode(Y)
    assert ras.bits_used(e_ras) == svd.bits_used(e_svd)          # fair CR comparison
    err = np.linalg.norm(Y - ras.decode(e_ras)) ** 2
    floor = SVDEncoder.truncation_error(Y, r)
    assert err >= floor * 0.99                                     # cannot beat Eckart-Young
    assert err <= RASBFPEncoder.theoretical_error_bound(Y, r, 4) + 0.05 * np.linalg.norm(Y) ** 2
    assert RASBFPEncoder.theoretical_error_bound(Y, r, 1) == float("inf")


def test_ras_bfp_non_power_of_two_M():
    rng = np.random.default_rng(5)
    Y = rng.standard_normal((12, 60)) + 1j * rng.standard_normal((12, 60))
    e = RASBFPEncoder(r=12, bits=14, oversample=0)
    assert nmse(Y, e.decode(e.encode(Y))) < -50                    # full rank -> lossless up to BFP


# -- CSEE --------------------------------------------------------------------------
def test_csee_full_support_is_bfp_only(channel):
    cfg, H, Y, *_ = channel
    e = CSEEEncoder(K=cfg.N, bits=14)
    enc = e.encode(Y)
    assert nmse(Y, e.decode(enc)) < -60
    assert e.bits_used(enc) == CSEEEncoder.predicted_bits(cfg.M, cfg.N, cfg.N, 14)


def test_csee_prediction_matches_measurement(channel):
    cfg, H, Y, *_ = channel
    for K in (8, 24, 60):
        e = CSEEEncoder(K=K, bits=10)
        enc = e.encode(Y)
        measured = nmse_linear(Y, e.decode(enc))
        est = CSEEEncoder.theoretical_nmse_bound(Y, K, 10)
        worst = CSEEEncoder.theoretical_nmse_bound(Y, K, 10, worst_case=True)
        assert measured <= worst * 1.0001                        # true upper bound
        assert abs(10 * np.log10(measured) - 10 * np.log10(est)) < 0.5   # estimate within 0.5 dB
        assert e.bits_used(enc) == CSEEEncoder.predicted_bits(cfg.M, cfg.N, K, 10)


def test_csee_menu_prediction_equals_pointwise(channel):
    cfg, H, Y, *_ = channel
    Yd = CSEEEncoder.delay_domain(Y)
    Ks, bl = [8, 24, 60, 240], [4, 8, 12]
    menu = CSEEEncoder.predict_menu(Yd, Ks, bl)
    for i, K in enumerate(Ks):
        for j, b in enumerate(bl):
            assert np.isclose(menu[i, j], CSEEEncoder.theoretical_nmse_bound(Y, K, b), rtol=1e-6)


def test_csee_noise_aware_prediction_tracks_clean_nmse():
    for snr in (0.0, 20.0):
        ch = TDLAChannel(ChannelConfig(M=16, N=240, SNR_dB=snr, seed=9))
        Y, S = ch.generate_received_signal(ch.generate_H(), return_clean=True, symbol_type="reference")
        Yd = CSEEEncoder.delay_domain(Y)
        Ks, bl = [8, 24, 240], [6, 12]
        pred = CSEEEncoder.predict_menu(Yd, Ks, bl, noise_var=10 ** (-snr / 10))
        for i, K in enumerate(Ks):
            for j, b in enumerate(bl):
                e = CSEEEncoder(K, b)
                meas = nmse_linear(S, e.decode(e.encode(Y)))
                assert abs(10 * np.log10(pred[i, j]) - 10 * np.log10(meas)) < 2.5
        # at low SNR keeping everything (K = N) must look worse for the signal than keeping few taps
        if snr == 0.0:
            assert pred[-1, -1] > pred[0, -1]


def test_csee_needs_delay_sparsity(channel):
    cfg, H, Y_ref, S_ref, Y_dat = channel
    e = CSEEEncoder(K=24, bits=10)
    assert nmse(Y_ref, e.decode(e.encode(Y_ref))) < -12          # works on reference symbols
    assert nmse(Y_dat, e.decode(e.encode(Y_dat))) > -3           # fails on modulated data symbols


def test_csee_zero_input():
    Y = np.zeros((4, 48), dtype=complex)
    e = CSEEEncoder(K=8, bits=8)
    assert np.allclose(e.decode(e.encode(Y)), 0)
    assert CSEEEncoder.theoretical_nmse_bound(Y, 8) == 0.0
    with pytest.raises(ValueError):
        CSEEEncoder(K=0)


def test_metrics_edge_cases():
    Z = np.zeros((2, 2))
    assert nmse_linear(Z, Z) == 0.0
    assert nmse_linear(Z, np.ones((2, 2))) == float("inf")
    with pytest.raises(ValueError):
        compression_ratio(10, 0)
