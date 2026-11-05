"""Markov-fluid theory for the deadline-feasible rate: effective bandwidth, Chernoff tail bounds and the
shortfall sandwich that justifies the newsvendor surrogate.

Setting
-------
A cell's fronthaul demand d_1, d_2, ... is a discrete-time Markov-modulated process: a phase chain X_t
on {0, ..., K-1} with transition matrix P and, given X_t = k, an increment d_t with log-MGF
psi_k(theta) = log E[exp(theta d_t) | X_t = k] (Gamma increments here, but any family with an MGF works).
The horizon has H slots and the deadline is D slots, so the deadline-feasible rate is

    r* = max_{1 <= s <= e <= H}  A(s, e) / (e - s + 1 + D),       A(s, e) = d_s + ... + d_e.

Window log-MGF (Markov-additive process). With Phi(theta) = diag(exp(psi_k(theta))) and pi the stationary
law of the phase at the start of the window,

    Lambda_l(theta) = log E[exp(theta A(1, l))] = log( pi^T Phi (P Phi)^{l-1} 1 ).

Effective bandwidth (Kesidis-Walrand-Chang 1993; Chang 1994):

    alpha(theta) = lim_{l -> inf} Lambda_l(theta) / (l theta) = log rho(P Phi(theta)) / theta,

rho the spectral radius; alpha is non-decreasing from the mean rate (theta -> 0) to the peak rate.

Proposition (Chernoff-union tail bound on r*). For every x > 0,

    P(r* > x) <= sum_{l=1}^{H} (H - l + 1) * min_{theta > 0} exp( -theta x (l + D) + Lambda_l(theta) ) =: U(x).

Proof: {r* > x} = union over windows [s, e] of {A(s, e) > x (e - s + 1 + D)}; a window of length l occurs
H - l + 1 times and, under a stationary start, has the law of A(1, l); the union bound and the Chernoff
inequality P(A > y) <= exp(-theta y + Lambda_l(theta)) for every theta > 0 give the claim.

Corollary (large-deadline decay). Since Lambda_l(theta) <= l theta alpha(theta) + c(theta) with c
independent of l (Perron-Frobenius), for x above the mean rate, U(x) <= H^2 C(theta) exp(-theta x D)
for every theta with alpha(theta) <= x, so  limsup_{D -> inf} (1/D) log P(r* > x) <= -x theta*(x) with
theta*(x) = sup{theta : alpha(theta) <= x}. This is the effective-bandwidth decay rate of the fluid queue
served at rate x, evaluated at buffer level x D (a bit that waits D slots at rate x sits behind x D bits).

Proposition (shortfall sandwich). Serve the arrivals a_1..a_H FIFO at constant rate r with deadline D from an
empty queue and let V(r) be the volume dropped at the deadline. Then

    (D + 1) (r* - r)^+   <=   V(r)   <=   sum_t (a_t - r)^+ .

Proof. Upper bound: the queue can only grow by (a_t - r)^+ in slot t, and every dropped bit was once part of
that growth. Lower bound: let [s*, e*] attain r*; all bits arriving in that window have to leave the system
by e* + D, and the server removes at most r (e* - s* + 1 + D) of them in that time, so at least
A(s*, e*) - r (e* - s* + 1 + D) = (e* - s* + 1 + D)(r* - r) >= (D + 1)(r* - r) bits are dropped.
Consequently the expected weighted violation of an interval is at least (D_i + 1) times the weighted
expected newsvendor shortfall sum_i w_i E[(B_i + X_i - r_i)^+], which is the quantity the KKT rule
minimises; with the backlog treated as deterministic the surrogate is exact up to the upper-bound gap.
"""
from __future__ import annotations

from typing import Tuple
import numpy as np

from .demand import required_rate


# ---------------------------------------------------------------------------
# log-MGFs
# ---------------------------------------------------------------------------
def gamma_log_mgf(theta: np.ndarray, mean: np.ndarray, cv: np.ndarray) -> np.ndarray:
    """log E exp(theta X) for X ~ Gamma with the given mean and coefficient of variation.

    shape k = 1/cv^2, scale s = mean/k; log-MGF = -k log(1 - theta s), finite for theta < 1/s.
    Returns +inf where the MGF does not exist. Broadcasts over theta / mean / cv.
    """
    theta = np.asarray(theta, dtype=float)
    mean = np.asarray(mean, dtype=float)
    cv = np.asarray(cv, dtype=float)
    k = 1.0 / np.maximum(cv, 1e-6) ** 2
    s = mean / k
    arg = 1.0 - theta * s
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(arg > 0, -k * np.log(np.where(arg > 0, arg, 1.0)), np.inf)
    return np.where(mean <= 0, 0.0, out)


def theta_max(mean: np.ndarray, cv: np.ndarray) -> float:
    """Largest theta for which every phase MGF is finite (open at the right end)."""
    mean = np.asarray(mean, dtype=float)
    cv = np.asarray(cv, dtype=float)
    k = 1.0 / np.maximum(cv, 1e-6) ** 2
    s = mean / k
    pos = s > 0
    return float(1.0 / s[pos].max()) if pos.any() else np.inf


# ---------------------------------------------------------------------------
# Markov-additive window log-MGF and effective bandwidth
# ---------------------------------------------------------------------------
def window_log_mgf(P: np.ndarray, log_phi: np.ndarray, pi: np.ndarray, H: int) -> np.ndarray:
    """Lambda_l(theta) for l = 1..H and a grid of theta.

    P [K, K]; log_phi [G, K] = psi_k(theta_g); pi [K]. Returns [G, H]. Computed in log space with
    per-step renormalisation so that long windows do not overflow.
    """
    G, K = log_phi.shape
    out = np.empty((G, H))
    # v_g = pi^T Phi_g  (row vector per theta)
    log_v = np.log(np.maximum(pi, 1e-300))[None, :] + log_phi          # [G, K]
    for l in range(1, H + 1):
        m = log_v.max(1, keepdims=True)
        out[:, l - 1] = (m[:, 0] + np.log(np.exp(log_v - m).sum(1)))
        if l < H:
            v = np.exp(log_v - m)                                       # [G, K]
            v = v @ P                                                   # [G, K]
            log_v = m + np.log(np.maximum(v, 1e-300)) + log_phi
    return out


def effective_bandwidth(P: np.ndarray, log_phi_fn, theta: np.ndarray) -> np.ndarray:
    """alpha(theta) = log rho(P Phi(theta)) / theta for a vector of theta (log_phi_fn(theta) -> [K])."""
    theta = np.atleast_1d(np.asarray(theta, dtype=float))
    out = np.empty_like(theta)
    for g, th in enumerate(theta):
        lp = log_phi_fn(th)
        if not np.all(np.isfinite(lp)):
            out[g] = np.inf
            continue
        M = P * np.exp(lp)[None, :]
        rho = np.max(np.abs(np.linalg.eigvals(M)))
        out[g] = np.log(rho) / th if th > 0 else np.nan
    return out


def chernoff_union_tail(x: np.ndarray, P: np.ndarray, mean: np.ndarray, cv: np.ndarray, pi: np.ndarray,
                        deadline: int, H: int, n_theta: int = 48) -> np.ndarray:
    """Upper bound U(x) on P(r* > x) for a Markov-modulated Gamma source (vector of x; fronthaul units).

    theta is optimised on a log-spaced grid below theta_max; the bound is clipped to 1.
    """
    x = np.atleast_1d(np.asarray(x, dtype=float))
    th_max = theta_max(mean, cv)
    if not np.isfinite(th_max):
        th_max = 1.0 / max(mean.max(), 1e-9)
    thetas = th_max * np.logspace(-3.5, np.log10(0.995), n_theta)         # log-spaced below theta_max
    log_phi = np.stack([gamma_log_mgf(th, mean, cv) for th in thetas])    # [G, K]
    ok = np.all(np.isfinite(log_phi), axis=1)
    thetas, log_phi = thetas[ok], log_phi[ok]
    Lam = window_log_mgf(P, log_phi, pi, H)                                # [G, H]
    ls = np.arange(1, H + 1)
    # exponent[g, l, j] = -theta_g x_j (l + D) + Lambda_l(theta_g)
    expo = -thetas[:, None, None] * x[None, None, :] * (ls + deadline)[None, :, None] + Lam[:, :, None]
    best = expo.min(0)                                                     # [H, J]
    mult = (H - ls + 1)[:, None]
    with np.errstate(over="ignore"):
        U = (mult * np.exp(best)).sum(0)
    return np.minimum(U, 1.0)


def doob_tail(x: np.ndarray, P: np.ndarray, mean: np.ndarray, cv: np.ndarray, pi: np.ndarray,
              deadline: int, H: int, n_theta: int = 200) -> np.ndarray:
    """Supermartingale (Doob / Duffield-type) bound: P(r* > x) <= H * (pi.h / min h) * exp(-theta x D)
    for any theta with alpha(theta) <= x, h the Perron right eigenvector of Phi(theta) P; optimised over theta.

    Proof sketch: for a fixed window start s, N_e = exp(theta (A(s,e) - x(e-s+1))) h(X_{e+1}) is a non-negative
    supermartingale when rho(Phi P) <= exp(theta x); Doob's maximal inequality bounds P(sup_e N_e >= lambda)
    by E[h(X_s)] / lambda, and {r* > x} is the union over the H starts of {sup_e (A(s,e) - x(e-s+1)) > x D}.
    Unlike the union-Chernoff bound this one has only one factor H and carries the deadline in the exponent,
    so it is the sharper of the two for long deadlines; for x below the mean rate it is vacuous.
    """
    x = np.atleast_1d(np.asarray(x, dtype=float))
    th_max = theta_max(mean, cv)
    thetas = th_max * np.logspace(-4, np.log10(0.999), n_theta)
    out = np.ones(len(x))
    for th in thetas:
        lp = gamma_log_mgf(th, mean, cv)
        if not np.all(np.isfinite(lp)):
            continue
        M = np.exp(lp)[:, None] * P                                         # Phi P
        vals, vecs = np.linalg.eig(M)
        k = int(np.argmax(vals.real))
        rho = float(vals[k].real)
        h = np.abs(vecs[:, k].real)
        if h.min() <= 0:
            continue
        C = float(pi @ h / h.min())
        admissible = np.log(rho) <= th * x                                  # alpha(theta) <= x
        cand = np.where(admissible, H * C * np.exp(-th * x * deadline), 1.0)
        out = np.minimum(out, cand)
    return np.minimum(out, 1.0)


def bound_quantiles(levels: np.ndarray, P: np.ndarray, mean: np.ndarray, cv: np.ndarray, pi: np.ndarray,
                    deadline: int, H: int, x_max: float, n_x: int = 80) -> np.ndarray:
    """Conservative quantiles q(alpha) = min{x : U(x) <= 1 - alpha} from the Chernoff-union bound."""
    xs = np.linspace(0.0, x_max, n_x)
    U = chernoff_union_tail(xs, P, mean, cv, pi, deadline, H)
    out = np.empty(len(levels))
    for j, a in enumerate(levels):
        idx = np.nonzero(U <= 1.0 - a)[0]
        out[j] = xs[idx[0]] if len(idx) else x_max
    return out


# ---------------------------------------------------------------------------
# shortfall sandwich (fluid FIFO with deadline)
# ---------------------------------------------------------------------------
def fluid_drops(arrivals: np.ndarray, rate: float, deadline: int) -> float:
    """Volume dropped when a_1..a_H are served FIFO at constant `rate` with deadline D (fluid, empty start).

    Mirrors the simulator's cohort mechanics in fluid form: serve oldest first, then age, drop the cohort
    that would exceed the deadline. Arrivals after the horizon are zero, service continues for D slots.
    """
    a = np.asarray(arrivals, dtype=float)
    H = len(a)
    cohort = np.zeros(deadline + 1)
    dropped = 0.0
    for t in range(H + deadline + 1):
        cohort[0] += a[t] if t < H else 0.0
        rem = rate
        for age in range(deadline, -1, -1):
            x = min(cohort[age], rem)
            cohort[age] -= x
            rem -= x
            if rem <= 0:
                break
        dropped += cohort[deadline]
        cohort[1:] = cohort[:-1]
        cohort[0] = 0.0
    return float(dropped)


def sandwich(arrivals: np.ndarray, rate: float, deadline: int) -> Tuple[float, float, float]:
    """(lower bound, drops, upper bound) of the shortfall sandwich for one arrival vector and rate."""
    a = np.asarray(arrivals, dtype=float)
    rstar = required_rate(a, deadline)
    lo = (deadline + 1) * max(rstar - rate, 0.0)
    hi = float(np.maximum(a - rate, 0.0).sum())
    return lo, fluid_drops(a, rate, deadline), hi
