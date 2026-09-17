"""Matrix inversion techniques being benchmarked.

Every function takes a single (n, n) float32/float64 numpy array and
returns its inverse. Classical methods run on the dtype they are given
(the dataset is float32, matching the precision the neural models use).
"""

from __future__ import annotations

import numpy as np
import scipy.linalg


def lu_inverse(a: np.ndarray) -> np.ndarray:
    """LU decomposition with partial pivoting, then solve A X = I."""
    lu, piv = scipy.linalg.lu_factor(a, check_finite=False)
    return scipy.linalg.lu_solve((lu, piv), np.eye(a.shape[0], dtype=a.dtype), check_finite=False)


def lapack_getri_inverse(a: np.ndarray) -> np.ndarray:
    """numpy.linalg.inv — LAPACK getrf+getri (LU based, tuned reference)."""
    return np.linalg.inv(a)


def gauss_jordan_inverse(a: np.ndarray) -> np.ndarray:
    """Gauss-Jordan elimination with partial pivoting (vectorized numpy)."""
    n = a.shape[0]
    aug = np.hstack([a.astype(a.dtype, copy=True), np.eye(n, dtype=a.dtype)])
    for col in range(n):
        pivot = col + np.argmax(np.abs(aug[col:, col]))
        if pivot != col:
            aug[[col, pivot]] = aug[[pivot, col]]
        aug[col] /= aug[col, col]
        factors = aug[:, col].copy()
        factors[col] = 0.0
        aug -= np.outer(factors, aug[col])
    return aug[:, n:]


def qr_inverse(a: np.ndarray) -> np.ndarray:
    """QR decomposition: A = QR  =>  A^-1 = R^-1 Q^T."""
    q, r = scipy.linalg.qr(a, check_finite=False)
    return scipy.linalg.solve_triangular(r, q.T, check_finite=False)


def svd_inverse(a: np.ndarray) -> np.ndarray:
    """SVD: A = U S V^T  =>  A^-1 = V S^-1 U^T."""
    u, s, vt = np.linalg.svd(a)
    return (vt.T / s) @ u.T


def newton_schulz_inverse(a: np.ndarray, tol: float = 1e-6, max_iters: int = 50) -> np.ndarray:
    """Classic Newton-Schulz iteration X_{k+1} = X_k (2I - A X_k)."""
    n = a.shape[0]
    eye = np.eye(n, dtype=a.dtype)
    norm1 = np.abs(a).sum(axis=0).max()
    norminf = np.abs(a).sum(axis=1).max()
    x = a.T / (norm1 * norminf)
    for _ in range(max_iters):
        ax = a @ x
        x = x @ (2.0 * eye - ax)
        if np.abs(ax - eye).max() < tol:
            break
    return x


CLASSICAL_METHODS = {
    "LU decomposition (scipy lu_factor/lu_solve)": lu_inverse,
    "LAPACK getri (numpy.linalg.inv)": lapack_getri_inverse,
    "Gauss-Jordan elimination": gauss_jordan_inverse,
    "QR decomposition": qr_inverse,
    "SVD": svd_inverse,
    "Newton-Schulz iteration": newton_schulz_inverse,
}
