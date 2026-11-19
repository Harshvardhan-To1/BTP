"""Trace-driven family "real5g": per-user downlink throughput and CQI from a public 5G operator dataset.

Source: D. Raca, D. Leahy, C. J. Sreenan, J. J. Quinlan, "Beyond Throughput, The Next Generation: A 5G
Dataset with Channel and Context Metrics", ACM MMSys 2020 (github.com/uccmisl/5Gdataset, GPL-3.0).
166 client-side sessions (Netflix / Amazon Prime streaming and file download, static and driving) on a
commercial Irish network, logged about once per second.

Construction of one trace
-------------------------
* Sessions are split once into a TRAIN pool (seeds < 3000: training, validation, policy search) and a
  disjoint TEST pool (seeds >= 3000), every third session in path order going to TEST.
* Each cell aggregates USERS_PER_CELL sessions drawn from its pool at random start offsets.
* User u contributes its measured rate r_u(t) and costs r_u(t) / se_u(t) PRB-layers, with se_u from its
  measured CQI through the LTE 4-bit CQI efficiency table (TS 36.213 Table 7.2.3-1) times 134.4 data REs
  per PRB-layer. The cell's fronthaul demand is beta * sum_u r_u / se_u.
* Each one-second sample is replayed as HOLD_SLOTS slots (one 10 ms control interval): the real
  sequence of rates is kept, the time axis is compressed 100x. No synthetic randomness is added.
* Cells are scaled to the scenario load with the same LL / eMBB load shares as the other families, and a
  cell's demand is clipped at its own air-interface peak (the radio cannot schedule more); the scale is
  chosen so that the mean after clipping meets the target load.
"""
from __future__ import annotations

import glob
import io
import os
import urllib.request
import zipfile

import numpy as np

from .config import NetworkConfig, TrafficConfig

URL = "https://raw.githubusercontent.com/uccmisl/5Gdataset/master/5G-production-dataset.zip"
DATA = os.path.join(os.path.dirname(__file__), "..", "data", "real5g", "sessions.npz")
USERS_PER_CELL = 6
HOLD_SLOTS = 20
CQI_EFF = np.array([0.0, 0.1523, 0.2344, 0.3770, 0.6016, 0.8770, 1.1758, 1.4766, 1.9141, 2.4063, 2.7305,
                    3.3223, 3.9023, 4.5234, 5.1152, 5.5547])
DATA_RES = 168 * 0.8


def prepare(path: str = DATA) -> None:
    """Download the dataset and store per-session 1 s series of DL rate (kbit/s) and CQI."""
    import pandas as pd
    raw = urllib.request.urlopen(URL, timeout=120).read()
    rates, cqis, names = [], [], []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for f in sorted(n for n in z.namelist() if n.endswith(".csv") and "__MACOSX" not in n):
            d = pd.read_csv(z.open(f))
            d["t"] = pd.to_datetime(d.Timestamp, format="%Y.%m.%d_%H.%M.%S")
            d["dl"] = pd.to_numeric(d.DL_bitrate, errors="coerce")
            d["cqi"] = pd.to_numeric(d.CQI, errors="coerce")
            g = d.groupby("t")[["dl", "cqi"]].mean().resample("1s").mean()
            g["dl"] = g.dl.fillna(0.0).clip(lower=0.0)
            g["cqi"] = g.cqi.ffill().bfill().fillna(9).clip(1, 15)
            rates.append(g.dl.values.astype(np.float32))
            cqis.append(g.cqi.values.astype(np.float32))
            names.append(f.split("5G-production-dataset/")[-1])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    off = np.cumsum([0] + [len(r) for r in rates])
    np.savez_compressed(path, rate=np.concatenate(rates), cqi=np.concatenate(cqis), offsets=off,
                        names=np.array(names))


_CACHE = {}


def sessions(pool: str):
    if pool not in _CACHE:
        if not os.path.exists(DATA):
            prepare()
        z = np.load(DATA)
        off, rate, cqi = z["offsets"], z["rate"], z["cqi"]
        all_s = [(rate[off[i]:off[i + 1]], cqi[off[i]:off[i + 1]]) for i in range(len(off) - 1)]
        _CACHE["test"] = [s for i, s in enumerate(all_s) if i % 3 == 0]
        _CACHE["train"] = [s for i, s in enumerate(all_s) if i % 3 != 0]
    return _CACHE[pool]


def generate_traffic_real5g(net: NetworkConfig, tcfg: TrafficConfig, num_slots: int, seed: int):
    from .traffic import TrafficTrace
    pool = sessions("test" if seed >= 3000 else "train")
    rng = np.random.default_rng(seed + 7_000_000)
    n = net.num_cells
    beta, cap = net.fh_bits_per_prb_layer, net.usable_bits_per_slot
    T = int(np.ceil(num_slots / HOLD_SLOTS)) + 1
    pick = rng.choice(len(pool), size=n * USERS_PER_CELL, replace=len(pool) < n * USERS_PER_CELL)
    user_bits = np.zeros((n, T))
    prb_layers = np.zeros((n, T))
    for i in range(n):
        for k in pick[i * USERS_PER_CELL:(i + 1) * USERS_PER_CELL]:
            r, c = pool[k]
            idx = (rng.integers(len(r)) + np.arange(T)) % len(r)
            se = CQI_EFF[np.rint(c[idx]).astype(int)] * DATA_RES
            user_bits[i] += r[idx]
            prb_layers[i] += r[idx] / se
    shares = np.array(tcfg.load_share, dtype=float) if tcfg.load_share else \
        np.array([0.6 if c.deadline_slots <= 10 else 1.0 for c in net.cells])
    target = tcfg.load * cap * shares / shares.sum()
    fh0 = prb_layers * beta
    peak = np.array(net.peak_bits_per_slot)[:, None]
    scale = target / np.maximum(fh0.mean(1), 1e-12)
    for _ in range(20):                      # rescale so that the mean AFTER peak clipping meets the target
        scale *= target / np.maximum(np.minimum(fh0 * scale[:, None], peak).mean(1), 1e-12)
    fh = fh0 * scale[:, None]
    clip = np.minimum(1.0, peak / np.maximum(fh, 1e-12))
    fh, arrivals = fh * clip, user_bits * scale[:, None] * clip
    se_mean = arrivals.sum(1) / np.maximum(fh.sum(1), 1e-12) * beta
    se = np.where(fh > 0, arrivals / np.maximum(fh, 1e-12) * beta, se_mean[:, None])
    rep = lambda x: np.repeat(x, HOLD_SLOTS, axis=1)[:, :num_slots]
    arrivals, se, fh = rep(arrivals), rep(se), rep(fh)
    return TrafficTrace(arrivals_bits=arrivals, se=se, fh_demand_bits=fh, regime_mult=rep(clip),
                        mean_fh_load=float(fh.sum(0).mean() / cap))
