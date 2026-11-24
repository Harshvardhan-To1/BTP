# Evidence map — BTP MSE report (Fronthaul Load Management)

Repository snapshot: commit `86ad6e3` ("view", 2026-09-18), branch `main`,
remote `origin/main`. All paths below are relative to the repository root.

## Classification of the work in the repository

1. **Implemented and experimentally evaluated** — the matrix-inversion
   benchmark (`matinv_bench/`): dataset generator, six classical methods,
   three learned models, benchmark harness, and saved results
   (`results/benchmark_results.csv`, `results/benchmark_summary.md`,
   `results/inference_time.png`). Rerun during this task (see below).
2. **Implemented but insufficiently evaluated / not verifiable** — the
   compression study (BFP / truncated-SVD baselines, "CSEE", "RAS-BFP",
   "ACAFS"). Experiment drivers exist (`experiments/exp1..4*.py`) and saved
   figures exist (`results/figures/exp*.png/pdf`), but every driver imports a
   `src/` package (`src.channel.tdl_a`, `src.encoder.*`, `src.metrics.*`)
   that is **absent from the repository and from git history**. The numbers
   in `docs/mid_evaluation_report.md` therefore cannot be rerun or checked.
   `test.md` (sec. 2.5) itself concedes: "The compression code imported a
   `src/` package that is not in the repository, so those numbers are quoted,
   not re-run." Reported in the MSE report only as an earlier exploratory
   phase with this limitation stated; its specific NMSE/CR/timing numbers are
   NOT reported as findings.
3. **Proposed / planned only** — the fronthaul capacity-allocation controller
   described in `test.md` sections 3–7 (deadline-feasible rate r*, quantile
   forecasts, KKT/newsvendor allocation, 200-run simulation study). **No
   simulator code, configuration, or result file for it exists anywhere in
   the repository or git history**, despite test.md's claim that "every
   number here comes from files in the repository". All of its quantitative
   results (violation-ratio tables, ablations, calibration results) are
   unsupported and are excluded from the report. The design is mentioned only
   as the planned next phase, without its claimed numbers.

## Documentation-vs-evidence discrepancies found

| # | Discrepancy | Resolution in report |
|---|---|---|
| D1 | `README.md`/`REPORT.md` headline tables (e.g. LU dim-500 median 4.2 ms, getri dim-100 0.13 ms) do **not** match the committed `results/benchmark_results.csv` (LU-scipy dim-500 median 56.3 ms; getri dim-100 median 0.174 ms), and omit InverseNet-Ultra which is in the CSV and `models/`. **Resolved by the verification rerun:** the rerun's timings closely match the README/REPORT tables, while the committed CSV was produced under thread oversubscription (its own header records 6 torch threads on a 4-core host), inflating LAPACK-path medians/tails. Accuracy metrics are identical across all three sources. Two residual README/REPORT errors: NS rel err quoted as "~5e-4 at dims 10/100" (actual dim-10 value 4.0e-2), and GJ dim-500 187.5 ms (actual 150-160 ms). | Report quotes the rerun (fully documented host) as primary timing source; contention sensitivity reported as finding F5; README/REPORT-specific numbers not used directly. See `validation/comparison.md`. |
| D2 | `matinv_bench/inversenet.py` InverseNet-Ultra docstring claims "~1e-7 relative error" and "outperforming classical LU decomposition in inference latency". Actual CSV: rel err 1.4e-6 (dims 100/500) and 1.7e-1 (dim 10, i.e. failure); median latency slower than `numpy.linalg.inv` at every dim. | Report states measured values only; no "outperforms LU" claim. |
| D3 | `docs/mid_evaluation_report.md` claims Theorems 1–5, `src/` modules, TDL-A simulator all "Done", plus a committee sign-off. `src/` is absent; theorems/proofs are nowhere in the repo. | Treated as aspirational documentation; not used as evidence. |
| D4 | `docs` single-slot table (CSEE K=300 → CR 12.7×) vs saved figure `exp1_nmse_vs_cr.png` (CSEE sweep K=10..60, CR up to ~155×): parameter ranges differ; underlying data absent. | Compression numbers excluded from findings. |
| D5 | `test.md` matrix-inversion table matches the committed CSV (medians), confirming the CSV is the authoritative record. | CSV used as authoritative saved evidence. |

## Claim-to-evidence table (report Section 4 unless noted)

| Claim / number in report | Source (file · code) | Conditions | Evidence status |
|---|---|---|---|
| Dataset: 1000 samples/dim, A = G/√n + 2I, dims {10,100,500}, float64 inverses stored float32, 80/20 split, seeded (seed=0+n) | `matinv_bench/generate_dataset.py` (generate_pairs, main), `train_inversenet.py` (TRAIN_FRACTION=0.8) | seeds fixed → dataset exactly reproducible | Rerun during this task (regenerated bit-identical by seed) |
| Six classical methods as described (LU lu_factor/lu_solve, getri via numpy.linalg.inv, Gauss-Jordan with partial pivoting, QR, SVD, Newton–Schulz to 1e-6) | `matinv_bench/methods.py` | float32 inputs | Rerun (code inspected line-by-line) |
| InverseNet-MLP: 3-layer MLP (hidden 512/1024), dims 10/100 only; dim 500 infeasible (>2×10⁹ params in in/out layers) | `matinv_bench/inversenet.py` InverseNetMLP, build_model | 2·(500²·hidden) ≥ 2B for any useful hidden | Recalculated from architecture; parameter-count arithmetic checked |
| InverseNet-NS: 8-step unrolled Newton–Schulz, 17 learned scalars (α, β₁..₈, γ₁..₈), dimension-independent | `matinv_bench/inversenet.py` InverseNetNS | — | Rerun |
| InverseNet-Ultra: 6–8 step unrolled iteration + 4-feature hypernetwork (~100 params) for the initial guess; benchmarked through a NumPy/BLAS inference path (not torch) | `matinv_bench/inversenet.py` InverseNetUltra, FastBLASInferenceEngine; `benchmark.py` L106-114 | timing not directly comparable to torch-path models; caveat stated in report | Rerun |
| Timing protocol: per-matrix (batch 1), 5 warmup calls, 200 held-out matrices/dim, CPU | `matinv_bench/benchmark.py` (WARMUP, bench_callable) | — | Rerun |
| Main results table (median ms + rel err per method/dim) | primary: rerun CSV `report_mse/validation/results_rerun/benchmark_results.csv` (4 vCPU, this task, lightly loaded); archived: `results/benchmark_results.csv` (contended host) | 200 samples; medians | Rerun quoted; accuracy identical to archived run to >=5 sig. figs (see validation/comparison.md) |
| LAPACK LU routes (getri / scipy-LU) fastest accurate methods at every dim; QR ~2x, SVD 6-9x, GJ 26x slower at n=500 | same CSVs | medians, rerun | Rerun; ratios recalculated from raw CSV |
| MLP held-out rel err 0.36 (dim 10) / 0.52 (dim 100) → unusable | rerun CSV (dim-100 MLP retrained from seeded recipe as checkpoint was gitignored); matches committed CSV to 6 sig. figs | — | Rerun (dim-10 exact; dim-100 via seeded retraining, documented) |
| NS-learned rel err 4.0e-2 (10) / 4.0e-4 (100) / 7.3e-3 (500) | rerun CSV; identical to committed CSV | fixed 8 steps | Rerun (accuracy matches saved exactly) |
| Ultra rel err 1.7e-1 (10) / 1.4e-6 (100) / 1.4e-6 (500); ~1.6x slower than getri at median (n=100/500) | rerun CSV; accuracy matches committed | NumPy-path timing caveat stated | Rerun |
| Latency-predictability finding (F5): fixed-step methods p95/median <= 1.1 in both runs; getri flat when quiet (1.04) but median 3x under oversubscription; scipy-LU/QR bimodal even when quiet (scipy-LU n=500: median 4.2 ms, p95 110 ms) | both CSVs, p95 columns | shared-CPU caveat stated | Rerun + saved; ratios recalculated |
| Slot-budget interpretation: 0.5 ms slot at 30 kHz SCS; n=100 inversion ~0.13 ms median fits, n=500 ~5.7 ms (3x under contention) does not | 3GPP numerology (external, cited); rerun + committed timings | order-of-magnitude, per-matrix, Python/CPU caveat | Recalculated from rerun + saved values |
| Fronthaul raw-rate motivation (multi-Gb/s per cell for 7-2x split) | external literature (Larsen et al. 2019; Polese et al. 2023) | cited, not measured | Bibliographically verified (web) 2026-09-24 |
| Figures 1–2 in report | generated from `report_mse/validation/results_rerun/benchmark_results.csv` by `report_mse/make_figures.py` | medians | Recalculated from rerun raw results |

## Verification performed during this task (Phase B)

- Full pipeline rerun on this VM (4 vCPU x86-64, Ubuntu 24.04, Python 3.12,
  torch CPU): dataset regeneration (seeded, dims 10/100/500), retraining of
  the gitignored dim-100 MLP checkpoint with the committed recipe
  (`train_inversenet.py`, torch.manual_seed(0)), benchmark rerun with
  `--out-dir report_mse/validation/results_rerun`. Original `results/` left
  untouched.
- Rerun outputs, commands, environment and comparison: see
  `report_mse/validation/` and `report_mse/README_build.md`.
- Accuracy metrics: rerun vs committed CSV agreement recorded in
  `report_mse/validation/comparison.md`. Timings differ in absolute value
  across hosts (expected); qualitative ranking statements used in the report
  were checked against both runs.

## References verified (Phase C, web, 2026-09-24)

1. Larsen, Checko, Christiansen, "A Survey of the Functional Splits Proposed
   for 5G Mobile Crosshaul Networks," IEEE COMST 21(1):146–172, 2019.
   DOI 10.1109/COMST.2018.2868805. (peer-reviewed)
2. Polese, Bonati, D'Oro, Basagni, Melodia, "Understanding O-RAN…," IEEE
   COMST 25(2):1376–1411, 2023. DOI 10.1109/COMST.2023.3239220. (peer-reviewed)
3. Wu, Yin, Wang, Dick, Cavallaro, Studer, "Large-Scale MIMO Detection for
   3GPP LTE: Algorithms and FPGA Implementations," IEEE JSTSP 8(5):916–929,
   2014. DOI 10.1109/JSTSP.2014.2313021. (peer-reviewed)
4. Gregor, LeCun, "Learning Fast Approximations of Sparse Coding," ICML 2010,
   pp. 399–406. (peer-reviewed proceedings)
5. Monga, Li, Eldar, "Algorithm Unrolling…," IEEE Signal Processing Magazine
   38(2):18–44, 2021. DOI 10.1109/MSP.2020.3016905. (peer-reviewed)
6. Schulz, "Iterative Berechnung der reziproken Matrix," ZAMM 13(1):57–59,
   1933. DOI 10.1002/zamm.19330130111. (archival)
7. O-RAN WG4 Control, User and Synchronization Plane Specification
   (O-RAN.WG4.CUS.0) — cited as the standard defining the open fronthaul
   7-2x split and BFP IQ compression. (standard)

## Unresolved issues (kept out of the report body)

- Approved project title, official project number, and official
  specialization were not among the supplied materials; the title page uses a
  provisional title (flagged in `submission_checklist.md`).
- README/REPORT headline tables remain inconsistent with the committed CSV
  (D1, resolved as a host-contention difference by the rerun); two specific
  README/REPORT figures (NS dim-10 error, GJ dim-500 time) remain wrong or
  stale in the repository docs; flagged here, not silently fixed.
- Compression-phase (`src/`) source restoration and the allocation-controller
  implementation are recorded as future work, matching the evidence.
