"""Block floating point (BFP) I/Q compression -- the O-RAN fronthaul baseline.

O-RAN WG4 CUS (section on U-plane compression) defines BFP with one shared
exponent per block of 12 resource elements (one PRB) per antenna, a 4-bit
exponent field and ``iqWidth``-bit two's-complement mantissas for I and Q.
This module implements that scheme for an arbitrary block length along the
last (subcarrier) axis of a complex matrix.

Encoding of one block ``x`` (complex, length ``B``) with ``b`` mantissa bits:

    m_max = max(|Re x|, |Im x|)
    e     = ceil(log2(m_max / (2^(b-1) - 1)))          shared exponent
    q     = clip(round(x / 2^e), -2^(b-1), 2^(b-1)-1)   integer mantissas

Bits used = ``2 * b`` per complex sample + ``exp_bits`` per block.

Quantisation step is ``Delta = 2^e``; per real component the error is bounded
by ``Delta / 2`` and, under the usual high-rate model, has variance
``Delta^2 / 12``.  Those two facts are what the CSEE bound uses.
"""

from __future__ import annotations

import numpy as np

EXP_BITS = 4
DEFAULT_BLOCK = 12          # one PRB, as in O-RAN


def _block_exponents(x_blocks: np.ndarray, bits: int) -> np.ndarray:
    """Shared exponent per block so the largest |component| fits in ``bits`` bits."""
    max_abs = np.maximum(np.abs(x_blocks.real), np.abs(x_blocks.imag)).max(axis=-1)
    qmax = 2 ** (bits - 1) - 1
    with np.errstate(divide="ignore"):
        e = np.ceil(np.log2(max_abs / qmax))
    e[~np.isfinite(e)] = 0.0            # all-zero block
    return e.astype(np.int32)


def bfp_encode(Y: np.ndarray, bits: int = 8, block_size: int = DEFAULT_BLOCK) -> dict:
    """Encode a complex matrix ``(..., N)`` block-wise along the last axis."""
    if bits < 2 or bits > 16:
        raise ValueError("bits must lie in [2, 16]")
    if block_size < 1:
        raise ValueError("block_size must be >= 1")
    Y = np.asarray(Y, dtype=np.complex128)
    shape = Y.shape
    N = shape[-1]
    n_blocks = -(-N // block_size)
    pad = n_blocks * block_size - N
    if pad:
        Y = np.concatenate([Y, np.zeros(shape[:-1] + (pad,), dtype=Y.dtype)], axis=-1)
    xb = Y.reshape(shape[:-1] + (n_blocks, block_size))
    e = _block_exponents(xb, bits)
    scale = np.exp2(e.astype(np.float64))[..., None]
    lo, hi = -(2 ** (bits - 1)), 2 ** (bits - 1) - 1
    re = np.clip(np.round(xb.real / scale), lo, hi).astype(np.int32)
    im = np.clip(np.round(xb.imag / scale), lo, hi).astype(np.int32)
    return {
        "re": re, "im": im, "exp": e,
        "bits": bits, "block_size": block_size, "shape": shape, "pad": pad,
    }


def bfp_decode(enc: dict) -> np.ndarray:
    scale = np.exp2(enc["exp"].astype(np.float64))[..., None]
    x = (enc["re"] + 1j * enc["im"]) * scale
    shape = enc["shape"]
    x = x.reshape(shape[:-1] + (-1,))
    if enc["pad"]:
        x = x[..., : shape[-1]]
    return x


def bfp_bits_used(enc: dict, exp_bits: int = EXP_BITS) -> int:
    n_samples = int(np.prod(enc["shape"]))
    n_blocks = int(np.prod(enc["exp"].shape))
    return 2 * enc["bits"] * n_samples + exp_bits * n_blocks


def bfp_quantization_noise_energy(Y: np.ndarray, bits: int, block_size: int = DEFAULT_BLOCK,
                                  worst_case: bool = False) -> float:
    """Predicted squared error energy of ``bfp_encode(Y)`` without encoding.

    ``worst_case=False``: sum over samples of ``Delta^2 / 6`` (two real
    components at ``Delta^2/12`` each).  ``worst_case=True``: ``Delta^2 / 2``
    (two components at ``(Delta/2)^2``), a deterministic upper bound.
    """
    Y = np.asarray(Y, dtype=np.complex128)
    shape = Y.shape
    N = shape[-1]
    n_blocks = -(-N // block_size)
    pad = n_blocks * block_size - N
    if pad:
        Y = np.concatenate([Y, np.zeros(shape[:-1] + (pad,), dtype=Y.dtype)], axis=-1)
    xb = Y.reshape(shape[:-1] + (n_blocks, block_size))
    e = _block_exponents(xb, bits)
    delta2 = np.exp2(2.0 * e.astype(np.float64))
    nonzero = (np.abs(xb) > 0).sum(axis=-1)          # zero samples quantise exactly
    per_sample = 0.5 if worst_case else 1.0 / 6.0
    return float((delta2 * nonzero * per_sample).sum())
