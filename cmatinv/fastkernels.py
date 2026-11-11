"""ctypes bindings for kernels/cmat_kernels.c (compile with kernels/build.sh)."""
import ctypes, os
import numpy as np

_here = os.path.dirname(__file__)
_lib = ctypes.CDLL(os.path.join(_here, "..", "kernels", "libcmat.so"))
_p = ctypes.c_void_p
_lib.ns_step_batch.argtypes = [_p, _p, _p, _p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
_lib.chol_inverse_batch.argtypes = [_p, _p, ctypes.c_int, ctypes.c_int, ctypes.c_int]


def ns_step(G, X, out=None, threads=4):
    """Fused X <- X (2I - G X); returns (X_new, resid) with resid = ||I - G X||_F / sqrt(K) of the input X."""
    S, K, _ = G.shape
    out = np.empty_like(X) if out is None else out
    resid = np.empty(S, np.float32)
    _lib.ns_step_batch(G.ctypes.data, X.ctypes.data, out.ctypes.data, resid.ctypes.data, S, K, threads)
    return out, resid


def chol_inverse(G, threads=4):
    S, K, _ = G.shape
    out = np.empty_like(G)
    _lib.chol_inverse_batch(G.ctypes.data, out.ctypes.data, S, K, threads)
    return out

_lib.rzf_fused_chol.argtypes = [_p, _p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_int]
_lib.rzf_fused_ns.argtypes = [_p, _p, _p, _p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_int]


def rzf_chol(H, alpha, power, W=None, threads=4):
    """Fused Gram + Cholesky inverse + W = H^H G^-1 (+ power scaling). H [S,K,M] complex64 -> W^T [S,K,M] (row k = beam vector of layer k; W = swapaxes)."""
    S, K, M = H.shape
    W = np.empty((S, K, M), np.complex64) if W is None else W
    _lib.rzf_fused_chol(H.ctypes.data, W.ctypes.data, S, K, M, alpha, power, threads)
    return W


def rzf_ns(H, Xprev, alpha, power, W=None, threads=4):
    """Fused Gram + one Newton-Schulz step from Xprev (updated in place) + W. Returns (W, exact input residual)."""
    S, K, M = H.shape
    W = np.empty((S, K, M), np.complex64) if W is None else W
    resid = np.empty(S, np.float32)
    _lib.rzf_fused_ns(H.ctypes.data, Xprev.ctypes.data, W.ctypes.data, resid.ctypes.data, S, K, M, alpha, power, threads)
    return W, resid

_lib.rzf_fused_fp16.argtypes = _lib.rzf_fused_chol.argtypes
_lib.has_fp16.restype = ctypes.c_int
HAS_FP16 = bool(_lib.has_fp16())


def rzf_fp16(H, alpha, power, W=None, threads=4):
    """Like rzf_chol but the W = X conj(H) product runs in AVX512-FP16 complex FMA (M must be a multiple of 16, K <= 32)."""
    S, K, M = H.shape
    assert HAS_FP16 and M % 16 == 0
    W = np.empty((S, K, M), np.complex64) if W is None else W
    _lib.rzf_fused_fp16(H.ctypes.data, W.ctypes.data, S, K, M, alpha, power, threads)
    return W


def _baselines():
    lib = ctypes.CDLL(os.path.join(_here, "..", "kernels", "librzfbase.so"))
    for f in (lib.rzf_lapack, lib.rzf_eigen):
        f.argtypes = _lib.rzf_fused_chol.argtypes
    return lib


def rzf_library(H, alpha, power, which="lapack", W=None, threads=4):
    """Library baselines with the rzf_chol contract: 'lapack' (OpenBLAS cgemm + LAPACK cposv) or 'eigen' (LLT)."""
    S, K, M = H.shape
    W = np.empty((S, K, M), np.complex64) if W is None else W
    getattr(_baselines(), "rzf_" + which)(H.ctypes.data, W.ctypes.data, S, K, M, alpha, power, threads)
    return W
