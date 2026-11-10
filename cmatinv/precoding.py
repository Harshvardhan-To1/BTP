"""RZF precoding and sum-rate evaluation."""
from __future__ import annotations

import numpy as np


def gram(H, alpha):
    K = H.shape[-2]
    return H @ np.conj(np.swapaxes(H, -1, -2)) + alpha * np.eye(K)


def rzf_weights(H, Ginv, power):
    """W = H^H G^-1, scaled to total power `power` per subcarrier. H [S,K,M] -> W [S,M,K]."""
    W = np.conj(np.swapaxes(H, -1, -2)) @ Ginv
    p = np.sum(np.abs(W) ** 2, axis=(-2, -1), keepdims=True)
    return W * np.sqrt(power / p)


def sum_rate(H, W, noise=1.0):
    """Downlink sum-rate [bit/s/Hz] averaged over subcarriers. SINR_k = |h_k w_k|^2 / (sum_j!=k |h_k w_j|^2 + noise)."""
    G = np.abs(H @ W) ** 2                              # [S, K, K]
    sig = np.diagonal(G, axis1=-2, axis2=-1)
    intf = G.sum(-1) - sig
    return np.mean(np.sum(np.log2(1 + sig / (intf + noise)), -1))
