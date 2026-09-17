# Problem formulation

## 1. System

An O-RAN-style uplink with `C` radio units (RUs, "cells") connected to one
distributed unit (DU) over a shared fronthaul link. Each RU has `M = 64`
antennas and receives an OFDM symbol of `N = 1200` subcarriers
(15 kHz spacing, 18 MHz occupied; 14 symbols per 1 ms slot). Per symbol and
per RU the RU holds the frequency-domain matrix

    Y_k = H_k diag(x_k) + W_k   in  C^{M x N},        k = 1..C

* `H_k`: TR 38.901 TDL-A channel, 23 Rayleigh taps at delays `tau_l` scaled to
  100 ns RMS delay spread, exponential antenna correlation `rho = 0.7`. Because
  `H_k = sum_l a_l e_l^T` its rank is at most 23 (spatial low rank) and its
  IFFT over subcarriers is concentrated on a few delay bins (delay sparsity).
* `x_k`: unit-modulus symbols. Two cases matter:
  *data symbols* (random QPSK per subcarrier, the bulk of the traffic) and
  *reference symbols* (a known sequence the RU removes, leaving `H_k + W'_k`).
* `W_k ~ CN(0, sigma^2)`, `sigma^2 = 10^(-SNR/10)`; `E|H|^2 = 1`.

Uncompressed antenna-space I/Q for one symbol costs `R_raw = 2 M N b_0` bits
with `b_0 = 16` bits per component: 2.46 Mbit per symbol, 34.4 Gbps per RU.

## 2. Decision variables and actuators

Per RU and per scheduling interval the controller chooses

1. an **encoder operating point** `a_k` from a finite menu, e.g.
   BFP mantissa width `b`, CSEE `(K, b)`, or a low-rank `(r, b)`;
2. optionally the **functional split / stream count** (ACAFS): antenna-space
   (M streams), beam-space (r streams), or split 6 (transport blocks).

Each operating point has an exactly computable **rate** `R_k(a)` in bits per
symbol (bit accounting in `src/encoder/*.bits_used`) and a **distortion**
`D_k(a) = ||Y_k - Y_hat_k||_F^2 / ||Y_k||_F^2` (linear NMSE).

## 3. Constraint and objective

    minimise   sum_k D_k(a_k)          [or  max_k D_k(a_k) for min-max fairness]
    subject to sum_k R_k(a_k) <= C_link            (shared link capacity, bits/symbol)
               a_k in menu

This is a multiple-choice knapsack. It is solved by a greedy marginal-gain
rule on the lower convex hull of each RU's (rate, distortion) points
(`src/control/allocator.py`), which is the Lagrangian-relaxation optimum up to
one fractional upgrade. Complexity O(C x |menu| x log) per interval; measured
~1 ms for 8 RUs x 66 options in Python, plus ~30 ms for the predictions.

Why NMSE and not throughput/BLER: the simulator models one symbol of the
physical layer up to the DU input; it has no scheduler, no channel estimator,
no decoder. NMSE of the transported matrix is the only distortion the model can
measure honestly. Two references are reported: NMSE vs the transported
(noisy) `Y` - what the link sees - and NMSE vs the noiseless `H` (reference
symbols) - what was actually lost, because encoders that discard noise-only
components otherwise look worse than they are. Neither is "end-to-end
latency" or "BLER", and the documentation does not call them that.

## 4. The rate-distortion predictors that make the allocation cheap

The controller must know `D_k(a)` for every menu option *without* encoding.

**Proposition 1 (CSEE).** With `Y_d = IFFT(Y)` row-wise, numpy normalisation
(`||Y||^2 = N ||Y_d||^2`), support `S` = top-K delay bins by antenna-summed
energy, and BFP quantiser `Q`,

    NMSE = ( T_S + E_q ) / ||Y_d||_F^2,
    T_S  = sum_{n not in S} ||Y_d[:, n]||^2          (exact, Parseval),
    E_q  = ||Y_d[:, S] - Q(Y_d[:, S])||_F^2.

`E_q` is predicted from block exponents only: `sum_blocks n_b Delta_b^2 / 6`
(high-rate estimate) or `sum_blocks n_b Delta_b^2 / 2` (deterministic worst
case, a true upper bound). Measured vs. predicted agree within 0.1-0.4 dB
(Exp5, `pred_abs_err_db`). Because top-K supports are nested, a whole menu of
`(K, b)` pairs costs about one encoder pass (`CSEEEncoder.predict_menu`).

**Theorem 2 (RAS-BFP, adapted from Halko-Martinsson-Tropp 2011, Thm 10.5).**
For a Gaussian sketch of size `r + p`, `p >= 2`, the projection error obeys
`E||Y - Y Q Q^H||_F^2 <= (1 + r/(p-1)) sum_{i>r} sigma_i^2`, and after
truncating the projected matrix to rank r,
`E||Y - Y_hat||_F^2 <= (4 + 2r/(p-1)) sum_{i>r} sigma_i^2`. The encoder uses an
SRHT sketch by default, for which the Gaussian bound is a reference checked
empirically (Exp1: the bound sits 6-10 dB above the measured curve).

**Eckart-Young floor.** No rank-r scheme can beat `sum_{i>r} sigma_i^2`; the
SVD baseline sits on it up to quantisation (tested).

## 5. Functional split model (ACAFS)

Per symbol, per RU: antenna-space `2 M N b`; beam-space `2 r N b + 2 M r b / T_c`
(weights refreshed every `T_c = 14` symbols); split 6 `r N eta` with
`eta = 6` bits per resource element. Ordering `R_6 << R_beam <= R_ant`.
Decision: `r/M < tau_high` -> beam-space with `max(r, ceil(tau_low M))`
streams; otherwise split 6 if the RU may run the full UL PHY, else antenna-space.
Savings are reported relative to the fixed antenna-space split.
Proposition 5 is the expected saving for r uniform on {1..M} - a model
prediction, not a bound.

## 6. Trade-offs the model can and cannot express

* Utilisation vs distortion: captured (Exp5 panel c vs a).
* Fairness: min-max objective vs sum objective (Exp5 greedy-max vs greedy-sum,
  worst cell up to 2.2 dB better at 27.5 Gbps, at a 0.7-2.6 dB cost in the
  per-cell mean; identical once capacity is loose).
* Decision overhead: measured in Python; only relative statements are valid.
* Latency, jitter, MAC scheduling, HARQ, real hardware timing: **not modelled**.
* CSEE is only valid on reference symbols; the allocator experiment therefore
  covers reference-symbol traffic (or any traffic if the menu is BFP-only).

## 7. Contribution, stated carefully

* Engineering: a runnable, tested simulator for the compression / split /
  allocation chain with exact bit accounting and analytical distortion
  predictors (the repository previously contained none of this code).
* Adaptation of known methods: BFP (O-RAN), truncated SVD, delay-domain
  sparsification, randomised range finder (HMT), multiple-choice knapsack
  greedy - none of these is new.
* Findings that are specific to this system and were not in the original
  documents: (i) delay-domain compression fails on modulated data symbols
  while spatial low rank survives; (ii) NMSE against the noisy input saturates
  at -SNR and misrepresents denoising encoders; (iii) the Prop. 1 predictor is
  accurate enough that prediction-based allocation matches an oracle that
  encodes every option.
* Not claimed: novelty of any encoder, hardware feasibility, gains on real
  traffic.
