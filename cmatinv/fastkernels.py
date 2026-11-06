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
