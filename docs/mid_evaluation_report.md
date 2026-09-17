# BTP Mid-Term Evaluation Report

**Project:** Fronthaul Load Management in 5G C-RAN / O-RAN — compression, split selection and capacity-constrained allocation
**Stage:** mid-term evaluation · **Date:** September 2026
**Scope of evidence:** Python/numpy simulation on 3GPP TR 38.901 TDL-A channels. No hardware, no real traces.

Status labels: **[repo]** existed in the repository before this iteration · **[new]** implemented and validated in this iteration · **[prelim]** preliminary · **[future]** planned.

---

## 1. Summary

Massive-MIMO uplink over an O-RAN split-7.2x fronthaul carries 2·M·N·16 bits per OFDM symbol per RU — 34.4 Gbps for M = 64 antennas and N = 1200 subcarriers — and several RUs share one link. The project builds and evaluates the chain that manages that load:

1. **Compression encoders** at the RU: O-RAN block floating point (BFP) and truncated SVD as baselines; **CSEE** (delay-domain top-K + BFP) and **RAS-BFP** (randomised sketch + QR + BFP) as proposed low-complexity encoders, each with an analytical rate-distortion predictor.
2. **ACAFS**, a rank-adaptive stream / functional-split selector with a corrected fronthaul bandwidth model.
3. A **capacity-constrained multi-cell allocator** that assigns each RU an encoder operating point so that the sum rate fits the shared link while minimising predicted distortion (**[new]**; this is the load-management decision itself).
4. A **matrix-inversion compute benchmark** (**[repo]**) that quantifies the DU/RU processing cost a split decision moves.

State at the start of this iteration: the repository contained the experiment scripts, figures and documents for items 1-2, but **not the source package they import** (`src/`), so nothing could be run or reproduced; several documented results were physically inconsistent (see `docs/audit.md`). This iteration reconstructed the simulator, corrected the models, added the allocator, added 42 tests, and regenerated every figure from code that is now in the repository.

## 2. System model

Received matrix at RU k for one OFDM symbol: `Y_k = H_k diag(x_k) + W_k ∈ C^{M×N}`, M = 64, N = 1200 (15 kHz SCS, 18 MHz), TDL-A (23 taps, 100 ns RMS delay spread), exponential antenna correlation ρ = 0.7, `E|H|² = 1`, `W ~ CN(0, 10^(-SNR/10))`.
Two symbol types: **data** (random QPSK per subcarrier) and **reference** (known sequence de-rotated by the RU, leaving `H_k + W'_k`).
Raw rate: `R_raw = 2·M·N·16` bits/symbol = 2.46 Mbit/symbol = 34.4 Gbps per RU (14 symbols per 1 ms slot).
Metrics: NMSE (dB) vs the transported `Y` and vs the noiseless `H`; compression ratio vs 16-bit I/Q with exact bit accounting; numpy encode time (relative only). Full formulation: `docs/problem_formulation.md`.

## 3. Methods

| Method | Payload | Cost | Predictor / bound | Status |
|---|---|---|---|---|
| BFP (O-RAN) | 2·b·M·N + 4·M·N/12 | O(MN) | quantisation-noise model | [new] baseline |
| Truncated SVD | BFP(U_r Σ_r), BFP(V_r) | O(MN·min(M,N)), economy SVD | Eckart-Young floor | [new] baseline |
| **CSEE** | BFP(Y_d[:,S]) + K·log₂N support bits | O(MN log N) | **Prop. 1**: NMSE = (tail + quant)/‖Y_d‖²; tail exact, quant estimate or worst-case bound | [new] |
| **RAS-BFP** | BFP(L_r), BFP(Q_r), same shape as SVD | O(MN·(r+p)) | **Thm. 2** (HMT 2011 Thm 10.5, Gaussian): E‖Y−Ŷ‖² ≤ (4 + 2r/(p−1))·Σ_{i>r}σ_i² | [new] |
| **ACAFS** | streams: r (beam-space), M (antenna-space), or transport blocks (split 6) | O(M²N) rank estimate | **Prop. 5**: expected saving under uniform rank | [new] |
| **Allocator** | one (K, b) per RU | O(C·|menu|) greedy on convex hulls | uses Prop. 1 (optionally noise-aware) | [new] |

## 4. Results (all measured in this iteration; raw data in `results/data/`)

### 4.1 Rate-distortion at 20 dB SNR, 30 realisations (Exp1)

| Method (operating point) | CR | NMSE vs Y, data symbols | NMSE vs Y, reference symbols |
|---|---:|---:|---:|
| BFP b = 8 | 2.0x | −46.4 dB | −46.4 dB |
| BFP b = 4 | 3.8x | −21.1 dB | −21.1 dB |
| SVD r = 12, b = 10 | 8.0x | −20.7 dB | −20.7 dB |
| RAS-BFP r = 12, b = 10 | 8.0x | −16.7 dB | −16.7 dB |
| CSEE K = 120, b = 10 | 15.6x | **−1.3 dB** | −19.6 dB |
| CSEE K = 40, b = 10 | 46.7x | −0.5 dB | −18.1 dB |

Takeaways: (i) delay-domain compression requires delay sparsity, which per-subcarrier modulation destroys; CSEE is a **reference-symbol / CSI compressor**, not a general I/Q compressor. (ii) Spatial low rank is invariant to modulation (`diag(x)` is invertible), so SVD / RAS-BFP work on both. (iii) At 20 dB all truncating encoders sit near the −20 dB noise floor of the vs-`Y` metric. RAS-BFP's Theorem-2 reference bound lies 6-10 dB above the measured curve (valid, loose); CSEE's worst-case Prop.-1 bound coincides with the measurement because the exact tail term dominates.

### 4.2 Encode time vs M, N = 1200, numpy medians of 7 (Exp2)

| M | BFP | SVD (economy) | CSEE (K=120) | RAS-BFP (r=12) |
|---:|---:|---:|---:|---:|
| 16 | 0.15 ms | 1.8 ms | 0.16 ms | 1.4 ms |
| 64 | 0.66 ms | 12.6 ms | 0.58 ms | 2.6 ms |
| 128 | 1.6 ms | 39.6 ms | 1.2 ms | 5.7 ms |

RAS-BFP is ~5-7x faster than the SVD baseline at M ≥ 64 (the previously documented ~100x gap came from timing a full N×N SVD). These are Python numbers; only the ordering and scaling are claimed.

### 4.3 ACAFS saving vs SNR, 20 realisations (Exp3)

Mean estimated rank (99 % energy) falls from 63 at −5 dB to 8 at 30 dB. Beam-space-only saving vs fixed antenna-space: 0 % below 15 dB, 33 % at 16 dB, 83-84 % at ≥ 20 dB. With split 6 allowed the saving is 59-84 % across the whole range because split 6 carries transport blocks (≈ 20x cheaper in the model) — that option is gated by RU compute, which is where the matrix-inversion benchmark enters. The 1/8-subcarrier rank estimator saves ~30 % of the estimation time but under-estimates rank by up to 10 at 10-17 dB SNR; the τ_low stream floor is the guard against that. Prop. 5 (uniform rank): 38 % beam-space, 77 % with split 6 — a model prediction, not a bound.

### 4.4 NMSE vs SNR at CR ≈ 8x, 12 realisations (Exp4)

vs transported `Y`: SVD / CSEE / RAS-BFP track −SNR (they discard noise-only components, which counts as error). vs noiseless `H`: at 0 dB, CSEE K=120 gives −9.0 dB and SVD r=12 −6.3 dB where the raw noisy matrix is at 0 dB — the encoders denoise; at 30 dB SVD −34 dB, CSEE −27 dB, RAS-BFP −26 dB, BFP b=4 −21 dB. CSEE on data symbols: −0.7 to −1.4 dB at every SNR.

### 4.5 Multi-cell allocation, 8 RUs with SNR {0,5,10,15,20,25,30,20} dB, 5 seeds (Exp5) **[new]**

Menu: 11 K-values × 6 bit widths = 66 CSEE points; capacity as a fraction of the 275 Gbps raw load. Per-cell NMSE averaged in dB (mean ± std over seeds):

| Capacity | uniform-CSEE | uniform-BFP | greedy-sum (pred.) | oracle (measured) | greedy-clean (noise-aware) |
|---|---|---|---|---|---|
| 55 Gbps (0.2) | −17.2 / −16.1 dB | −12.6 / −8.9 | **−23.4** / −16.9 | −23.4 / −16.9 | −16.3 / **−23.5** (63 % util.) |
| 27.5 Gbps (0.1) | −15.6 / −17.8 | −2.0 (3 dropped) | **−18.1** / −17.3 | −17.6 / −16.9 | −16.2 / **−23.5** |
| 13.8 Gbps (0.05) | −14.6 / −19.3 (78 % util.) | −0.9 (6 dropped) | **−15.6** / −18.5 | −15.6 / −18.5 | −15.6 / **−23.0** |
| 5.5 Gbps (0.02) | −14.0 / −19.5 | −0.5 (7 dropped) | −13.3 / −17.6 | −13.3 / −17.6 | **−14.5** / **−21.4** |
| 1.4 Gbps (0.005) | −9.4 (1 dropped) | all dropped | −10.0 (1 dropped) | −10.0 | −9.9 (1 dropped) |

(cells: NMSE vs `Y` / NMSE vs `H`; std over seeds 0.1-0.8 dB, full table in `results/data/exp5_allocation_summary.csv`).

Findings: (i) prediction-driven greedy equals the oracle at every capacity — the Prop.-1 predictor is within 0.5 dB, so no encoding is needed to decide; (ii) it beats uniform allocation by 0.6-11 dB on its own objective with ~99 % utilisation; (iii) **negative result turned into a design change**: on the signal metric, minimising NMSE vs `Y` wastes bits reproducing noise in low-SNR cells and is *worse* than uniform at 0.02-0.05; the noise-aware objective (RU noise estimate fed into Prop. 1) fixes this, gains 3-6 dB vs `H`, and stops consuming capacity once extra bits stop helping (25-63 % utilisation at ≥ 55 Gbps). Decision time: ~1 ms allocation + ~27 ms menu prediction for 8 cells in Python.

### 4.6 Matrix-inversion compute benchmark **[repo, re-run]**

LAPACK LU is fastest and float32-exact at every size (0.006 / 0.14 / 5.9 ms at n = 10 / 100 / 500). Learned unrolled Newton-Schulz (InverseNet-NS, 17 parameters) generalises (4e-4 relative error at n = 100) but is slower; the direct-regression MLP fails (0.36-0.52 error). InverseNet-Ultra reaches 1e-6 error, matching classic Newton-Schulz time, never beating LU medians. A ReLU/GELU mismatch in its NumPy engine was fixed (`tests/test_matinv.py`). Relevance: a 100×100 inversion per PRB group fits a 500 µs slot on a CPU core; 500×500 does not — this bounds what RU compute (split 6) or DU compute can absorb.

## 5. What was in the repository vs what was done now

| Item | Before | Now |
|---|---|---|
| `src/` simulator | absent | reconstructed, tested |
| Exp1-4 | scripts referencing missing code; figures irreproducible | rerun; baseline (full SVD), estimator (fake fast rank), split model (inverted), metric interpretation fixed |
| Allocation under shared capacity | absent | Exp5 with baselines, seeds, oracle and objective ablations |
| Tests | none | 42 |
| Compute benchmark | complete | engine bug fixed, docstring corrected, re-run |
| Documents | claims not backed by code | rewritten to match code and data |

## 6. Limitations

* Single-symbol simulation; no MAC scheduler, HARQ, latency, jitter, or multi-slot dynamics.
* CSEE applies to reference symbols only; the allocator experiment therefore covers reference-symbol traffic (or BFP-only menus for data). A RAS-BFP predictor for the menu is future work.
* Timings are Python/numpy; no hardware evidence.
* The Theorem-2 bound is proven for Gaussian sketches; the SRHT default is checked empirically.
* Split-6 rate model (r·N·η with η = 6 bit/RE) is coarse.
* Noise variance is assumed known exactly at the RU in the noise-aware ablation.

## 7. Plan to the final evaluation

1. Slot-level simulation mixing data and reference symbols; allocator running per slot with a mixed CSEE / RAS-BFP / BFP menu (needs a RAS-BFP predictor).
2. Joint split + compression decision: ACAFS choosing beam-space streams *and* the allocator choosing bits under one capacity, with the compute benchmark as the RU-compute constraint.
3. Sensitivity to noise-variance estimation error and to rank-estimation bias.
4. If time permits: a learned predictor only where no analytical one exists, evaluated against the analytical one on held-out channels; C/SIMD timing of BFP, CSEE and RAS-BFP.

## 8. Deliverables

| Asset | Path |
|---|---|
| Simulator | `src/` |
| Experiments and raw metrics | `experiments/`, `results/data/`, `results/logs/` |
| Figures | `results/figures/exp{1..5}_*.png|pdf` |
| Tests | `tests/` |
| Demo notebook (executed) | `notebooks/mid_evaluation_demo.ipynb` |
| Audit, formulation, change log | `docs/audit.md`, `docs/problem_formulation.md`, `docs/change_summary.md` |
| Literature review | `docs/research_review.md` |
| Presentation and speaker preparation | `docs/mid_evaluation.pptx`, `docs/presentation_prep.md` |
| Original figures/tables as found | `results/original_snapshot/` |
