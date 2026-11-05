"""Standards-based downlink traffic generator (3GPP channel and traffic models).

Second traffic family, independent of the hand-designed generator in
``traffic.py``. Nothing here is fitted to our results; every model and
parameter comes from a 3GPP / ITU-R evaluation document:

  * Radio channel     : 3GPP TR 38.901 UMa (LOS probability, path loss,
                        shadow fading), ISD 500 m, fc = 3.5 GHz, 100 MHz,
                        hexagonal first-tier interference (6 BSs, full load),
                        Rayleigh fast fading with Jakes correlation at 3 km/h.
  * Link-to-system    : 3GPP TR 36.942 Annex A attenuated Shannon bound
                        (alpha = 0.6, SINR_min = -10 dB) quantised to the
                        CQI efficiencies of 3GPP TS 38.214 Table 5.2.2.1-2.
  * eMBB traffic      : FTP Model 3 (3GPP TR 36.814 A.2.1.3.1 / TR 38.913):
                        Poisson file arrivals per UE, file size 0.5 MByte.
  * Low-latency traffic: XR / cloud-gaming video (3GPP TR 38.838 Sec. 5.1):
                        60 fps, 30 Mbit/s, truncated-Gaussian frame size
                        (std 10.5 %, +-50 %) and jitter (std 2 ms, +-4 ms).
  * MAC scheduler     : per-cell round-robin PRB sharing among UEs with data.

The fronthaul demand of a cell in a slot is the number of PRB-layers its
scheduler would transmit if the fronthaul were unconstrained, times the BFP
bits per PRB-layer (config.fronthaul_bits_per_prb_layer_slot). This is the
quantity the shared-link controller has to budget. The offered load is set by
the number of XR UEs per LL cell and the FTP arrival rate per eMBB UE, both
calibrated (analytically, then one empirical correction pass) to the
to the scenario's target mean load: an analytic guess, one short empirical
scheduling pass that fixes the integer XR user count, and Poisson thinning of
the FTP arrivals on the final trace (bisection on the keep-probability, +-1 %).
Nothing else is tuned; the traffic process itself is left as the standards
describe it (stationary users, no hand-designed regimes or bursts).
"""
from __future__ import annotations

import numpy as np
from scipy.special import j0

from .config import NetworkConfig, TrafficConfig, RES_PER_PRB_PER_SLOT
from .traffic import TrafficTrace

# ---------------------------------------------------------------------------
# constants (3GPP TR 38.901 UMa calibration set, TR 38.802 Table A.2.1-1)
# ---------------------------------------------------------------------------
FC_GHZ = 3.5
ISD_M = 500.0
H_BS, H_UT = 25.0, 1.5
TX_POWER_DBM = 49.0            # 100 MHz, UMa
BS_GAIN_DBI, UE_GAIN_DBI = 8.0, 0.0
NOISE_FIGURE_DB = 9.0
BANDWIDTH_HZ = 100e6
UE_SPEED_MPS = 3.0 / 3.6
MIN_DIST_M = 35.0
DATA_RE_FRACTION = 0.8         # share of REs carrying data (rest: DMRS / control)

# TS 38.214 Table 5.2.2.1-2 (64QAM CQI table): efficiency in bits per RE
CQI_EFFICIENCY = np.array([0.1523, 0.2344, 0.3770, 0.6016, 0.8770, 1.1758, 1.4766,
                           1.9141, 2.4063, 2.7305, 3.3223, 3.9023, 4.5234, 5.1152, 5.5547])
SHANNON_ALPHA = 0.6            # TR 36.942 A.1 attenuation factor
SINR_MIN_DB = -10.0

# traffic models
FTP_FILE_BITS = 0.5 * 8 * 2 ** 20                 # 0.5 MByte (TR 36.814)
XR_FPS = 60.0                                    # TR 38.838
XR_RATE_BPS = 30e6
XR_SIZE_STD_REL, XR_SIZE_TRUNC_REL = 0.105, 0.5
XR_JITTER_STD_MS, XR_JITTER_TRUNC_MS = 2.0, 4.0
EMBB_UES_PER_CELL = 20


def _db(x):
    return 10.0 * np.log10(x)


def _lin(xdb):
    return 10.0 ** (xdb / 10.0)


def uma_los_probability(d2d: np.ndarray) -> np.ndarray:
    """TR 38.901 Table 7.4.2-1, UMa, h_UT <= 13 m."""
    d = np.maximum(d2d, 1e-3)
    p = 18.0 / d + np.exp(-d / 63.0) * (1.0 - 18.0 / d)
    return np.where(d <= 18.0, 1.0, p)


def uma_path_loss_db(d2d: np.ndarray, los: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """TR 38.901 Table 7.4.1-1, UMa LOS / NLOS path loss with shadow fading (dB)."""
    d3d = np.sqrt(d2d ** 2 + (H_BS - H_UT) ** 2)
    c = 3e8
    dbp = 4.0 * (H_BS - 1.0) * (H_UT - 1.0) * FC_GHZ * 1e9 / c
    pl1 = 28.0 + 22.0 * np.log10(d3d) + 20.0 * np.log10(FC_GHZ)
    pl2 = (28.0 + 40.0 * np.log10(d3d) + 20.0 * np.log10(FC_GHZ)
           - 9.0 * np.log10(dbp ** 2 + (H_BS - H_UT) ** 2))
    pl_los = np.where(d2d <= dbp, pl1, pl2)
    pl_nlos = np.maximum(pl_los, 13.54 + 39.08 * np.log10(d3d) + 20.0 * np.log10(FC_GHZ) - 0.6 * (H_UT - 1.5))
    sf = rng.normal(0.0, 1.0, size=d2d.shape) * np.where(los, 4.0, 6.0)
    return np.where(los, pl_los, pl_nlos) + sf


def drop_users_sinr(rng: np.random.Generator, n_users: int) -> np.ndarray:
    """Wideband mean SINR (linear) of users dropped uniformly around a UMa site.

    Seven BSs (centre plus first tier at distance ISD) all transmit at full
    power; each user attaches to the strongest received BS (best server) and
    the other six interfere. The dropping area is the centre hexagon, so the
    sample is the SINR distribution of a fully loaded UMa deployment.
    """
    radius = ISD_M / np.sqrt(3.0)
    r = np.sqrt(rng.uniform(MIN_DIST_M ** 2, radius ** 2, n_users))
    phi = rng.uniform(0, 2 * np.pi, n_users)
    x, y = r * np.cos(phi), r * np.sin(phi)
    prx = np.zeros((7, n_users))
    for k in range(7):
        if k == 0:
            bx = by = 0.0
        else:
            bx, by = ISD_M * np.cos((k - 1) * np.pi / 3), ISD_M * np.sin((k - 1) * np.pi / 3)
        dk = np.maximum(np.hypot(x - bx, y - by), MIN_DIST_M)
        los_k = rng.random(n_users) < uma_los_probability(dk)
        prx[k] = _lin(TX_POWER_DBM + BS_GAIN_DBI + UE_GAIN_DBI - uma_path_loss_db(dk, los_k, rng))
    noise = _lin(-174.0 + _db(BANDWIDTH_HZ) + NOISE_FIGURE_DB)
    serving = prx.max(0)
    return serving / (prx.sum(0) - serving + noise)


def spectral_efficiency_bits_per_re(sinr_lin: np.ndarray) -> np.ndarray:
    """TR 36.942 attenuated Shannon, quantised down to the TS 38.214 CQI efficiencies."""
    sinr_db = _db(np.maximum(sinr_lin, 1e-12))
    se = SHANNON_ALPHA * np.log2(1.0 + sinr_lin)
    se = np.where(sinr_db < SINR_MIN_DB, 0.0, np.minimum(se, CQI_EFFICIENCY[-1]))
    idx = np.searchsorted(CQI_EFFICIENCY, se, side="right") - 1
    return np.where(idx >= 0, CQI_EFFICIENCY[np.clip(idx, 0, len(CQI_EFFICIENCY) - 1)], 0.0)


def _truncnorm(rng, mean, std, lo, hi, size):
    x = rng.normal(mean, std, size)
    bad = (x < lo) | (x > hi)
    while bad.any():
        x[bad] = rng.normal(mean, std, bad.sum())
        bad = (x < lo) | (x > hi)
    return x


def xr_frame_arrivals(rng: np.random.Generator, num_slots: int, slot_s: float, n_users: int) -> np.ndarray:
    """[n_users, num_slots] bits arriving per slot from TR 38.838 XR video streams."""
    out = np.zeros((n_users, num_slots))
    period_slots = 1.0 / XR_FPS / slot_s
    mean_bits = XR_RATE_BPS / XR_FPS
    for u in range(n_users):
        n_frames = int(num_slots / period_slots) + 3
        base = (rng.uniform(0, period_slots) + np.arange(n_frames) * period_slots)
        jitter = _truncnorm(rng, 0.0, XR_JITTER_STD_MS, -XR_JITTER_TRUNC_MS, XR_JITTER_TRUNC_MS, n_frames) * 1e-3 / slot_s
        slots = np.floor(base + jitter).astype(int)
        sizes = _truncnorm(rng, mean_bits, XR_SIZE_STD_REL * mean_bits, (1 - XR_SIZE_TRUNC_REL) * mean_bits,
                           (1 + XR_SIZE_TRUNC_REL) * mean_bits, n_frames)
        ok = (slots >= 0) & (slots < num_slots)
        np.add.at(out[u], slots[ok], sizes[ok])
    return out


def _schedule(arrivals: np.ndarray, sinr_mean: np.ndarray, fading_rho: float, prb_layers: np.ndarray,
              rng: np.random.Generator):
    """Per-slot round-robin PRB scheduling of all cells at once.

    arrivals: [N, K, S] user bits; sinr_mean: [N, K] wideband mean SINR (linear,
    0 for unused UE slots). Each slot the instantaneous SINR is sinr_mean times
    a Rayleigh fading gain with Jakes temporal correlation, mapped to an MCS
    efficiency. Returns served user bits [N, S] and PRB-layers [N, S].
    """
    N, K, S = arrivals.shape
    backlog = np.zeros((N, K))
    served_bits = np.zeros((N, S))
    served_prb = np.zeros((N, S))
    active_ue = sinr_mean > 0
    eta_floor = RES_PER_PRB_PER_SLOT * DATA_RE_FRACTION * CQI_EFFICIENCY[0]
    h = (rng.normal(size=(N, K)) + 1j * rng.normal(size=(N, K))) / np.sqrt(2)
    innov = np.sqrt(1 - fading_rho ** 2)
    for t in range(S):
        h = fading_rho * h + innov * (rng.normal(size=(N, K)) + 1j * rng.normal(size=(N, K))) / np.sqrt(2)
        eta = RES_PER_PRB_PER_SLOT * DATA_RE_FRACTION * spectral_efficiency_bits_per_re(sinr_mean * np.abs(h) ** 2)
        eta = np.where(active_ue, np.maximum(eta, eta_floor), 0.0)
        backlog += arrivals[:, :, t]
        demand = np.where(active_ue, np.ceil(backlog / np.maximum(eta, 1.0)), 0.0)
        alloc = np.zeros((N, K))
        remaining = prb_layers.astype(float).copy()
        for _ in range(2):
            need = np.maximum(demand - alloc, 0.0)
            n_act = (need > 0).sum(1)
            share = np.where(n_act > 0, remaining / np.maximum(n_act, 1), 0.0)
            give = np.minimum(need, share[:, None] * (need > 0))
            alloc += give
            remaining = remaining - give.sum(1)
            if (remaining <= 0).all():
                break
        bits = np.minimum(backlog, alloc * eta)
        backlog -= bits
        served_bits[:, t] = bits.sum(1)
        served_prb[:, t] = alloc.sum(1)
    return served_bits, served_prb


def generate_traffic_3gpp(net: NetworkConfig, tcfg: TrafficConfig, num_slots: int, seed: int) -> TrafficTrace:
    rng = np.random.default_rng(seed + 7_000_000)   # separate stream from the synthetic family
    n = net.num_cells
    beta = net.fh_bits_per_prb_layer
    cap = net.usable_bits_per_slot
    slot_s = net.slot_duration_s
    fading_rho = float(j0(2 * np.pi * UE_SPEED_MPS * FC_GHZ * 1e9 / 3e8 * slot_s))

    if tcfg.load_share:
        shares = np.array(tcfg.load_share, dtype=float)
    else:
        shares = np.array([0.6 if c.deadline_slots <= 10 else 1.0 for c in net.cells])
    shares = shares / shares.sum()
    target_fh = tcfg.load * cap * shares                     # mean fronthaul bits/slot per cell
    is_ll = np.array([c.deadline_slots <= 10 for c in net.cells])
    prb_layers = np.array([net.prbs_per_cell * c.layers for c in net.cells])

    # --- users and channels -------------------------------------------------
    K = max(EMBB_UES_PER_CELL, 12)
    sinr_mean = np.zeros((n, K))
    n_users = np.zeros(n, dtype=int)
    for i in range(n):
        sinr_mean[i] = drop_users_sinr(rng, K)
        if is_ll[i]:
            # XR streams need a channel that can carry them (TR 38.838 evaluates XR capacity, i.e. the
            # number of satisfied UEs); keep redrawing UEs until all have at least CQI 7 (~1.5 bit/RE)
            for _ in range(50):
                bad = spectral_efficiency_bits_per_re(sinr_mean[i]) < CQI_EFFICIENCY[6]
                if not bad.any():
                    break
                sinr_mean[i, bad] = drop_users_sinr(rng, int(bad.sum()))
    eta_mean = RES_PER_PRB_PER_SLOT * DATA_RE_FRACTION * spectral_efficiency_bits_per_re(sinr_mean)
    eta_mean = np.maximum(eta_mean, RES_PER_PRB_PER_SLOT * DATA_RE_FRACTION * CQI_EFFICIENCY[0])
    # XR users per LL cell: integer count that best matches the target load analytically
    xr_bits_per_slot = XR_RATE_BPS * slot_s
    for i in np.where(is_ll)[0]:
        eta_bar = float(np.mean(eta_mean[i]))
        per_user_fh = xr_bits_per_slot / eta_bar * beta
        n_users[i] = int(np.clip(np.round(target_fh[i] / per_user_fh), 1, K))
    for i in np.where(~is_ll)[0]:
        n_users[i] = EMBB_UES_PER_CELL
    active = np.arange(K)[None, :] < n_users[:, None]
    eta_mean = np.where(active, eta_mean, 0.0)
    sinr_mean = np.where(active, sinr_mean, 0.0)

    def build_arrivals(lam_cell: np.ndarray, S: int, rng_a: np.random.Generator) -> np.ndarray:
        arr = np.zeros((n, K, S))
        for i in range(n):
            k = n_users[i]
            if is_ll[i]:
                arr[i, :k] = xr_frame_arrivals(rng_a, S, slot_s, k)
            else:
                lam_ue = lam_cell[i] / k                      # files per slot per UE
                arr[i, :k] = rng_a.poisson(lam_ue, size=(k, S)) * FTP_FILE_BITS
        return arr

    # --- calibration ------------------------------------------------------------
    # Round-robin scheduling lets low-SE users consume most PRBs, so the analytic
    # guess based on the mean spectral efficiency is only a starting point. One
    # short empirical pass fixes the integer number of XR UEs per LL cell; the
    # eMBB file rate is then set on the final trace by Poisson thinning (bisection
    # on the keep-probability), so that the realised offered load matches the
    # scenario target to within ~1 %. This normalises the offered load only; the
    # controllers never see this calibration.
    lam = np.zeros(n)
    for i in np.where(~is_ll)[0]:
        eta_bar = float(np.mean(eta_mean[i, :n_users[i]]))
        lam[i] = target_fh[i] * eta_bar / beta / FTP_FILE_BITS
    calib_slots = min(num_slots, 6000)
    embb_idx = np.where(~is_ll)[0]
    rng_c = np.random.default_rng(seed + 7_500_000)
    _, prb_c = _schedule(build_arrivals(lam, calib_slots, rng_c), sinr_mean, fading_rho, prb_layers, rng_c)
    fh_c = prb_c.mean(1) * beta
    for i in np.where(is_ll)[0]:
        per_user = fh_c[i] / n_users[i]
        n_users[i] = int(np.clip(np.round(target_fh[i] / per_user), 1, K))
    active = np.arange(K)[None, :] < n_users[:, None]
    sinr_mean = np.where(active, sinr_mean, 0.0)
    for j, i in enumerate(embb_idx):
        if fh_c[i] > 0:
            lam[i] *= target_fh[i] / fh_c[i]
    lam_max = 0.85 * prb_layers * 70.0 / FTP_FILE_BITS        # stability (effective SE ~70 bit/PRB-layer)
    lam_hi = np.minimum(2.0 * lam, lam_max)                     # generate at a high rate, then thin

    rng_f = np.random.default_rng(seed + 7_250_000)
    arrivals_hi = build_arrivals(lam_hi, num_slots, rng_f)
    keep_u = rng_f.random(arrivals_hi.shape)
    target_total = tcfg.load * cap

    def thinned(p: float) -> np.ndarray:
        arr = arrivals_hi.copy()
        for i in embb_idx:
            arr[i] = np.where(keep_u[i] < p, arr[i], 0.0)
        return arr

    lo, hi = 0.0, 1.0
    best = None
    for _ in range(9):
        p = 0.5 * (lo + hi)
        rng_s = np.random.default_rng(seed + 7_750_000)      # same fading for every bisection step
        bits, prb = _schedule(thinned(p), sinr_mean, fading_rho, prb_layers, rng_s)
        realised = prb.mean(1).sum() * beta
        best = (bits, prb)
        if abs(realised - target_total) / target_total < 0.01:
            break
        if realised < target_total:
            lo = p
        else:
            hi = p
    bits, prb = best

    cell_eta = np.array([eta_mean[i, :n_users[i]].mean() for i in range(n)])
    se = np.where(prb > 0, bits / np.maximum(prb, 1e-9), cell_eta[:, None])
    fh_demand = prb * beta
    regimes = np.ones((n, num_slots))
    return TrafficTrace(arrivals_bits=bits, se=se, fh_demand_bits=fh_demand, regime_mult=regimes,
                        mean_fh_load=float(fh_demand.sum(0).mean() / cap))
