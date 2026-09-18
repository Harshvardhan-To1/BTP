"""Deadline-feasible demand: the budget rate a cell actually needs.

For a cell with deadline D (slots) and per-slot fronthaul-equivalent arrivals
a_0..a_{H-1} over a horizon, the smallest constant service rate r that lets
every bit be served FIFO within D slots of its arrival (starting from an
empty queue) is

    r*(a, D) = max_{0 <= s <= e < H}  ( sum_{k=s}^{e} a_k ) / (e - s + 1 + D).

Proof sketch: the bits arriving in [s, e] must all be served by slot e + D,
and a constant-rate FIFO server can serve at most r (e - s + 1 + D) bits in
slots s..e+D, so r >= r* is necessary; sufficiency follows from the standard
arrival-curve / service-curve argument (a bit arriving at e is served by
e + D iff the backlog created since the last idle instant s has been cleared,
which is exactly the condition above). The simulator serves in PRB-layer
granularity, so r* is a lower bound that is tight up to one PRB-layer.

Interval-sum demand (sum a_k / H) is the special case D -> infinity up to a
constant; for tight deadlines r* can be several times the mean rate. This is
why forecasting the mean is not enough for low-latency cells.
"""
from __future__ import annotations

import numpy as np


def required_rate(arrivals: np.ndarray, deadline: int) -> float:
    """Minimum constant rate (bits/slot) serving `arrivals` within `deadline` slots."""
    a = np.asarray(arrivals, dtype=float)
    H = a.shape[0]
    if H == 0:
        return 0.0
    cs = np.concatenate([[0.0], np.cumsum(a)])
    s = np.arange(H)[:, None]
    e = np.arange(H)[None, :]
    sums = cs[e + 1] - cs[s]
    lengths = e - s + 1 + deadline
    valid = e >= s
    ratio = np.where(valid, sums / np.maximum(lengths, 1), 0.0)
    return float(ratio.max())


def required_rates(arrivals: np.ndarray, deadlines: np.ndarray) -> np.ndarray:
    """Vectorised over cells: arrivals [N, H], deadlines [N] -> [N]."""
    a = np.asarray(arrivals, dtype=float)
    n, H = a.shape
    if H == 0:
        return np.zeros(n)
    cs = np.concatenate([np.zeros((n, 1)), np.cumsum(a, axis=1)], axis=1)   # [N, H+1]
    s = np.arange(H)[:, None]
    e = np.arange(H)[None, :]
    sums = cs[:, e + 1] - cs[:, s]                                          # [N, H, H]
    lengths = (e - s + 1)[None, :, :] + np.asarray(deadlines, dtype=float)[:, None, None]
    ratio = np.where((e >= s)[None], sums / np.maximum(lengths, 1), 0.0)
    return ratio.reshape(n, -1).max(1)


def backlog_rate(backlog_bits: np.ndarray, deadlines: np.ndarray, hol_age: np.ndarray, interval: int,
                 telemetry_delay: int = 0) -> np.ndarray:
    """Per-slot rate to clear the observed backlog within its remaining slack.

    Bits observed with head-of-line age a (tau slots ago) can still be served
    in D - a - tau + 1 slots. Because a budget is held for the whole interval,
    reserving B/1 for one urgent slot would waste the budget for the other
    T-1 slots, so the slack is floored at ceil(D/2) (bits that cannot be
    cleared at that pace are given up) and capped at the interval length.
    """
    slack = np.clip(deadlines - hol_age - telemetry_delay + 1, np.ceil(deadlines / 2.0), float(interval))
    return backlog_bits / slack
