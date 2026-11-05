import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cmatinv.channel import ChannelConfig, MassiveMIMOChannel
from cmatinv.inverters import *
from cmatinv.precoding import gram, rzf_weights, sum_rate

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "v2")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 130,
                     "lines.linewidth": 1.8, "lines.markersize": 5, "font.family": "serif"})

MP_LO, MP_HI = 0.5, 1.1     # margins chosen from the exp5 coverage study


def snr_to_rho(snr_db):
    return 10 ** (snr_db / 10)


def drops(n, **kw):
    """Yield (cfg, channel, H, alpha, rho) for n independent user drops."""
    snr = kw.pop("snr_db", 10.0)
    seed0 = kw.pop("seed0", 5000)
    for i in range(n):
        cfg = ChannelConfig(seed=seed0 + i, **kw)
        ch = MassiveMIMOChannel(cfg)
        rho = snr_to_rho(snr)
        yield cfg, ch, ch.current(), cfg.K / rho, rho


def rate_with(H, Ginv, rho):
    return sum_rate(H, rzf_weights(H, Ginv, rho))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name + ".png"))
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    plt.close(fig)


def dump(obj, name):
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        json.dump(obj, f, indent=1, default=float)


def interval(G, Gh, alpha):
    dg = np.real(np.diagonal(G, axis1=-2, axis2=-1))
    return moment_interval(Gh, alpha / dg, margin_hi=MP_HI, margin_lo=MP_LO)


def jnn(Gh, ctx, n):
    """Joint Newton-Neumann (Shao et al. 2016): Theta = first Newton iterate from X0 = D^-1 (= I here)."""
    I = eye_like(Gh)
    Th = 2.0 * I - Gh
    T = I - ctx.mm(Th, Gh)
    X = I.copy()
    for _ in range(n - 1):
        X = I + ctx.mm(T, X)
    return ctx.mm(X, Th)
