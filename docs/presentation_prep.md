# Mid-evaluation preparation guide

Companion to `docs/mid_evaluation.pptx` (20 slides: 15 main + 5 backup) and `docs/mid_evaluation_report.md`. Everything below refers only to work that exists in the repository and to numbers in `results/`. Where a statement is a limitation or something *not* done, say so in the room — the committee will respect that more than a claim you cannot back.

Status tags used everywhere: **[repo]** existed before this iteration · **[new]** implemented and validated now · **[fix]** corrected · **[prelim]** preliminary · **[future]** planned.

---

## 1. 60–90 second introduction

> My B.Tech. project is on fronthaul load management in 5G centralised and Open RAN. In these architectures the radio unit does very little processing and ships frequency-domain I/Q samples for every antenna and every subcarrier to a distributed unit. With 64 antennas and 1200 subcarriers at 16-bit I/Q that is about 34 Gbit/s per radio unit, and several radio units usually share one fronthaul link. So the question is: per OFDM symbol, how do we compress each radio unit's data, how many spatial streams do we send, and how do we share the link so that the sum fits the capacity with the least distortion?
>
> My repository contains a Python simulator on 3GPP TDL-A channels with four encoders — the O-RAN block-floating-point baseline, truncated SVD, and two proposed structured encoders — a rank-adaptive functional-split controller, and, new in this iteration, a capacity-constrained allocator that shares one link across eight radio units using an analytical rate–distortion predictor instead of trial encoding.
>
> I want to be upfront about three things. First, at the start of this iteration the simulator package was missing from the repository, so I reconstructed and tested it; second, I found and corrected several modelling errors in the earlier figures; third, the most useful result is partly negative: one of the proposed encoders only works on reference symbols, not data symbols, and I will show why. Everything is simulation — no hardware, no real traces.

---

## 2. Slide-by-slide speaking guide (target ≈ 13 minutes for slides 1–13)

| # | Slide | ~time | What to say / show | Watch out |
|---|---|---|---|---|
| 1 | Title | 0:20 | Title, one-sentence scope, point at the status legend. | — |
| 2 | Why fronthaul load is the bottleneck | 1:00 | Derive 2.46 Mbit/symbol → 34.4 Gbps per RU; three levers; define "load management" as the constrained choice per RU. Say what is *not* modelled. | Do not say "latency" or "throughput" — the simulator has neither. |
| 3 | Starting point / audit | 1:15 | Walk the table row by row: `src/` missing → reconstructed; SVD baseline fixed; split ordering fixed; fake fast-rank curve replaced; NMSE metric clarified; allocator added. | Present it as engineering diligence, not as blame. |
| 4 | Research context | 1:15 | Six rows: standard BFP baseline; split bit-rate ordering from 3GPP; Lagén et al. as closest shared-fronthaul work (downlink, modulation compression); CsiNet explains delay-domain sparsity; RL orchestration exists but our rate model is closed-form; numerical foundations. End with the gap statement. | Say "abstract only" for [1][8][13][14][21] if asked for details. |
| 5 | System model | 1:00 | Diagram: K RUs → one link → DU + controller. Equation `Y = H diag(x) + W`; rank ≤ 23; data vs reference symbols; metrics you can honestly measure. | NMSE has two references: vs `Y` (what the link carries) and vs `H` (signal actually lost). |
| 6 | Formulation + predictor | 1:15 | Multiple-choice knapsack; greedy on convex hull; Proposition 1 (tail term exact, quantisation term modelled); noise-aware variant; Theorem 2 is HMT's bound, for Gaussian sketches. | Do not call Theorem 2 "ours". |
| 7 | Encoders | 1:00 | Table, then the key observation: `diag(x)` preserves rank but destroys delay sparsity. | This is the finding that explains slide 8. |
| 8 | Result 1 (Exp1) | 1:15 | Two panels: data vs reference. CSEE −18 dB at 47x on reference, ≈ 0 dB on data. SVD/RAS-BFP identical across panels. Everything clusters at the −20 dB noise floor. | Bounds are dashed; Prop. 1 coincides; HMT bound 6–10 dB loose. |
| 9 | Results 2–3 (Exp2, Exp4) | 1:00 | Economy SVD 12.6 ms vs RAS-BFP 2.6 ms at M=64 (≈5x, not 100x). Exp4: vs `Y` follows −SNR; vs `H` shows denoising at low SNR. | Python timings → ordering only. |
| 10 | Result 4 (Exp3, ACAFS) | 1:00 | Corrected split ordering; beam-space saving 0 % below 15 dB → 83 % at 20 dB; split 6 always cheap but needs RU compute; fast estimator biased low by up to 10, guarded by the stream floor. | Prop. 5 is a prediction under a uniform-rank assumption, not a bound. |
| 11 | Result 5 (Exp5, allocator) | 1:45 | Panel (a): greedy ≈ oracle; up to 11.5 dB over uniform; uniform-BFP drops RUs below 55 Gbps. Panel (b): the negative result — plain objective is *worse* than uniform on the signal at 14–27 Gbps; noise-aware objective gains 4–8 dB and releases capacity (25 % utilisation at 138 Gbps). Panel (c): min-max improves worst RU up to 2.2 dB at 0.7–2.6 dB mean cost. | 5 seeds, std 0.1–0.8 dB. Menu is CSEE-only ⇒ reference-symbol traffic. |
| 12 | Compute benchmark | 0:45 | LU 0.14 ms at n=100 fits a slot, 5.9 ms at n=500 does not; learned NS generalises but is slower; bug fixed (ReLU→GELU). Role: RU-compute constraint for split 6 — [future] to wire in. | Ultra is 0.17 error at n=10; do not oversell. |
| 13 | Contributions / limitations / plan | 1:15 | Read the three columns. Say "no novelty claimed for any single encoder; the contribution is the validated system and the findings." | — |
| 14–15 | References | 0:10 | Point only. | — |
| 16–20 | Backup | on demand | Audit list; Prop. 1 derivation; RAS-BFP + Thm 2; ACAFS numbers + allocator pseudo-code; reproducibility commands. | — |

---

## 3. Equations and algorithms in plain words

**Signal model.** `Y = H·diag(x) + W`. Each subcarrier `n` of the received 64×1200 matrix is the channel column `h_n` scaled by the transmitted symbol `x_n`, plus noise. TDL-A has 23 paths, so `H = Σ_l a_l e_lᵀ` is a sum of 23 rank-one terms → rank ≤ 23. Taking an IFFT along the subcarrier axis turns `H` into 23 (leaked) delay bins → sparse.

**Why CSEE fails on data symbols.** IFFT of a product is a convolution: `IFFT(H·diag(x)) = IFFT(H) ⊛ IFFT(x)`. If `x` is random QPSK, `IFFT(x)` is white noise across all 1200 bins, so the convolution smears the 23 bins everywhere. Multiplying by `diag(x)`, an invertible matrix, cannot change the rank — so spatial low-rank encoders are unaffected.

**BFP (baseline).** Per block of 12 REs: find the max magnitude, take a shared exponent (4 bits), keep `b`-bit mantissas for I and Q. Bits = `2·b·M·N + 4·M·N/12`. Error per component ≤ Δ/2 with Δ = 2^exponent.

**CSEE.** IFFT rows → energy per delay bin summed over antennas → keep top-K bins (one shared support, `K·⌈log₂N⌉` bits) → BFP-quantise the kept 64×K block.

**Proposition 1** (`predict_menu`). Because IFFT is unitary up to `N`, `‖Y − Ŷ‖² = N·(T_S + E_q)`: `T_S` = energy of discarded bins (exact), `E_q` = quantisation error (estimate `n_bΔ_b²/6` per block, worst case `n_bΔ_b²/2`). Since top-K supports are nested, one sort gives `T_S` for every K, and block maxima give Δ for every `b` — the whole 66-point menu costs one IFFT. Noise-aware variant: white noise contributes `Mσ²/N` per bin, so subtract expected noise from the tail, charge the noise in kept bins, and normalise by signal energy `‖Y‖² − Mσ²` (σ² assumed known at the RU — a stated assumption).

**RAS-BFP.** `Z = ΩY` (SRHT or Gaussian sketch of the antenna axis to r+p rows) → QR of `Zᴴ` gives `Q` (N×(r+p)) spanning the dominant right subspace → `L = YQ` → small SVD → rank r → transmit BFP(L_r), BFP(Q_r). Payload shape equals truncated SVD ⇒ fair CR comparison. **Theorem 2** is HMT 2011 Thm 10.5 (`E‖Y − QQᴴY‖²_F ≤ (1 + r/(p−1))Σ_{i>r}σ_i²`, Gaussian sketch) plus a triangle-inequality step for the rank-r truncation, giving `(4 + 2r/(p−1))Σ_{i>r}σ_i²`. SRHT is checked empirically only.

**ACAFS.** Estimate rank `r` (99 % of the energy of the eigenvalues of `YYᴴ`; fast variant uses 1/8 of the subcarriers). If `r/M < τ_high = 0.55` → beam-space with `max(r, ⌈0.15·M⌉)` streams; else split 6 if the RU may host the UL PHY, else antenna-space. Bits: antenna-space `2MNb`; beam-space `2rNb + 2Mrb/14`; split 6 `rNη`, η = 6 bit/RE.

**Allocator** (`greedy_allocate`). Each RU has a menu of (rate, distortion) points. Keep the lower convex hull. Start every RU at its cheapest point; if the sum exceeds capacity, drop the RUs whose cheapest point is least useful. Then repeatedly take the upgrade with the largest distortion reduction per bit (sum objective) or upgrade the currently worst RU (max objective) until nothing fits. This is the Shoham–Gersho / Lagrangian bit-allocation algorithm; optimal on the hull up to one fractional step.

---

## 4. Fifteen likely questions with answers

1. **Why is this "load management" and not just compression?**
   Compression alone decides one RU's operating point. Load management here means choosing operating points for all RUs jointly so the sum rate fits the shared link — the multiple-choice knapsack in Exp5. Compression and split selection are the *levers*; the allocator is the *management*.

2. **What exactly was wrong before, and how do I know the new results are right?**
   The `src/` package was never committed, so nothing was reproducible; the SVD baseline was timed as a full N×N SVD; the split model had Option 6 as the most expensive split, opposite to 3GPP TR 38.801; the "fast rank estimate" was the exact rank plus random noise; the NMSE-vs-SNR claim ignored that the metric saturates at −SNR. The new code has 42 unit tests (BFP round-trip error bounds, SVD optimality, Prop. 1 vs measured NMSE, HMT bound holds, allocator respects capacity, edge cases) and the original figures are kept in `results/original_snapshot/` for comparison.

3. **Is ML necessary here? Why no learned model?**
   Not for this stage. The rate is known exactly from bit accounting and the distortion has a closed-form predictor within 0.5 dB, so a learned predictor has nothing to add. The literature uses RL for split orchestration when the cost model is only measurable (Murti et al.); ours is closed-form. The repository's ML component is the matrix-inversion benchmark, where learned Newton–Schulz generalises but is not faster than LAPACK. ML becomes justified if I add a predictor for RAS-BFP under SRHT (no closed form) or a learned CSI basis as in CsiNet.

4. **What do the baselines establish?**
   BFP is what O-RAN deploys — it fixes the reference for "exact" transport at ≈2x. Truncated SVD is the best rank-r approximation (Eckart–Young), so it upper-bounds what any rank-r method (RAS-BFP) can do. Uniform allocation is today's static configuration. The oracle allocator (encode every option) shows the ceiling of the greedy algorithm given perfect knowledge — matching it proves the predictor is good enough.

5. **How realistic are the assumptions?**
   TDL-A is the 3GPP link-level model; 64 antennas, 1200 subcarriers, 15 kHz spacing are standard. Unrealistic or simplified: one OFDM symbol at a time, i.i.d. realisations, perfect σ² knowledge in the noise-aware ablation, no MAC/HARQ/latency, split-6 bit rate as a fixed 6 bit/RE, Python timings.

6. **CSEE fails on data symbols — so is it useless?**
   No, but it is a CSI / reference-symbol compressor, like CsiNet, not a general I/Q compressor. Reference symbols (DMRS/SRS) are a substantial part of uplink traffic in massive MIMO (a qualitative statement, not measured here), and Exp5 shows the allocator working on that traffic. The honest statement is that the earlier claims for CSEE on general I/Q were wrong.

7. **Why does NMSE vs Y follow −SNR? Which metric should we trust?**
   A truncating encoder discards the noise subspace; the vs-Y metric counts that as error, so it floors at the noise level. Against the noiseless `H` the same encoders *denoise* (Exp4: CSEE −9 dB at 0 dB SNR where the raw matrix is at 0 dB). Both are reported; the DU actually receives `Ŷ`, so vs-Y is the transport fidelity and vs-H is the signal fidelity. The right metric ultimately is BLER after the receiver — future work.

8. **Why the greedy allocator and not an exact solver?**
   On the lower convex hull the greedy marginal-gain rule equals the Lagrangian (λ-sweep) solution of Shoham–Gersho up to one fractional step, and it runs in about 1 ms for 8 RUs × 66 options. An exact DP over 8 × 66 is also cheap; I would use it to quantify the hull gap as a follow-up, but the oracle comparison already shows the ceiling.

9. **What did the negative result in Exp5 teach you?**
   Optimising fidelity to the noisy matrix spends bits reproducing noise in the 0–5 dB RUs; on the signal metric that is worse than uniform at 14–27 Gbps. Using the RU's noise estimate inside Proposition 1 fixes it (4–8 dB better vs H) and makes the allocator stop using capacity once extra bits stop helping. The objective, not the algorithm, was the problem.

10. **How accurate is the predictor, and what happens if σ² is wrong?**
    |predicted − measured| ≤ 0.5 dB for CSEE across Exp5 (the BFP predictor is within 1.3 dB). Sensitivity to σ² error is *not* evaluated yet — it is the first item under future work.

11. **Is Theorem 2 your result?**
    No. It is Halko–Martinsson–Tropp's Theorem 10.5 for Gaussian sketches with an Eckart–Young triangle-inequality step for truncation. I use SRHT for speed; the bound is checked empirically (6–10 dB slack in Exp1) and the code returns ∞ for p < 2 rather than an invalid bound.

12. **Where is the compute-cost / matrix-inversion part relevant?**
    Split 6 is the cheapest split on the fronthaul but requires the RU to run the uplink PHY, including MMSE-type matrix inverses per PRB group. The benchmark shows what that costs: a 100×100 inverse fits a 500 µs slot on one CPU core, 500×500 does not. Wiring this as an RU-compute constraint into ACAFS is future work.

13. **How were the runs made reproducible?**
    Fixed seeds; 30/7/20/12/5 repetitions for Exp1–5; every `results/data/*.json|csv` records generation time, Python/numpy versions, host and CPU count; console logs in `results/logs/`; the deck is generated from those files by `docs/build_slides.py`, so numbers cannot drift.

14. **What is the actual contribution, and is any of it novel?**
    Engineering and validation: a working, tested simulator; corrected baselines; an analytical rate–distortion menu that makes per-symbol allocation practical; a multi-RU allocator with proper baselines and ablations; and the finding about which structure survives modulation. The encoders adapt known techniques (BFP, HMT range finder, delay-domain truncation). I claim no algorithmic novelty.

15. **What will be different at the final evaluation?**
    Slot-level simulation mixing data and reference symbols with a mixed CSEE/RAS-BFP/BFP menu (needs a RAS-BFP predictor); joint ACAFS + allocation under one capacity with the compute constraint; σ² and rank-bias sensitivity; a BLER-based evaluation if a PUSCH chain can be added; C/SIMD timings for the encoders.

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

**Optional — notebook walk-through**

```bash
cd notebooks && jupyter nbconvert --execute --to notebook --inplace mid_evaluation_demo.ipynb
```

**Fallback if anything fails live (clearly say "previously generated outputs"):**
- Figures: `results/figures/exp1_nmse_vs_cr.png`, `exp3_acafs.png`, `exp4_snr_sweep.png`, `exp5_allocation.png`
- Tables: `results/data/exp5_allocation_summary.csv`, `results/benchmark_results.csv`
- Console logs: `results/logs/exp1.log` … `exp5.log`, `matinv_benchmark.log`
- Original (pre-fix) figures for comparison: `results/original_snapshot/figures/`

Troubleshooting encountered during this work: `ModuleNotFoundError: src` → run from the repository root (scripts insert the root on `sys.path`; the notebook must be launched from `notebooks/`). `libreoffice`/PDF is only needed to re-export the deck; `python docs/build_slides.py` regenerates the `.pptx` from the current results.
