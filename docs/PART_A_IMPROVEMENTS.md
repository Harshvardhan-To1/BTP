# Part A: drawbacks and what was done about them

Every number below comes from `experiments_v2/exp19` to `exp25`, run on the CPU-only development VM
(4 vCPU Xeon with AVX-512, no GPU). JSON results are in `results/v2/`. All channels are simulated
(3GPP 38.901 UMa / TDL-A); nothing here uses measured data.

| # | Drawback | Status | Where |
|---|---|---|---|
| 1 | IQ compression code (`src/`) missing; 13-16x was quoted at -20 dB NMSE, a quality that is not usable for 64/256-QAM | Re-implemented and re-evaluated at equal post-detection quality | `iqcomp/`, exp19 |
| 2 | Compression encoder too slow (eigendecomposition per PRB) | C/OpenMP encoder plus certificate-driven basis reuse | `kernels/iq_kernels.c`, exp20, exp21 |
| 3 | Closest prior-art inverters (Chebyshev-iteration RZF, ChebI-NS, TPE, warm Neumann) not compared | Implemented and compared | exp22 |
| 4 | Perfect CSI, fixed user set, few drops without CIs | CSI error, user swaps, 12 drops with bootstrap 95 % CIs; new Schur swap update | exp23, `WarmStartTracker.reschedule` |
| 5 | Kernel only compared with numpy | Compared with OpenBLAS + LAPACK `cposv` and Eigen fixed-size LLT, at 1 and 4 threads | `kernels/rzf_baselines.cpp`, exp24 |
| 6 | RU weights per 3-PRB group scored only at the subcarrier they were computed on | Scored on every subcarrier; delay-domain weight compression added | exp25 |
| 7 | Real-matrix InverseNet benchmark is not the RAN problem | Marked as superseded by the complex batched results | `results/benchmark_summary.md` |
| - | GPU / FPGA timing, measured channels, over-the-air tests | **Not fixable here** (no hardware, no data) | see the end |

## 1. IQ compression at equal post-detection quality (exp19)

Uplink 7-2x, M = 64, 24 PRBs, 256-QAM, per-subcarrier MMSE detection; quality is the post-detection EVM
and SINR. CR is relative to 16-bit I/Q, including all exponents and basis bits. Each entry gives the CR at
the 3GPP 256-QAM EVM limit (3.5 %), then the CR at no more than 1 dB SINR loss. "-" means the point is not
reached. At 10 dB SNR even the uncompressed signal misses 3.5 % EVM.

| config | O-RAN BFP | DFT beamspace | exact SVD + MP rank | pilot sketch + MP rank (ours) | CSI-aided combining (needs DU weights) |
|---|---|---|---|---|---|
| K=4, 20 dB | 3.1 / 2.2 | 2.3 / - | 13.8 / 10.4 | **13.9 / 10.5** | 41.5 / 31.3 |
| K=4, 30 dB | 3.1 / 1.7 | 3.0 / - | 9.2 / - | **11.4 / -** | 41.5 / 25.2 |
| K=8, 20 dB | 3.1 / 2.2 | - / - | 6.9 / 5.2 | **7.0 / -** | 20.8 / 15.7 |
| K=8, 30 dB | 3.1 / 1.7 | - / - | 4.8 / - | **6.6 / -** | 20.8 / 12.6 |

The signal rank per PRB is 16-26, more than K, because the channel varies in frequency within a PRB.
Fixed rank r = K therefore loses 7-26 dB, so the rank is chosen at the Marchenko-Pastur noise edge.
At usable quality the pilot-sketch encoder is 2-4.5x better than O-RAN BFP. The old 13-16x figure only
holds for K = 4. CSI-aided RU combining compresses about 3x more but needs DU combining weights at the RU.

## 2. Encoder speed (exp20, exp21)

Times are for 273 PRBs per slot, median.

| encoder | 1 thread | 4 threads |
|---|---|---|
| numpy O-RAN BFP | 24.4 ms | 24.1 ms |
| numpy pilot sketch | 80.6 ms | 84.2 ms |
| C O-RAN BFP | 3.9 ms | 8.0 ms (memory-bound on this VM) |
| C pilot sketch, basis refreshed every slot | 34.9 ms | 10.4 ms |
| C pilot sketch, 25 % of PRBs refreshed | 12.7 ms | 3.8 ms |

The projection L = Q^H Y alone is 0.37 GFLOP per slot. Meeting the 0.5 ms slot therefore needs an
FPGA, GPU or ASIC, not 4 CPU cores. This is stated as a limitation.

Basis reuse (exp21) relies on an out-of-sample certificate: the energy of a validation symbol (symbol 7)
that falls outside the stored basis. The PRB's basis is refreshed when this energy exceeds thr times its
value at the last refresh. At b = 8:

| speed | certificate (thr 1.1-1.5) | round-robin refresh every 8 slots | refresh every slot |
|---|---|---|---|
| 3 km/h | refreshes 18-43 % of PRBs, CR 6.8-7.4x, 2.8-3.0 dB | CR 7.5x, 3.0 dB | CR 5.7x, 2.6 dB |
| 30 km/h | refreshes 100 %, CR 5.7x, 2.6 dB | 33 dB loss (fails) | CR 5.7x, 2.6 dB |
| 120 km/h | refreshes 100 %, CR 5.7x, 2.6 dB | fails | CR 5.7x, 2.6 dB |

The certificate adapts to speed by itself and never fails, unlike any fixed refresh period.

## 3. Prior-art inverters (exp22)

GEMMs needed for at most 1 % RZF sum-rate loss, cold start. These are our implementations of the
published iterations.

| method | M=64, K=16 | M=128, K=16 | M=64, K=32 |
|---|---|---|---|
| Chebyshev cubic iteration, classical init | 18 | 15 | > 21 |
| Chebyshev cubic iteration, MP-scalar init | 9 | 6 | 12 |
| ChebI-NS-style (1 cubic step + NS) | 9 | 7 | 11 |
| TPE, exact-moment optimal coefficients (moment cost not counted) | **6** | **5** | > 16 |
| Chebyshev-MP + NS (ours) | 7 | **5** | **9** |

Tracking, M = 64, K = 16, rate loss and GEMM-equivalents per slot:

| method | 3 km/h | 30 km/h | 120 km/h |
|---|---|---|---|
| warm Neumann, 4 terms, exact every 8 | 0.000 %, 4.5 | 0.84 %, 4.5 | 86 %, 4.5 |
| warm Neumann, 3 terms, exact every 4 | 0.000 %, 3.25 | 3.5 %, 3.25 | 69 %, 3.25 |
| RMT-WS (ours) | 0.006 %, **2.25** | **0.43 %**, 5.2 | **0.12 %**, 6.25 |

TPE with *oracle* moments beats our cold start by one GEMM at K/M = 0.25. Those moments need an
eigendecomposition, or an RMT prediction that is less accurate. Our scheme is the cheapest at K/M = 0.5,
where TPE does not converge within 16 GEMMs. In tracking, warm-started Neumann is competitive only at
pedestrian speed; it fails at 120 km/h because it has no certificate.

## 4. CSI error, scheduling changes, confidence intervals (exp23)

These runs use 12 drops and report the mean with a bootstrap 95 % CI. The loss is relative to the exact
inverse of the same, possibly estimated, Gram matrix.

* **CSI NMSE -20 / -10 dB:** losses of 0.04-0.24 %, CI upper bound at or below 0.30 %. Fresh estimation noise
  every slot makes consecutive Grams less similar. At -10 dB the certificate therefore refreshes 94-98 %
  of subcarriers, and the warm-start saving disappears unless the CSI is filtered over time (the inverse
  stays correct).
* **User swaps:** the probe certificate reads a residual of only about sqrt(s/K) when s of K users change.
  With one swap per slot at 3 km/h the naive tracker therefore did not refresh and lost 4.7 %
  [4.0, 5.5]. The new `WarmStartTracker.reschedule` downdates the removed users and appends the new ones
  with a Schur-complement block inverse, costing 4s/K GEMM-equivalents.

| 3 km/h | naive | reset rows | Schur swap update |
|---|---|---|---|
| 1 swap / slot | 4.70 % [3.99, 5.46], 6.0 GEMM | 2.72 %, 5.0 | **0.008 % [0.004, 0.012], 2.5** |
| 4 swaps / slot | 0.44 %, 6.25 | 1.16 %, 6.25 | **0.006 % [0.004, 0.009], 3.25** |

At 30 km/h the Schur update gives 0.65-0.70 %, the same as the no-swap case. At 120 km/h every method
refreshes every slot.

## 5. Kernel versus optimised libraries (exp24)

The full RZF precoder (Gram, inverse or Cholesky solve, W) for 273 subcarriers, complex64, in ms. All
three agree to within 1e-6 relative error.

| K x M | ours, 1 thr | Eigen LLT, 1 thr | OpenBLAS + LAPACK, 1 thr | ours, 4 thr | Eigen, 4 thr | OpenBLAS + LAPACK, 4 thr |
|---|---|---|---|---|---|---|
| 8 x 64 | **0.27** | 0.48 | 1.74 | **0.08** | 0.13 | 0.96 |
| 16 x 64 | **0.94** | 1.49 | 4.41 | **0.28** | 0.37 | 1.45 |
| 32 x 64 | **3.79** | 4.68 | 10.77 | **1.02** | 1.20 | 3.04 |
| 16 x 128 | **1.63** | 2.77 | 8.50 | **0.47** | 0.72 | 2.55 |

The fused kernel is 1.2-1.8x faster than Eigen with fixed-size matrices and 2.8-11x faster than
per-subcarrier OpenBLAS/LAPACK calls. The latter are dominated by call overhead at these small sizes.
MKL batched routines and cuBLAS / cuPHY were not available here.

## 6. RU weight granularity (exp25)

The test band is 24 PRBs at full subcarrier resolution, M = 64, K = 16, 8-bit weights updated every
slot, with the fronthaul figure scaled to 273 PRBs. For reference, DU-side precoding (M streams) needs
118 Gbit/s and the K-layer floor is 29.6 Gbit/s.

| scheme (total FH) | DS 30 ns | DS 100 ns | DS 300 ns |
|---|---|---|---|
| 1 weight per 3-PRB group, the old assumption (32.8 Gbit/s) | 0.906 | 0.742 | 0.517 |
| 1 weight per PRB (39.3 Gbit/s) | 0.974 | 0.897 | 0.744 |
| delay domain, 32 taps (42.6 Gbit/s) | 0.974 | 0.968 | 0.888 |
| delay domain, 48 taps (49.1 Gbit/s) | 0.982 | 0.978 | **0.959** |
| delay domain, 64 taps (55.6 Gbit/s) | 0.986 | 0.983 | 0.980 |

(Values are the sum-rate relative to exact per-subcarrier RZF.)

This **corrects** the earlier claim of "72 % fronthaul saving at 0.3 % rate loss" with per-3-PRB-group
weights. That claim only holds for nearly flat channels; at 300 ns delay spread the same weights lose
48 % of the rate. With delay-domain weight compression the RU-precoding split still needs 2.1-2.4x less
fronthaul than DU precoding (49-56 Gbit/s against 118) at 2-4 % rate loss for every delay spread tested.

## What cannot be fixed on this machine

* **GPU / FPGA / ASIC timing.** No accelerator is available. The fronthaul encoder's 0.37 GFLOP per slot
  and the batched inversion should be benchmarked against cuPHY / cuBLAS `matinvBatched` / MAGMA on a
  real GPU.
* **Measured channels.** All results use 38.901 / TDL simulations. The `MassiveMIMOChannel` interface
  (H of shape [S, K, M]) is ready for a public measured data set such as KU Leuven or Lund.
* **Over-the-air / testbed validation** on an O-RAN 7-2x RU, including C-plane signalling cost.
* **MKL batched baselines.** MKL is not installed; Eigen and OpenBLAS/LAPACK were used instead.
