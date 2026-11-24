"""ctypes bindings for kernels/iq_kernels.c (compile with kernels/build.sh)."""
import ctypes, os
import numpy as np

from .codecs import EXP_BITS
from .uplink import SC, SYM

_lib = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "..", "kernels", "libiq.so"))
_p, _i, _f = ctypes.c_void_p, ctypes.c_int, ctypes.c_float
_lib.bfp_batch.argtypes = [_p, _p, _i, _i, _i, _i, _i]
_lib.pilot_encode.argtypes = [_p, _i, _i, _i, _p, _i, _p, _i, _f, _f, _i, _i, _i, _f, _p, _p, _p, _p, _p, _i]


def bfp(Y, b, threads=4):
    Y = np.ascontiguousarray(Y, np.complex64)
    P, R, n = Y.shape
    out = np.empty_like(Y)
    _lib.bfp_batch(Y.ctypes.data, out.ctypes.data, P, R, n, b, threads)
    return out, P * R * SYM * (SC * 2 * b + EXP_BITS)


def pilot_encode(Y, pilot_cols, b=8, bq=8, margin=1.5, noise_var=1.0, rmax=24, threads=4,
                 refresh=None, state=None, cert_thr=0.0, val_symbol=7):
    """Returns (Qq [P,M,rmax], Lq [P,rmax,n], rank [P], bits). Decode with Qq @ Lq.

    refresh: bool mask [P]; PRBs with False reuse the basis and rank in `state` = (Qq, rank, cert_ref) from
    an earlier call (round-robin basis refresh). With cert_thr > 0 a reused PRB is refreshed anyway when the
    energy of the validation REs (symbol `val_symbol`, not used to build the basis) outside its basis grows
    above cert_thr x its value in the slot where the basis was built. Basis bits are only
    counted for PRBs that were refreshed. Returns (Qq, Lq, rank, bits, refreshed_mask, state).
    """
    Y = np.ascontiguousarray(Y, np.complex64)
    P, M, n = Y.shape
    assert n == SC * SYM
    pil = np.ascontiguousarray(pilot_cols, np.int32)
    vc = np.ascontiguousarray(np.arange(SC) * SYM + val_symbol, np.int32)
    if state is None:
        Qq = np.zeros((P, M, rmax), np.complex64); r = np.ones(P, np.int32); cref = np.ones(P, np.float32)
        refresh = np.ones(P, bool)
    else:
        Qq, r, cref = state
    ref = np.ascontiguousarray(np.ones(P, bool) if refresh is None else refresh, np.uint8)
    Lq = np.empty((P, rmax, n), np.complex64)
    _lib.pilot_encode(Y.ctypes.data, P, M, n, pil.ctypes.data, len(pil), vc.ctypes.data, len(vc), noise_var, margin, b, bq, rmax,
                      cert_thr, ref.ctypes.data, cref.ctypes.data, Qq.ctypes.data, Lq.ctypes.data, r.ctypes.data, threads)
    bits = int(np.sum(ref * r * (M * 2 * bq + EXP_BITS) + r * SYM * (SC * 2 * b + EXP_BITS)))
    return Qq, Lq, r, bits, ref.astype(bool), (Qq, r, cref)
