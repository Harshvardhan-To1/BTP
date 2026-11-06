import numpy as np
from cmatinv.channel import ChannelConfig, MassiveMIMOChannel, doppler_rho
from cmatinv.inverters import (Ctx, equilibrate, moment_interval, cheb_ns, residual, probe_residual,
                               chebyshev_inverse)
from cmatinv.precoding import gram
from cmatinv.tracker import WarmStartTracker


def _gram(seed=0, **kw):
    cfg = ChannelConfig(seed=seed, **kw)
    ch = MassiveMIMOChannel(cfg)
    al = cfg.K / 10.0
    return cfg, ch, gram(ch.current(), al), al


def test_channel_power_and_aging():
    cfg, ch, G, al = _gram()
    H0 = ch.current(); H1 = ch.step()
    c = np.vdot(H0, H1).real / np.linalg.norm(H0) / np.linalg.norm(H1)
    assert abs(c - doppler_rho(cfg)) < 0.05


def test_cold_start_converges():
    cfg, ch, G, al = _gram(M=128, K=16)
    Gh, s = equilibrate(G)
    dg = np.real(np.diagonal(G, axis1=-2, axis2=-1))
    a, b = moment_interval(Gh, al / dg, 1.1, 0.5)
    ctx = Ctx()
    X = cheb_ns(Gh, ctx, a, b, 4, 2)
    assert residual(Gh, X).max() < 1e-3 and ctx.gemms == 7


def test_interval_covers_spectrum_iid():
    cfg, ch, G, al = _gram(angular_spread_deg=0)
    Gh, s = equilibrate(G)
    dg = np.real(np.diagonal(G, axis1=-2, axis2=-1))
    a, b = moment_interval(Gh, al / dg, 1.1, 0.5)
    ev = np.linalg.eigvalsh(Gh)
    assert np.all(ev[:, 0] >= a) and np.all(ev[:, -1] <= b)


def test_certificate_tracks_true_residual():
    cfg, ch, G, al = _gram()
    Gh, s = equilibrate(G)
    X = np.linalg.inv(Gh) + 0.05 * np.random.default_rng(0).standard_normal(Gh.shape)
    est = probe_residual(Gh, X, probes=4)
    true = residual(Gh, X)
    assert np.all(est / true > 0.5) and np.all(est / true < 2.0)


def test_tracker_safe_under_fast_fading():
    cfg, ch, G, al = _gram(speed_kmh=120.0)
    trk = WarmStartTracker(al)
    for H in ch.sequence(6):
        Gi, _ = trk.update(gram(H, al))
        assert np.all(np.isfinite(Gi))


def test_doppler_law_matches_iid_simulation():
    from cmatinv.tracker import predicted_warm_residual
    cfg = ChannelConfig(M=64, K=8, angular_spread_deg=0, shadow_db=0, min_dist_m=499, max_dist_m=500,
                        speed_kmh=10.0, seed=3)
    ch = MassiveMIMOChannel(cfg)
    al = cfg.K / 10.0
    Gp = gram(ch.current(), al)
    Gn = gram(ch.step(), al)
    Gh, s = equilibrate(Gn)
    X0 = np.linalg.inv(Gp) / (s[:, :, None] * s[:, None, :])
    r = np.median(residual(Gh, X0))
    pred = predicted_warm_residual(cfg.K, cfg.M, 1 - doppler_rho(cfg))
    assert 0.8 < r / pred < 1.4


def test_fused_c_kernels_match_numpy():
    import pytest
    try:
        from cmatinv.fastkernels import rzf_chol, rzf_ns, chol_inverse
    except OSError:
        pytest.skip("libcmat.so not built (run kernels/build.sh)")
    from cmatinv.precoding import rzf_weights
    rng = np.random.default_rng(0)
    for K, M in ((8, 64), (16, 48), (32, 128)):
        H = ((rng.standard_normal((6, K, M)) + 1j * rng.standard_normal((6, K, M))) / np.sqrt(2)).astype(np.complex64)
        al = K / 10.0
        G = H @ np.conj(np.swapaxes(H, -1, -2)) + al * np.eye(K)
        Wr = rzf_weights(H.astype(complex), np.linalg.inv(G), 10.0)
        assert np.linalg.norm(rzf_chol(H, al, 10.0).transpose(0, 2, 1) - Wr) / np.linalg.norm(Wr) < 1e-5
        Xp = np.linalg.inv(G).astype(np.complex64) * np.complex64(1.02)
        X = Xp.copy()
        _, r = rzf_ns(H, X, al, 10.0)
        assert np.allclose(r, np.linalg.norm(np.eye(K) - G @ Xp, axis=(1, 2)) / np.sqrt(K), rtol=1e-3)
