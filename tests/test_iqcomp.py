import os
import numpy as np
import pytest
from iqcomp.uplink import UplinkConfig, make_slot, post_detection_quality
from iqcomp.codecs import bfp, pilot_code, mp_rank, svd_code, dmrs_columns, raw_bits


@pytest.fixture(scope="module")
def slot():
    return make_slot(UplinkConfig(n_prb=4, K=4, snr_db=20, seed=1))


def test_uncompressed_quality_is_reasonable(slot):
    q = post_detection_quality(slot["Y"], slot)
    assert 25 < q["sinr_db"] < 45 and q["evm"] < 0.035


def test_bfp_rate_and_quality(slot):
    Yhat, bits = bfp(slot["Y"], 9)
    assert 1.6 < raw_bits(*slot["Y"].shape[:2]) / bits < 1.8
    q0 = post_detection_quality(slot["Y"], slot)["sinr_db"]
    assert q0 - post_detection_quality(Yhat, slot)["sinr_db"] < 0.5


def test_mp_rank_exceeds_users_but_not_antennas(slot):
    r = mp_rank(slot["Y"], slot["noise_var"])
    assert np.all(r >= 4) and np.all(r < slot["Y"].shape[1])


def test_pilot_sketch_beats_bfp_rate(slot):
    (Yhat, bits), r = pilot_code(slot["Y"], 8, 8, dmrs_columns(), noise_var=slot["noise_var"])
    assert bits < bfp(slot["Y"], 9)[1]
    q0 = post_detection_quality(slot["Y"], slot)["sinr_db"]
    assert q0 - post_detection_quality(Yhat, slot)["sinr_db"] < 3.5


def test_c_pilot_encoder_matches_numpy_rate(slot):
    lib = os.path.join(os.path.dirname(__file__), "..", "kernels", "libiq.so")
    if not os.path.exists(lib):
        pytest.skip("kernels/libiq.so not built (run kernels/build.sh)")
    from iqcomp import fastcodec as fc
    Y = slot["Y"].astype(np.complex64)
    Qq, Lq, r, bits, ref, st = fc.pilot_encode(Y, dmrs_columns(), noise_var=slot["noise_var"])
    assert ref.all() and np.all(r >= 4)
    Yhat = np.einsum("pmr,prn->pmn", Qq, Lq)
    rel = np.linalg.norm(Yhat - Y) / np.linalg.norm(Y)
    assert rel < 0.3
