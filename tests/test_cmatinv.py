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
