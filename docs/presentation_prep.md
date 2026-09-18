# Mid-evaluation preparation guide

Companion to `docs/mid_evaluation.pptx` (22 slides: 15 main + 2 reference + 5 backup) and `docs/mid_evaluation_report.md`. Everything below refers only to work that exists in the repository and to numbers in `results/`. Where something is a limitation or was *not* done, say so in the room — the committee will respect that more than a claim you cannot back.

Status tags used everywhere: **[repo]** existed before this iteration · **[new]** built and checked now · **[fix]** corrected · **[prelim]** early result · **[future]** planned.

---

## 1. 60–90 second introduction

> My B.Tech. project is on fronthaul load management in 5G centralised and Open RAN. The radio unit does very little processing and sends the raw received samples — one complex number per antenna and per subcarrier — to the unit that does the baseband work. With 64 antennas and 1200 subcarriers at 16 bits, that is about 34 Gbit/s per radio unit, and several radio units usually share one link. So the question is: for every OFDM symbol, how do we compress each radio unit's data, how many spatial streams do we send, and how do we share the link so the total fits?
>
> A large part of the project is linear algebra. The received matrix has structure — only about 23 propagation paths, so it is low rank and sparse in the delay domain — and every compressor I use is a matrix decomposition that keeps the important part: truncated SVD, a randomised SVD, and a delay-domain (IFFT) truncation, all followed by the standard O-RAN block floating point quantiser. The second linear-algebra part is matrix inversion: the receiver has to invert a matrix every slot, and where that inversion can run decides which functional split is possible. I benchmarked classical inversion methods against three neural networks that try to learn the inverse.
>
> New in this iteration is the part that ties it together: an allocator that shares one link across eight radio units, using a formula for the compression error instead of trial encoding.
>
> Three honest points up front. First, the simulator package was missing from the repository when I started, so I rebuilt and tested it. Second, I found and corrected several errors in the earlier figures. Third, two of the most useful results are negative: the delay-domain compressor only works on reference symbols, and the learned matrix inverter does not beat LAPACK. Everything is simulation — no hardware, no real traffic.

---

## 2. Slide-by-slide speaking guide (target ≈ 14 minutes for slides 1–15)

| # | Slide | ~time | What to say / show | Watch out |
|---|---|---|---|---|
| 1 | Title | 0:20 | Title, one-sentence scope, point at the tag legend. | — |
| 2 | Why the link is the bottleneck | 0:50 | 2.46 Mbit per symbol → 34.4 Gbit/s per RU → 275 Gbit/s for 8 RUs. Three ways to reduce the load. Say what is *not* modelled. | Do not say "latency" or "throughput" — the simulator has neither. |
| 3 | What the project is built from | 1:00 | Three columns: A) compression by matrix decomposition (SVD, randomised SVD, delay-domain, BFP quantiser, ACAFS), B) cost of matrix inversion (classical vs learned), C) sharing one link (new). Stress that A and B are the linear-algebra core. | Keep it to one sentence per bullet; details come later. |
| 4 | Starting point / audit | 1:00 | Walk the table: `src/` missing → rebuilt; SVD baseline fixed; split costs fixed; fake fast-rank curve replaced; error metric clarified; inversion engine bug fixed; allocator added. | Present it as diligence, not blame. |
| 5 | Research context | 1:00 | Seven rows; end with the gap statement. Closest prior art: Aswathylakshmi–Ganti (same delay-domain idea, but they remove data symbols first), Li et al. and Kanno et al. (single-link bit adaptation). | Say "abstract only" for [1][8][13][14][21][25]–[28] if pressed for details. |
| 6 | System model | 0:50 | Diagram: K RUs → one link → DU + controller. `Y = H diag(x) + W`; rank ≤ 23; data vs reference symbols; the two error references. | vs `Y` = what the link carries; vs `H` = signal actually lost. |
| 7 | Compression = decompose, keep, quantise | 1:00 | Table: which decomposition each encoder uses, what is sent, cost, error model. Then the key observation: `diag(x)` keeps the rank but destroys delay sparsity. | This is the finding that explains slide 9. |
| 8 | Allocation + predictor | 1:00 | Multiple-choice knapsack; greedy on the convex hull; Proposition 1 (dropped-tap term exact, quantisation term modelled); noise-aware form; Theorem 2 is HMT's bound. | Do not call Theorem 2 "ours". |
| 9 | Result 1 (Exp1) | 1:00 | Two panels: data vs reference. CSEE −18 dB at 47x on reference, ≈ 0 dB on data. SVD/RAS-BFP identical across panels. Everything flattens at the −20 dB noise floor. | Dashed lines are predictions; Prop. 1 lies on the curve; HMT bound 6–10 dB loose. |
| 10 | Results 2–3 (Exp2, Exp4) | 0:50 | Thin SVD 12.6 ms vs randomised 2.6 ms at M=64 (≈5x, not 100x). Exp4: vs `Y` follows −SNR; vs `H` the decompositions denoise at low SNR. | Python timings → ordering only. |
| 11 | Result 4 (Exp3, ACAFS) | 0:50 | Corrected split costs; streams-only saving 0 % below 15 dB → 83 % at 20 dB; split 6 always cheap but needs RU compute → points to slide 13. Fast estimator biased low, guarded by the stream floor. | Prop. 5 is a prediction, not a bound. |
| 12 | Result 5 (Exp5, allocator) | 1:40 | Panel (a): greedy ≈ oracle; up to 11 dB over uniform; uniform-BFP drops RUs below 55 Gbps. Panel (b): the negative result — plain objective is *worse* than uniform on the signal at 14–27 Gbps; noise-aware objective gains 4–8 dB and releases capacity. Panel (c): min-max improves the worst RU up to 2.2 dB at 0.7–2.6 dB mean cost. | 5 seeds. Menu is CSEE-only ⇒ reference-symbol traffic. |
| 13 | Result 6 — cost of one inversion | 1:00 | Plot: time vs size for all methods. LU 0.14 ms at n=100 (≈7 per core per 1 ms slot), 5.9 ms at n=500 (does not fit). Newton–Schulz 3–7x slower but only matrix multiplies. Role: RU-compute limit for split 6 — [future] to wire in. | Random well-conditioned matrices, not channel matrices. |
| 14 | Result 6b — learned inversion | 1:00 | MLP fails and cannot scale; learned Newton–Schulz (17 parameters) generalises to any n but is slower; Ultra reaches 1e-6 at n=100/500 but 0.17 at n=10 and never beats LU. Bug fixed (ReLU→GELU); docstring corrected. | Do not oversell Ultra; the honest conclusion is "LU wins on a CPU". |
| 15 | Done / limits / next | 1:00 | Read the three columns. Say "no novelty claimed for any single algorithm; the contribution is the validated system and its findings." | — |
| 16–17 | References | 0:10 | Point only. | — |
| 18–22 | Backup | on demand | Audit list; Prop. 1 derivation; RAS-BFP + Thm 2; ACAFS numbers + allocator pseudo-code; reproduction commands. | — |

---

## 3. Equations and algorithms in plain words

**Signal model.** `Y = H·diag(x) + W`. Column `n` of the received 64×1200 matrix is the channel column `h_n` times the transmitted symbol `x_n`, plus noise. TDL-A has 23 paths, so `H = Σ_l a_l e_lᵀ` is a sum of 23 rank-one matrices → rank ≤ 23. An IFFT along the subcarrier axis turns `H` into about 23 (slightly leaked) delay taps → sparse.

**Why CSEE fails on data symbols.** The IFFT of a product is a convolution: `IFFT(H·diag(x)) = IFFT(H) ⊛ IFFT(x)`. If `x` is random QPSK, `IFFT(x)` looks like white noise over all 1200 taps, so the 23 taps get smeared everywhere. Multiplying by `diag(x)`, an invertible matrix, cannot change the rank — so the low-rank encoders do not care.

**BFP (baseline).** Per block of 12 samples: find the largest magnitude, store a shared exponent (4 bits), keep `b`-bit mantissas for I and Q. Bits = `2·b·M·N + 4·M·N/12`. Error per component ≤ Δ/2 with Δ = 2^exponent.

**Truncated SVD.** `Y = UΣVᴴ`; keep the `r` largest singular values. By Eckart–Young this is the best possible rank-`r` approximation, so it is the reference for every low-rank method. Send `BFP(U_rΣ_r)` and `BFP(V_r)`. The thin SVD costs O(MN·M); the old code timed the full square SVD by mistake.

**RAS-BFP (randomised SVD).** `Z = ΩY` — multiply the antenna axis by a random sketch (SRHT or Gaussian) down to r+p rows → QR of `Zᴴ` gives `Q` (N×(r+p)), which spans roughly the same subspace as the top right singular vectors → `L = YQ` → small SVD → rank r → send BFP(L_r), BFP(Q_r). Same payload shape as truncated SVD ⇒ fair comparison. **Theorem 2** is HMT 2011 Thm 10.5 (`E‖Y − QQᴴY‖²_F ≤ (1 + r/(p−1))Σ_{i>r}σ_i²`, Gaussian sketch) plus a triangle-inequality step for the rank-r truncation, giving `(4 + 2r/(p−1))Σ_{i>r}σ_i²`. SRHT is checked empirically only.

**CSEE.** IFFT along the rows → energy per delay tap summed over antennas → keep the top-K taps (one shared set, `K·⌈log₂N⌉` bits of indices) → BFP-quantise the kept 64×K block.

**Proposition 1** (`predict_menu`). Because the IFFT preserves energy (up to the factor `N`), `‖Y − Ŷ‖² = N·(T_S + E_q)`: `T_S` = energy of the dropped taps (exact), `E_q` = quantisation error (estimate `n_bΔ_b²/6` per block, worst case `n_bΔ_b²/2`). Because the top-K sets are nested, one sort gives `T_S` for every K, and the block maxima give Δ for every `b` — the whole 66-setting menu costs one IFFT. Noise-aware form: white noise puts `Mσ²/N` in every tap, so subtract the expected noise from the dropped part, charge the noise in the kept taps, and divide by the signal energy `‖Y‖² − Mσ²` (σ² assumed known at the RU — a stated assumption).

**ACAFS.** Estimate the rank `r` (eigenvalues of `YYᴴ` holding 99 % of the energy; the fast version uses 1/8 of the subcarriers). If `r/M < 0.55` → send `max(r, ⌈0.15·M⌉)` streams; else split 6 if the RU may host the uplink receiver, else all antennas. Bits: all antennas `2MNb`; `r` streams `2rNb + 2Mrb/14`; split 6 `rNη`, η = 6 bit/RE.

**Allocator** (`greedy_allocate`). Each RU has a menu of (rate, error) points. Keep the lower convex hull. Start every RU at its cheapest point; if the total exceeds capacity, drop the RUs whose cheapest point helps least. Then repeatedly take the upgrade with the largest error reduction per bit (sum objective), or upgrade the currently worst RU (max objective), until nothing fits. This is the Shoham–Gersho / Lagrangian bit-allocation algorithm; optimal on the hull up to one fractional step.

**Matrix inversion methods** (`matinv_bench/methods.py`). LU (`scipy.linalg.lu_factor` + `lu_solve` on the identity) and LAPACK `getri` (`numpy.linalg.inv`) — O(n³), the standard. QR: `A = QR`, `A⁻¹ = R⁻¹Qᵀ`. SVD: `A⁻¹ = VΣ⁻¹Uᵀ` (most expensive, but also gives the condition number). Gauss–Jordan: row reduction of `[A | I]`, textbook method, slowest. Newton–Schulz: `X ← X(2I − AX)` from a scaled starting guess; each step only multiplies matrices, converges quadratically once `‖I − AX‖ < 1`.

**Learned inversion** (`matinv_bench/inversenet.py`). InverseNet-MLP: flatten `A`, regress `A⁻¹` with a fully connected network — fails (0.36 relative error at n=10) and cannot scale (n=500 would need > 2 billion parameters). InverseNet-NS: unroll Newton–Schulz for 8 steps as `X ← X(β_k I − γ_k AX)` and learn `α` (start scale) and the 16 step coefficients — 17 parameters, independent of `n`, so it generalises; 4e-4 error at n=100 but slower than LU. InverseNet-Ultra: adds a tiny network that maps four matrix statistics (trace, Frobenius, 1- and ∞-norms) to the starting guess — 1e-6 error at n=100/500 (0.17 at n=10), same speed as classical Newton–Schulz, never beats LU medians. Trained on the first 80 % of each dataset, timed on the last 20 %.

---

## 4. Seventeen likely questions with answers

1. **Why is this "load management" and not just compression?**
   Compression alone decides one RU's setting. Load management here means choosing the settings for all RUs together so the total rate fits the shared link — the multiple-choice knapsack in Exp5. Compression and split selection are the *levers*; the allocator is the *management*.

2. **What exactly was wrong before, and how do I know the new results are right?**
   The `src/` package was never committed, so nothing was reproducible; the SVD baseline was timed as a full N×N SVD; the split model had split 6 as the most expensive, opposite to 3GPP TR 38.801; the "fast rank estimate" was the exact rank plus random noise; the error-vs-SNR claim ignored that the metric follows −SNR by construction; the NumPy inference engine of the learned inverter used a different activation than the trained model. The new code has 42 unit tests (BFP round-trip error bounds, SVD optimality, Prop. 1 vs measured error, HMT bound holds, allocator respects capacity, NumPy engine matches PyTorch, edge cases) and the original figures are kept in `results/original_snapshot/`.

3. **Why is matrix decomposition the right tool for compression here?**
   Because the received matrix has structure that a decomposition exposes. With 23 propagation paths the 64×1200 matrix has rank at most 23, so almost all its energy sits in a few singular vectors (SVD) or a few delay taps (IFFT). A decomposition separates the part that carries the signal from the part that is mostly noise; we send the first and drop the second. Plain quantisation (BFP) cannot do that — it treats every sample the same and only reaches 2x.

4. **Why a randomised SVD instead of the exact one?**
   Cost. The thin SVD of a 64×1200 matrix takes about 13 ms in Python; the randomised version (sketch → QR → small SVD) takes 2.6 ms for the same payload and 1–4 dB more error. Per OFDM symbol (71 µs) even that is too slow in Python, but the ordering and the scaling are what matter. The theory (Halko–Martinsson–Tropp) says the randomised subspace captures the top singular directions with high probability when you oversample by a few columns.

5. **Is ML necessary here? Why no learned model in the fronthaul part?**
   Not for this stage. The rate is known exactly from bit accounting and the error has a closed-form predictor within 0.5 dB, so a learned predictor has nothing to add. The literature uses RL for split orchestration when the cost model can only be measured (Murti et al.); ours is closed-form. The ML in the repository is the learned matrix inverter, and there the result is negative: it generalises but is not faster than LAPACK. ML becomes justified if I need a predictor for RAS-BFP under SRHT (no closed form) or a learned CSI basis as in CsiNet.

6. **What did the learned matrix inversion show, and why keep it if it lost?**
   Three models. The direct MLP fails and cannot scale. The learned Newton–Schulz has 17 parameters, works at any size and reaches 4e-4 error at n=100, but is 2–3x slower than LU. Ultra reaches 1e-6 at n=100 and 500 — but 0.17 at n=10 — and matches classical Newton–Schulz in time, never beating LU medians. I keep it because a negative result answered a real question (can learning beat LAPACK on a CPU for well-conditioned matrices? no), and because the unrolled iteration uses only matrix multiplications, which is the right shape for fixed-latency hardware — that is future work, not a claim.

7. **What do the baselines establish?**
   BFP is what O-RAN deploys — it is the reference for "exact" transport at ≈2x. Truncated SVD is the best rank-r approximation (Eckart–Young), so it bounds what any rank-r method (RAS-BFP) can do. Uniform allocation is today's static configuration. The oracle allocator (encode every option) shows the ceiling of the greedy rule with perfect knowledge — matching it proves the predictor is good enough. LAPACK LU is the reference for inversion.

8. **How realistic are the assumptions?**
   TDL-A is the 3GPP link-level model; 64 antennas, 1200 subcarriers, 15 kHz spacing are standard. Simplified or unrealistic: one OFDM symbol at a time, independent realisations, perfect σ² knowledge in the noise-aware ablation, no MAC/HARQ/latency, split-6 bit rate as a fixed 6 bit/RE, Python timings, and inversion benchmarked on random well-conditioned matrices rather than channel matrices (real MMSE matrices can be badly conditioned, which hurts Newton–Schulz most).

9. **CSEE fails on data symbols — so is it useless?**
   No, but it is a channel / reference-symbol compressor, like CsiNet, not a general I/Q compressor. The closest published work, Aswathylakshmi & Ganti (WCNC 2022), uses the same delay-domain low rank on a 64-antenna TDL-A uplink but first *separates the data symbols by blind deconvolution* — that step is exactly what CSEE lacks, which is why CSEE needs symbols the RU already knows. Reference symbols (DMRS/SRS) are a substantial part of uplink traffic in massive MIMO (a qualitative statement, not measured here), and Exp5 shows the allocator working on that traffic. The honest statement is that the earlier claims for CSEE on general I/Q were wrong.

10. **Why does the error vs Y follow −SNR? Which metric should we trust?**
    A truncating encoder throws away the noise subspace; the vs-Y metric counts that as error, so it floors at the noise level. Against the clean `H` the same encoders *denoise* (Exp4: CSEE −9 dB at 0 dB SNR where the raw matrix is at 0 dB). Both are reported: vs-Y is transport fidelity, vs-H is signal fidelity. The right metric in the end is BLER after the receiver — future work.

11. **Why the greedy allocator and not an exact solver?**
    On the lower convex hull the greedy rule equals the Lagrangian (λ-sweep) solution of Shoham–Gersho up to one fractional step, and it runs in about 1 ms for 8 RUs × 66 options. An exact DP over 8 × 66 is also cheap; I would use it to measure the hull gap as a follow-up, but the oracle comparison already shows the ceiling.

12. **What did the negative result in Exp5 teach you?**
    Minimising the error to the noisy matrix spends bits reproducing noise in the 0–5 dB RUs; on the signal metric that is worse than uniform at 14–27 Gbps. Putting the RU's noise estimate into Proposition 1 fixes it (4–8 dB better vs H) and makes the allocator stop using capacity once extra bits stop helping. The objective, not the algorithm, was the problem.

13. **How accurate is the predictor, and what happens if σ² is wrong?**
    |predicted − measured| ≤ 0.5 dB for CSEE across Exp5 (the BFP predictor is within 1.3 dB). Sensitivity to σ² error is *not* evaluated yet — it is the first item under future work.

14. **Is Theorem 2 your result?**
    No. It is Halko–Martinsson–Tropp's Theorem 10.5 for Gaussian sketches with an Eckart–Young triangle-inequality step for truncation. I use SRHT for speed; the bound is checked empirically (6–10 dB slack in Exp1) and the code returns ∞ for p < 2 rather than an invalid bound.

15. **How does the inversion benchmark connect to the fronthaul problem?**
    Split 6 is the cheapest split on the link but requires the RU to run the uplink receiver, including MMSE-type inverses per resource-block group every slot. The benchmark shows what that costs: a 100×100 inverse takes 0.14 ms on one CPU core (about 7 per 1 ms slot), a 500×500 inverse takes 6 ms and does not fit. Wiring this into ACAFS as an RU-compute constraint is future work.

16. **What is the actual contribution, and is any of it novel?**
    Engineering and validation: a working, tested simulator; corrected baselines; an analytical rate–error menu that makes per-symbol allocation practical; a multi-RU allocator with proper baselines and ablations; the finding about which matrix structure survives modulation; and an honest benchmark of learned vs classical inversion. The encoders adapt known linear algebra (BFP, HMT range finder, delay-domain truncation — cf. Aswathylakshmi & Ganti 2022). The closest prior art for the allocator is single-link (Li et al. 2019; Kanno et al. 2023); extending it to several RUs sharing one link with an analytical predictor is the engineering step. I claim no algorithmic novelty.

17. **What will be different at the final evaluation?**
    Slot-level simulation mixing data and reference symbols with a mixed CSEE/RAS-BFP/BFP menu (needs a RAS-BFP predictor); joint ACAFS + allocation under one capacity with the inversion cost as the RU compute limit; σ² and rank-bias sensitivity; inversion benchmark on real (ill-conditioned) channel matrices; a BLER-based evaluation if a PUSCH chain can be added; C/SIMD timings for the encoders.

---

## 5. Demonstration script

Run from the repository root. Times are on a 4-core CPU.

```bash
pip install -r requirements.txt            # numpy, scipy, pandas, matplotlib, tqdm, pytest (torch only for matinv_bench)
python -m pytest tests -q                  # expected: "42 passed in ~1 s"
```

**Demo 1 — data vs reference symbols (≈10 s)**

```bash
python experiments/exp1_nmse_vs_cr.py
```
Expected last lines (from `results/logs/exp1.log`):
```
[data]      BFP: CR 2.0 -> -46.4 dB | SVD: CR 8.0 -> -20.7 dB | CSEE: CR 46.7 -> -0.5 dB  | RAS-BFP: CR 8.0 -> -16.7 dB
[reference] BFP: CR 2.0 -> -46.4 dB | SVD: CR 8.0 -> -20.7 dB | CSEE: CR 46.7 -> -18.1 dB | RAS-BFP: CR 8.0 -> -16.7 dB
```
Point out: CSEE −0.5 dB vs −18.1 dB; SVD/RAS-BFP identical in both rows.

**Demo 2 — rank-adaptive split (≈3 s)**

```bash
python experiments/exp3_acafs_gain.py
```
Expected: one line per SNR, e.g. `SNR 10 dB: rank 54.5 (fast 45.0, |err| 9.45) saving split6 84.0% beam-space 0.0%` and `SNR 20 dB: rank 10.9 (fast 10.3, |err| 0.65) saving split6 82.7% beam-space 82.7%`.

**Demo 3 — shared-capacity allocation (≈8 s)**

```bash
python experiments/exp5_fronthaul_allocation.py
```
Expected: a table by `capacity_frac × policy`; at `0.1` (27.5 Gbps) `greedy-sum ≈ −18.1 dB`, `uniform-CSEE ≈ −15.6 dB`, `uniform-BFP ≈ −2.0 dB with dropped 3`; `greedy-clean` column `avg_cell_nmse_clean_db_mean ≈ −23.5` vs `greedy-sum ≈ −17.3`.

**Demo 4 — matrix inversion benchmark (≈1 min for n = 10 and 100; needs torch and `data/matrices_dim*.npz`)**

```bash
python -m matinv_bench.generate_dataset --dims 10 100 --num-samples 1000   # if data/ is empty
python -m matinv_bench.benchmark --dims 10 100
```
Expected: a table per dimension sorted by mean time; at n=100 `LU ≈ 0.09 ms`, `LAPACK getri ≈ 0.14 ms`, `InverseNet-NS ≈ 0.33 ms (rel err 4e-4)`, `InverseNet-Ultra ≈ 0.40 ms (rel err 1e-6)`, `SVD ≈ 1.2 ms`. Saved copy: `results/benchmark_summary.md`.

**Optional — notebook walk-through**

```bash
cd notebooks && jupyter nbconvert --execute --to notebook --inplace mid_evaluation_demo.ipynb
```

**Fallback if anything fails live (clearly say "previously generated outputs"):**
- Figures: `results/figures/exp1_nmse_vs_cr.png`, `exp3_acafs.png`, `exp4_snr_sweep.png`, `exp5_allocation.png`, `results/inference_time.png`
- Tables: `results/data/exp5_allocation_summary.csv`, `results/benchmark_results.csv`, `results/benchmark_summary.md`
- Console logs: `results/logs/exp1.log` … `exp5.log`, `matinv_benchmark.log`
- Original (pre-fix) figures for comparison: `results/original_snapshot/figures/`

Troubleshooting seen during this work: `ModuleNotFoundError: src` → run from the repository root (scripts add the root to `sys.path`; the notebook must be launched from `notebooks/`). `libreoffice`/PDF is only needed to re-export the deck; `python docs/build_slides.py` regenerates the `.pptx` from the current results.
