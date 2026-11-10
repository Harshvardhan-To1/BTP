# Critical review: what is actually new, what is not, and what is weak

Written after a targeted literature check (about 10 papers found through web search, only abstracts and excerpts read, not a
systematic survey). Anything not found is "not found by me", not "does not exist".

## 1. Novelty by component

| Component | Prior art found | Verdict |
|---|---|---|
| Warm start: previous slot's inverse as the initial value for Newton/Neumann inversion, with periodic exact recomputation | Neumann-series inversion for massive-MIMO channels correlated in time or frequency, with the previous inverse as the start and periodic accurate re-inversion (Univ. of Malaga work, "Inversion aproximada de matrices en sistemas Massive MIMO correlados en tiempo o frecuencia"); Newton iteration with `Z0 = A_t^-1` is the standard formulation (Shao 2016; Chebyshev/Newton JWCN 2019) | **Not novel.** I should not have presented it as the core idea. |
| Chebyshev-based initial guess followed by Newton/Neumann | Chebyshev-iteration RZF precoding (IEEE Access 2017: two iterations match RZF, optimised initial value); joint Chebyshev + Neumann / Chebyshev + SOR (JWCN 2019, "ChebI-NS", "ChebI-SOR-AMI"); truncated polynomial expansion with RMT-based design (Kammoun et al. 2014, JWCN 2016) | **Largely prior art.** My version uses a minimax Chebyshev polynomial on a Marchenko-Pastur-derived interval followed by Newton-Schulz, which differs in detail from their third-order Chebyshev matrix iteration, but I did not benchmark against ChebI-NS, so I cannot claim it beats it. |
| Marchenko-Pastur edges to set the polynomial interval | Used in Chebyshev-RZF and in TPE analyses | Not novel in itself. |
| Moment-matched interval `1 + v/s_bar -+ 2 sqrt(v)` from `||G||_F` and diag(G), valid for correlated / near-far channels (coverage measured) | Not found | **Possibly new, incremental.** Cheap and measurable; the lower edge is not reliable (88 to 90% coverage in strongly correlated / Rician cases). |
| Closed-form law `r0 ~ corr * 2 sqrt(K/(M-K)) sqrt(1-rho)` for the warm-start residual and the speed envelope derived from it | Not found | **Possibly new, incremental.** First-order heuristic, validated numerically only (measured/predicted 1.10 to 1.28, up to 1.56), not a proof; only one channel family. |
| Randomised residual certificate with tail bound and per-PRB step selection | Probe-based residual estimation is standard numerical linear algebra (Hutchinson-type); the Laurent-Massart bound I used is textbook | **Application is new to my knowledge; the techniques are not.** The bound is loose (51% bound vs 8% observed for one probe). The fused kernel's exact residual makes the probes unnecessary on CPU. |
| RU-side precoding (O-RAN Category B) to cut fronthaul | Standard O-RAN architecture (layers on the link, weights over the C-plane); an industry source quotes about 15 Gbit/s of weight traffic for per-subcarrier per-slot updates on 64T64R, versus 12 Gbit/s user plane | **Not novel.** My numbers are a model of a known trade-off. |
| Fused CPU kernel for Gram + inverse + W | Batched small-matrix kernels are well established (vendor batched LAPACK, Eigen, FPGA/ASIC massive-MIMO precoders) | **Engineering, not research novelty.** |
| Comparison framework (38.901 aging + sum-rate + fronthaul in one study) | Components are standard | A reasonable system study, not a new method. |

Bottom line: I did not find a component that is clearly new and significant on its own. The defensible contribution is an
**evaluation-and-design-rule study** (closed-form speed envelope, certified step selection, honest negative results), not a
new algorithm. It is a reasonable BTech/conference-workshop level contribution; it is not a breakthrough.

## 2. Weaknesses in the evidence

1. **The 10x to 15x kernel speed-up is against a weak baseline and is mostly threading.** `numpy.linalg.inv` on a batch is
   single-threaded and unoptimised for small complex matrices. At one thread the speed-up is 4.0x (K=8), 3.5x (K=16, M=64),
   3.3x, 2.9x and 2.5x (K=32, M=128). The rest is 4-thread parallelism that the baseline does not use. I did not compare
   against MKL/oneMKL batched routines or Eigen, which would probably close much of the 3 to 4x single-thread gap.
2. **The fronthaul saving depends on weight granularity and ignores its rate cost.** The 72% figure assumes one weight set per
   3-PRB group per slot. Per-PRB weights give 39.3 Gbit/s (67% saving). Per-subcarrier weights, which the industry source
   above implies for mobility tracking, give 146 Gbit/s, which is **worse** than the 118 Gbit/s DU-side baseline. The
   simulation also applies each group's weight at the single sampled subcarrier, so the sum-rate loss from using one weight
   across 3 PRBs (about 1 MHz, larger than a typical coherence bandwidth of a few hundred kHz at 300 ns delay spread) is
   not modelled; the 99.7% is optimistic.
3. **Prior-art comparisons use my own implementations** of Neumann, Joint Newton-Neumann and Gauss-Seidel/CG, not the
   authors' code, and not the closest competitors (ChebI-NS, Chebyshev-RZF, TPE with optimal coefficients).
4. **Simulation only.** Self-written 38.901-style channels, perfect CSI, fixed user set, no scheduling, no channel
   estimation error, no measured data. Few user drops per point (3 to 16); no multi-seed CIs outside exp13.
5. **On CPU, the Newton/tracking idea loses to a good exact inverse** on both operation count and time. Its value on
   GEMM-engine hardware is argued, not measured.
6. **The low-precision win** (0.15% vs 0.88% at 8 bits) depends on assuming wide-accumulate GEMM units and a Gauss-Jordan
   baseline that rounds every operation; a blocked or mixed-precision direct solver would narrow the gap.
7. **Theory is thin.** The Doppler law is a first-order heuristic; the certificate bound is standard concentration applied
   to a stable-rank quantity; no convergence proof for the adaptive policy.
8. **The original repo's open issues remain**: `experiments/exp1..4` import a missing `src/` package, and the
   InverseNet-Ultra "beats LAPACK" claim in the earlier work is not supported by medians.

## 3. What would make it publishable (priority order)

1. Reframe the contribution as a design study: speed envelope law + certified step selection + honest negative results.
2. Implement and compare against ChebI-NS, Chebyshev-RZF and TPE with RMT-optimal coefficients, and warm-started
   Neumann (the Malaga method). Without this, the algorithmic claim is not defensible.
3. Benchmark against MKL batched and Eigen, report single-thread and multi-thread numbers separately.
4. Model weight granularity and frequency interpolation in the fronthaul study; report the break-even granularity.
5. Add channel-estimation error, user scheduling changes and a public measured channel dataset.
6. Prove (or drop) the speed-envelope law; quantify when `corr` is 1.2 vs 1.6.
