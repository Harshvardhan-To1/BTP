"""O-RAN 7.2x downlink fronthaul model: precoding at the O-DU (Cat-A style, M streams) vs precoding at
the O-RU (Cat-B style, K layers + beamforming weights over the C-plane)."""
from __future__ import annotations

import numpy as np

PRB, SYM = 273, 14                # 100 MHz, 30 kHz SCS
SLOTS_PER_S = 2000
OVERHEAD = 1.08
BFP_EXP_BITS = 8


def iq_bits_per_prb_sym(mant_bits):
    return 12 * 2 * mant_bits + BFP_EXP_BITS


def stream_rate_gbps(n_streams, mant_bits=9):
    return n_streams * PRB * SYM * iq_bits_per_prb_sym(mant_bits) * OVERHEAD * SLOTS_PER_S / 1e9


def weight_rate_gbps(M, K, w_bits, update_slots, prb_per_group=3):
    groups = int(np.ceil(PRB / prb_per_group))
    bits_group = K * (M * 2 * w_bits + BFP_EXP_BITS)
    return groups * bits_group * OVERHEAD * SLOTS_PER_S / update_slots / 1e9


def quantize_weights(W, bits):
    """Block-floating-point quantisation, one shared exponent per (subcarrier, user) column of M weights."""
    scale = np.maximum(np.max(np.maximum(np.abs(W.real), np.abs(W.imag)), axis=-2, keepdims=True), 1e-30)
    lv = 2 ** (bits - 1) - 1
    q = lambda x: np.round(x / scale * lv) / lv * scale
    Wq = q(W.real) + 1j * q(W.imag)
    return Wq * np.sqrt(np.sum(np.abs(W) ** 2, axis=(-2, -1), keepdims=True) / np.sum(np.abs(Wq) ** 2, axis=(-2, -1), keepdims=True))
