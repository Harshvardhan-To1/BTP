# Complex matrix inversion for split-RAN precoding: novelty, simulations, results

Everything below is reproduced by `python experiments_v2/run_all.py` (about 1 minute, CPU only, needs only numpy,
scipy, matplotlib). Raw numbers: `results/v2/*.json`, figures: `results/v2/*.png|pdf`, tests: `pytest tests`.

## 1. Gaps found in the existing project

1. The inversion benchmark used **real**, i.i.d., well-conditioned matrices `A = G/sqrt(n) + 2I`. Massive-MIMO
   precoding needs **complex Hermitian** Gram matrices `G = HH^H + alpha I` of **correlated, near-far** channels.
2. "InverseNet-Ultra beats LAPACK" is a mean-time statement. In its own table the median at n=100 is 0.46 ms vs
   0.17 ms for LAPACK, and it is a learned-coefficient Newton-Schulz run on a model the benchmark data does not
   resemble. It should not be a headline claim.
3. The slot-to-slot warm start proposed in `REPORT.md` section 6 was never implemented or measured.
4. `experiments/exp1..4` import a `src/` package that is not in the repo, so Part A cannot be re-run.
5. Nothing connected the inversion work to the fronthaul topic of the project (where precoding runs, how often
   weights change, what that costs on the link).

## 2. What was added (`cmatinv/`, `experiments_v2/`)

| Module | Content |
|---|---|
| `channel.py` | 3GPP TR 38.901 UMa NLOS path loss + shadowing (near-far), TDL-A 23-tap profile (frequency selective over 100 MHz), per-user angular-spread spatial correlation, optional Rician LoS, Clarke/Jakes AR(1) aging `rho = J0(2 pi f_D T)` |
| `inverters.py` | complex Neumann, Newton-Schulz, Chebyshev (Clenshaw), prior-art Joint Newton-Neumann, GEMM counter, low-precision GEMM emulation, direct Gauss-Jordan at b bits |
| `tracker.py` | the proposed **RMT-WS** tracker |
| `precoding.py` | RZF weights, sum-rate |
| `fronthaul.py` | O-RAN 7.2x DL fronthaul model: DU-side (M streams) vs RU-side (K layers + weights) precoding |

### Proposed method, "RMT-WS" (random-matrix-theory-guided warm-start inversion)

1. **Equilibrate** `Gh = D^-1/2 G D^-1/2` (unit diagonal; removes the near-far spread, which otherwise wrecks every
   series method).
2. **Zero-eigensolve spectral interval** from the Marchenko-Pastur law and a moment match: `Gh` has spectral mean 1
   and variance `v = ||Gh||_F^2/K - 1`, giving `[a, b] = 1 + v/s_bar -+ 2 sqrt(v)` (K^2 work). Spatial correlation and
   LoS raise `v` and widen the interval automatically, which the fixed-ratio edge `(1 -+ sqrt(K/M))^2` cannot do.
3. **Cold start**: degree-d Chebyshev polynomial on `[a, b]` as the initial guess, then Newton-Schulz (quadratic).
4. **Tracking**: next slot starts Newton-Schulz from the previous inverse (rescaled by the new diagonal).
5. **Randomised residual certificate**: `||(I - Gh X) z|| / ||z||` with 2 Gaussian probes costs `4K^2` MACs
   (about `4/K` of a GEMM) and *predicts* how many Newton steps are needed (`r^(2^n) <= tol`) or that the warm start
   is no longer contractive (`r > 0.3`), in which case the cold start runs. This makes it safe at any speed.

Related work this builds on and differs from (citations from memory plus one search, check before submission):
Neumann-series inversion for massive MIMO (Wu et al. 2013; Prabhu et al. 2013), polynomial-expansion precoding with
RMT-optimal coefficients (Kammoun, Muller, Sikaz, Debbah, JSTSP 2014), Joint Newton-Neumann (Shao et al., 2016),
Gauss-Seidel/Neumann hybrids (CSPA 2025), Taylor-series inversion inside unfolded/GNN precoders (2025), Newton-Schulz
(Ben-Israel and Cohen 1966; Pan and Schreiber 1991), Hutchinson trace estimation, Marchenko-Pastur 1967.
Kammoun et al. already use RMT for polynomial coefficients, so **"RMT-based coefficients" alone is not the novelty**.
What is new here is the combination: moment-matched interval for correlated/near-far channels, Chebyshev-then-Newton
hybrid, certificate-driven warm start with a safe fallback, and the evaluation inside an O-RAN fronthaul model.

## 3. Results (M=64 antennas, K=16 layers unless stated, 10 dB cell-edge SNR, RZF, 30 kHz slots, 3.5 GHz)

**Exp5, spectrum and probability (`exp5_*`).** Gram spectrum matches Marchenko-Pastur. Coverage of `[a, b]` over
24 subcarriers x 30 drops: i.i.d. 100%, correlated (12 deg) 100% / 100%, strongly correlated (3 deg) lower edge 90%,
upper 100%, Rician 6 dB lower edge 88%, upper 99.9%. The fixed-ratio MP+Weyl bound covers the lower edge only 52% /
28% of the time in the last two cases. Lower-edge misses are the known weak spot (near-singular, LoS-dominated
Grams).

**Exp6, cold-start inversion (`exp6_*`), GEMMs (K^3 complex MACs) needed for <= 1% sum-rate loss vs exact:**

| | M=64,K=16 | M=128,K=16 | M=64,K=32 |
|---|---|---|---|
| Neumann w=1 (Prabhu/Wu) | >8 | >8 | >8 |
| Joint Newton-Neumann (Shao) | >10 | >10 | >10 |
| Newton-Schulz, classical init | >10 | >10 | >10 |
| Newton-Schulz, MP-scalar init (ours) | 8 | 8 | >10 |
| **Chebyshev-MP init + Newton-Schulz (ours)** | **6** | **5** | **9** |

The config per budget is chosen on validation drops, then reported on disjoint test drops.

**Exp7, tracking under aging (`exp7_*`), loss vs exact / GEMMs per slot per PRB:**

| speed | exact every 2 slots | cold start (6 GEMM) | warm x1 | warm x2 | **RMT-WS** |
|---|---|---|---|---|---|
| 3 km/h | 1.2% / 0.5 | 0.12% / 6 | 0.006% / 2 | 0.000% / 4 | **0.006% / 2.25** |
| 30 km/h | 16% / 0.5 | 0.14% / 6 | 10.9% / 2 | 0.99% / 4 | **0.45% / 5.2** |
| 120 km/h | 38% / 0.5 | 0.13% / 6 | diverges | diverges | **0.13% / 6.25** (falls back to cold start) |

No fixed warm-start depth is right at every speed; the certificate picks it per PRB and never diverges. The saving
is real at low and medium mobility (2.7x fewer GEMMs than a cold start at 3 km/h); at 120 km/h the method simply
becomes a cold start and gives no saving.

**Exp8, low precision (`exp8_*`).** GEMM operands/results rounded to b mantissa bits, wide accumulate (tensor-core /
NPU style). Sum-rate loss vs fp64 exact, direct Gauss-Jordan (every op rounded) vs Chebyshev+3 Newton (9 GEMMs):
8 bits 0.88% vs 0.15%; 6 bits 5.1% vs 1.4%; ill-conditioned (3 deg spread, 25 dB) at 10 bits 1.2% vs 0.49%. The
tracker at 8 mantissa bits loses 0.70% vs 0.54% at full precision at 30 km/h. The advantage depends on the
wide-accumulate GEMM assumption, which a rank-1-update direct method cannot use.

**Exp9, cost and latency (`exp9_*`), 273 PRBs per slot, complex64, this 4-core CPU:**

| K | LAPACK `inv` | cold start (6 GEMM, numpy) | warm x1 (2 GEMM) | `W = H^H G^-1` product |
|---|---|---|---|---|
| 8 | 0.35 ms | 0.72 ms | 0.09 ms | 0.18 ms |
| 16 | 1.60 ms | 3.09 ms | 0.29 ms | 0.42 ms |
| 32 | 7.82 ms | 16.6 ms | 1.43 ms | 1.05 ms |

Note: the numpy-based timings in this table are superseded by section 3d (C kernels), which shows a tuned Cholesky kernel beats every Newton-based path on CPU. Honest reading: in complex MACs a direct inverse (K^3) is *cheaper* than a single Newton step (2 K^3), and the
cold-start path is slower than LAPACK here. The win is the **tracking** step: batched GEMM runs about 5.5x faster than
batched LAPACK inversion on this CPU, so one warm step fits in a 0.5 ms slot at K=8 and K=16 (0.09 and 0.29 ms) where
LAPACK fits only at K=8; at K=32 neither fits on 4 CPU cores (1.4 vs 7.8 ms). The inversion is also only 6 to 20% of RZF MACs (the Gram and `W` formation dominate), and the
sequential critical path drops from about 3K steps to a few GEMMs, which matters for FPGA/ASIC/GPU. A tuned
Cholesky-based inverse would narrow the CPU gap; this was not measured.

**Exp10, where precoding runs (`exp10_*`), 100 MHz, BFP-9 IQ, 3-PRB weight groups.**
DU-side precoding sends M=64 streams: 118.4 Gbit/s. RU-side precoding sends K=16 layers (29.6 Gbit/s) plus
beamforming weights. With weights refreshed every slot at 8-bit BFP: **32.8 Gbit/s (-72%) at 99.7% of the exact RZF
sum-rate**; 6-bit weights 32.0 Gbit/s at 96.7%. Refreshing less often saves only a few Gbit/s but is costly in rate
at mobility (Tu=4 slots: 97% at 3 km/h, 70% at 30 km/h, 39% at 120 km/h). So RU-side precoding needs a per-slot
weight refresh at mobility, which is exactly the workload the cheap warm-start step makes affordable.

## 3b. Added on day 2: a closed-form law, a certificate guarantee, and confidence intervals

**Doppler-to-warm-start law (`exp11`, `exp12`).** For the residual of the previous slot's inverse,
`r0 = ||I - G_t X_{t-1}||_F / sqrt(K)`, a first-order expansion of the AR(1) channel gives

    r0  ~  corr * 2 * sqrt(K / (M - K)) * sqrt(1 - rho),     1 - rho ~ (pi f_D T)^2  (small Doppler)

so `r0` grows **linearly with UE speed** (measured log-log slope 1.00 at 1 to 20 km/h for K=8 and K=16, at 10 and 25 dB),
and the number of Newton steps needed is `ceil(log2(ln eps / ln r0))`. Measured / predicted over 7 (M, K) pairs
(K/M from 1/16 to 1/2) and speeds 3 and 10 km/h: median 1.10 (range 1.01 to 1.26) for i.i.d. equal-gain channels;
median 1.28 (range 1.20 to 1.56) for 38.901 near-far + 12 deg angular spread, so `corr ~ 1.3` there. The law is least
accurate at K/M = 0.5 (higher-order terms). Consequence, `max_warm_speed_kmh(K, M, corr=1.3)` in `cmatinv/tracker.py`
(3.5 GHz, 0.5 ms slots, `r0 <= 0.3`): about 39 km/h for M=64, K=16; 60 km/h for K=8; 23 km/h for K=32.
This is a design rule: for a given array and user count it says up to what speed a one-step warm start is valid and
when the DU must fall back to a cold start. Not derived rigorously (first-order, large-system heuristics); validated numerically.

**Certificate tail bound (`exp11`).** The probe estimate `r_hat^2 = sum_j ||R z_j||^2 / (p K)` with `z ~ CN(0, I)` is
unbiased for `||R||_F^2 / K`, and `||R z||^2 = sum_i sigma_i^2 e_i` with `e_i ~ Exp(1)`. A Laurent-Massart lower-tail
bound for weighted chi-square sums gives

    P( r_hat^2 <= (1 - d) r^2 )  <=  exp( - p d^2 s / 2 ),     s = (sum sigma_i^2)^2 / sum sigma_i^4  (stable rank of R).

For `d = 0.5`, averaged over aged-channel residuals: empirical miss probability 8.0%, 2.0%, 0.12% for p = 1, 2, 4 vs
bound 51%, 26%, 7%. The bound holds but is loose (it uses a worst-case chi-square tail). Because
`||R||_2 <= ||R||_F = sqrt(K) r`, accepting a warm start when `r_hat <= sqrt(1-d)/sqrt(K)` (0.18 for K=16, d=0.5)
guarantees contraction with probability at least `1 - exp(-p d^2 s / 2)`. That guarantee is conservative: in a safety
audit (480 per-PRB cases, 3 to 120 km/h) the empirical rule `r_hat <= 0.3` had **0 accepted-but-non-contractive cases**
(spectral radius of R < 1 in all), while `0.4` and `0.5` had 4 and 12. The theoretical threshold accepts 43% of cases,
the empirical one 60%.

**Confidence intervals (`exp13`, 16 independent user drops, bootstrap 95%):**

| speed | cold start 6 GEMM | **RMT-WS** |
|---|---|---|
| 3 km/h | 0.41% [0.26, 0.59] at 6 GEMM | **0.011% [0.007, 0.017] at 2.25 GEMM** |
| 30 km/h | 0.41% [0.25, 0.62] at 6 GEMM | 0.62% [0.42, 0.84] at 5.4 GEMM [5.25, 5.54] |
| 120 km/h | 0.39% [0.24, 0.55] at 6 GEMM | 0.39% [0.25, 0.55] at 6.25 GEMM (all cold starts) |

With proper intervals the 30 km/h case is a **wash** (about 10% fewer GEMMs, slightly higher loss); the clear win is
at low mobility (2.7x fewer GEMMs, 30x lower loss than a fixed cold start). Fixed 1- or 2-step warm starts lose 12.9% and
1.8% at 30 km/h and fail completely at 120 km/h.

## 3c. Stronger existing baselines (`exp14`): the honest answer to "do we beat prior art?"

GEMMs (K^3-MAC equivalents) needed for <= 1% sum-rate loss, cold start, same test drops:

| | M=64,K=16 | M=128,K=16 | M=64,K=32 |
|---|---|---|---|
| Gauss-Seidel (sweep counted as 1 GEMM-equivalent) | **6** | **4** | >12 |
| Block conjugate gradient (no spectrum info) | 7 | 5 | 12 |
| Chebyshev-MP init + Newton-Schulz (ours; best of config grid per budget, so flattering to us) | **6** | 5 | **9** |

So against Gauss-Seidel and CG, which are standard in the massive-MIMO precoding literature, **we do not win on
operation count when K/M <= 0.25** (tie or loss); we win only at K/M = 0.5. Their cost counts hide that Gauss-Seidel
sweeps are sequential triangular solves (critical path about K per sweep) and CG needs inner-product reductions each
iteration, whereas our kernels are pure GEMMs plus a closed-form interval. Whether that matters depends on the target
hardware and was **not measured**. The earlier claim (we beat Neumann / Joint Newton-Neumann / classical Newton-Schulz)
stands, but those are older baselines and are my own implementations. Gauss-Seidel and CG were not warm-started here;
a warm-started comparison is the fair next test of the tracking contribution.

## 3d. C kernels and an honest correction of the timing claims (`kernels/`, `exp15`, `exp16`)

I wrote batched complex64 C kernels (`kernels/cmat_kernels.c`, AVX/FMA via `-march=native`, OpenMP over PRBs,
`kernels/build.sh`, Python binding `cmatinv/fastkernels.py`): (a) a **fused Newton-Schulz step** `X <- X(2I - GX)` that
also returns the **exact** residual `||I - GX||_F / sqrt(K)` of its input as a by-product (the product `GX` is already
computed, so the certificate costs K^2 extra instead of a probe pass; since `||R^2||_F <= ||R||_F^2` the output residual
is deterministically bounded by the input residual squared), and (b) a **Cholesky-based exact inverse** as the
strongest direct baseline. Both match numpy to float32 precision (relative error 1e-7 to 3e-7).

Wall-clock per slot, 273 PRBs, complex64, 4-core Xeon, median of 40 runs:

| K | numpy/LAPACK `inv` | C Cholesky inverse (4 thr) | numpy NS step | **C fused NS step (4 thr)** |
|---|---|---|---|---|
| 8 | 0.353 ms | 0.041 ms | 0.089 ms | 0.035 ms |
| 16 | 1.593 ms | 0.124 ms | 0.289 ms | 0.115 ms |
| 32 | 7.876 ms | 0.582 ms | 1.463 ms | 0.662 ms |

What this says:
- **Real improvement:** the C kernels run the DU inversion 10 to 13x faster than numpy/LAPACK (K=16: 1.59 ms -> 0.12 ms;
  K=32: 7.9 ms -> 0.58 ms), and K=16 now fits in a 0.5 ms slot with room to spare. This is a genuine CPU result.
- **Correction:** the earlier claim that a warm Newton step is "5.5x faster than LAPACK" compared against a slow
  library path. Against a tuned Cholesky kernel the NS step is **not faster**: 0.115 vs 0.124 ms at K=16, 0.66 vs
  0.58 ms at K=32, and the adaptive tracker averages 2.25 to 6.25 steps. **On this CPU, a good direct inverse beats
  the proposed tracker on both time and operation count.** The tracking contribution can only pay off on hardware
  where GEMM engines are far more efficient than sequential factorisation (GPU, NPU, systolic arrays, RU
  accelerators), which I could not test.
- After the inverse is optimised, the Gram `H H^H` and `W = H^H G^-1` products (numpy batched matmul) become the
  dominant cost at K=16 (about 0.43 ms each); fusing those in C is the next kernel step (not done).

**Warm-started Gauss-Seidel / CG (`exp16`)**, loss vs exact / GEMM-equivalents per slot (4 drops, K=16, M=64):

| | 3 km/h | 30 km/h | 120 km/h |
|---|---|---|---|
| exact Cholesky | 0 / 1 | 0 / 1 | 0 / 1 |
| warm Gauss-Seidel x2 | 0.23% / 2 | 5.9% / 2 | 16.9% / 2 |
| warm Gauss-Seidel x4 | 0.009% / 4 | **0.63% / 4** | 2.9% / 4 |
| warm CG x4 (+1 residual) | 0.013% / 5 | 0.96% / 5 | 5.5% / 5 |
| RMT-WS (ours) | **0.006% / 2.25** | 0.43% / 5.2 | **0.12% / 6.25** |

Against the iterative baselines we win at 3 km/h (about 40x lower loss than GS x2 at similar cost) and at 120 km/h
(0.12% vs 2.9% for GS x4, because the certificate triggers a cold start), and at 30 km/h GS x4 is on the same
cost-accuracy frontier (0.63% at 4 vs 0.43% at 5.2). Against the exact Cholesky inverse we win nowhere on CPU.

## 3e. Kernel optimisation of the whole precoder (`kernels/cmat_kernels.c`, `exp17`)

Treating the DU workload as a kernel-programming task, I fused the whole per-PRB RZF chain into one C pass
(`rzf_fused_chol`, `rzf_fused_ns`): load H once, Gram `H H^H + alpha I` (lower triangle only), Cholesky inverse
(or one fused Newton step with its free exact residual), `W = H^H G^-1` and the power scaling, all L1/stack
resident, OpenMP across PRBs, split re/im planes, `-O3 -march=native -ffast-math`. Optimisations that mattered:

1. Hermitian symmetry: Gram computed on the lower triangle only, Cholesky reads only the lower triangle.
2. Fusion: no intermediate G, X or W arrays in DRAM; one load of H, one store of W.
3. Register-blocked axpy formulation of `W = H^H X` (32-wide m blocks, accumulators stay in vector registers across the
   j loop) and a transposed output layout `W^T [S, K, M]` so every inner loop is contiguous. This alone cut the
   K=16, M=64 precoder from 0.81 ms to about 0.42 ms.
4. A 4-column register-blocked Gram variant was tried and was **slower** (0.65 ms), so it was reverted.

Whole precoder per slot (273 PRBs, complex64, 4-core Xeon, median of 40 runs), numpy + LAPACK vs fused C (4 threads):

| K, M | numpy + LAPACK | fused C, Cholesky | fused C, Newton step | speed-up |
|---|---|---|---|---|
| 8, 64 | 1.09 ms | 0.12 ms | 0.13 ms | 9.1x |
| 16, 64 | 3.29 ms | 0.46 ms | 0.42 ms | 7.1x |
| 32, 64 | 12.5 ms | 1.53 ms | 1.66 ms | 8.1x |
| 16, 128 | 4.81 ms | 0.70 ms | 0.65 ms | 6.9x |
| 32, 128 | 15.7 ms | 2.36 ms | 2.52 ms | 6.6x |

Thread scaling is close to linear (K=16, M=64: 1.58 -> 0.78 -> 0.46 ms for 1, 2, 4 threads). **K=8 and K=16 (M=64) now fit
a 0.5 ms slot on 4 CPU cores for the entire precoder**, which numpy+LAPACK does not for K=16 (3.3 ms). Numerical error
vs the float64 reference is 2e-7 to 4e-7 (single precision). Timings vary by about 10% between runs on this shared VM.

Interpretation: this is a solid kernel-engineering result (about 7 to 9x), and it applies equally to the exact
Cholesky path. The warm Newton path ties but does not beat Cholesky inside the fused pipeline (0.42 vs 0.46 ms), so
on a CPU the practical recommendation is the fused Cholesky kernel; the Newton/certificate machinery is for
GEMM-engine hardware. Not done: AVX-512 / AMX paths, FP16 kernels, cache-blocking for K > 32, NUMA pinning, and the
Gram step is still the largest single stage.
Build: `kernels/build.sh` (needs gcc with OpenMP); the library is git-ignored. Requires an x86 CPU with AVX/FMA for the
`-march=native` build.

## 4. Claims we can defend, and ones we cannot

Defensible: (i) a moment-matched MP interval is a probabilistic, eigensolve-free spectral model that works for
correlated and near-far channels; (ii) Chebyshev-then-Newton beats Neumann-type schemes (Neumann, Joint Newton-Neumann, classical Newton-Schulz) at
equal GEMM budget, but only ties or loses to Gauss-Seidel/CG on operation count for K/M <= 0.25 (section 3c); (iii) certificate-driven warm start cuts tracking cost 2.7x at low mobility (not at 30 km/h and above) and is
safe at high mobility, with a closed-form speed envelope and a probabilistic safety bound for the certificate; (iv) RU-side precoding with per-slot refreshed 8-bit weights saves 72% fronthaul at 0.3% rate loss.

Not defensible: that it needs fewer arithmetic operations than a direct Cholesky/LU inverse (it does not at K <= 32);
that it beats LAPACK in cold-start wall-clock; any "real-world measured" claim. **No measured channel data is
used**; channels are 3GPP TR 38.901 / ITU-R M.2412-style simulations with standard parameters. The next step for
real-world evidence is a public measured massive-MIMO set (for example the KU Leuven or Lund measurements) fed
through `MassiveMIMOChannel`'s interface (H of shape [S, K, M]).

## 5. Other limitations

Fixed user set (no scheduling changes between slots), perfect CSI (no estimation error), per-PRB-group weights
without frequency interpolation, single seed family with 3 to 12 drops per point (no confidence intervals yet),
CPU-only timing, the lower spectral edge is not always covered, and the fronthaul model ignores C-plane signalling
and weight compression beyond BFP.

## 6. Suggested next steps for the paper

Done on day 2: confidence intervals for the tracking table, certificate tail bound, Doppler law. Remaining: a Cholesky-inverse timing baseline, channel-estimation error, user
scheduling changes (certificate-triggered refresh), measured channels, a fixed-point FPGA cost estimate, and
close the loop with Part B by letting the weight-refresh rate be a per-cell knob in the fronthaul allocation rule.
