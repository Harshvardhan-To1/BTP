# Change summary (this change set, 2026-09-17)

Each entry: what changed, why it matters, files, how it was validated.
Status: **[new]** implemented and validated here; **[fix]** bug fix to
existing material; **[docs]** documentation; **[future]** not done.

## 1. Reconstructed the missing `src/` package  [new]

* **What.** `src/channel/tdl_a.py`, `src/encoder/{bfp,svd_encoder,csee,ras_bfp}.py`,
  `src/split/acafs.py`, `src/metrics/nmse.py`, matching every call made by
  `experiments/exp1..4` and the notebook (class names, method names, keyword
  arguments, return types).
* **Why.** Nothing in the fronthaul half of the project could run without it.
* **Validation.** All original scripts run unchanged at import level; 42
  pytest tests cover round-trips, bit accounting, bounds, edge cases; the
  notebook executes end-to-end.
* **Caveat.** This is a re-implementation from the specification in the
  scripts and docs, not a recovery of lost code. Numbers differ from the
  committed figures (see audit item 4, 7, 8) and the new ones are the ones to
  trust because they are reproducible.

## 2. Symbol model: data vs reference symbols  [new]

* **What.** `generate_received_signal(..., symbol_type="data"|"reference")`.
* **Why.** The original CSEE result is only obtainable when the transmitted
  symbols are constant/known. Real fronthaul carries modulated data on ~12 of
  14 symbols per slot.
* **Validation.** `test_csee_needs_delay_sparsity`; Exp1 panel (a)/(b); Exp4
  dashed curve. Spatial rank invariance tested (`test_channel_power_and_rank`).

## 3. Economy SVD baseline and timing fixes in Exp2  [fix]

* **What.** `SVDEncoder` uses `full_matrices=False`; O(MN) reference line in ms.
* **Why.** The committed figure showed SVD ~100x slower than it is; the
  "4-6x faster than SVD" claim depended on it.
* **Validation.** Exp2 rerun: SVD 12.6 ms, RAS-BFP 2.6 ms, CSEE 0.6 ms, BFP
  0.7 ms at M=64 (medians, numpy). `results/data/exp2_complexity.json`.

## 4. ACAFS bandwidth model corrected; real fast rank estimator  [fix]

* **What.** `SplitBandwidthModel` with antenna-space / beam-space / split-6
  rates ordered per 3GPP TR 38.801; savings vs fixed antenna-space split;
  `estimate_rank_fast` = Gram eigenvalues on a random 1/8 subset of
  subcarriers (replaces `exact + random(-1,1)`); Prop. 5 = expected saving
  under uniform rank (not called a bound).
* **Why.** The original "vs split 6" framing was inverted; the fast curve was fake.
* **Validation.** `test_split_bandwidth_ordering`, `test_acafs_rule_and_edges`,
  `test_prop5_is_the_uniform_average`; Exp3 reports rank bias and timing of the
  fast estimator (bias up to ~10 ranks at 10-17 dB, 30 % time saving).

## 5. Honest distortion metrics in Exp1/Exp4  [fix]

* **What.** Report NMSE vs transported `Y` and vs noiseless `H`; noise floor
  drawn; Exp4 default operating points changed to CR ≈ 8x (BFP b=4 as closest).
* **Why.** Truncating encoders' NMSE vs `Y` equals about −SNR; the old text
  claimed "stable across SNR" from a figure that showed the opposite.
* **Validation.** Exp4 output table in `results/logs/exp4.log`.

## 6. Capacity-constrained multi-cell allocator  [new]

* **What.** `src/control/allocator.py`: `Menu`, `build_csee_menu`,
  `build_bfp_menu`, `greedy_allocate` (sum / max objectives, convex-hull
  pruning, overload dropping), `uniform_allocate`; `CSEEEncoder.predict_menu`
  (vectorised Prop. 1, optional noise-aware form).
  `experiments/exp5_fronthaul_allocation.py`: 8 cells, 6 capacities, 5 seeds,
  policies uniform-CSEE / uniform-BFP / greedy-sum / greedy-max / greedy-clean /
  oracle; CSV of every run plus summary.
* **Why.** This is the actual "load management" decision the project title
  promises; the repo had no shared-capacity model.
* **Validation.** 9 tests (capacity respected, greedy ≥ uniform on its
  objective, low load picks best option, overload drops least-useful cells,
  zero-traffic cell, invalid inputs, units); Exp5 asserts rate accounting
  equals encoder bit count for every chosen point; greedy = oracle within
  0.5 dB (prediction error column).
* **Result that changed the design.** Minimising NMSE vs `Y` makes the
  allocator spend bits on noise in low-SNR cells (visible on the vs-`H`
  metric). The noise-aware predictor (`noise_var` argument) fixes this: 3-6 dB
  better signal NMSE and 25-63 % utilisation at high capacity because more bits
  no longer help. Reported as an objective ablation, not hidden.

## 7. `matinv_bench` fixes and re-run  [fix]

* **What.** `FastBLASInferenceEngine` now applies exact GELU (was ReLU);
  overstated `InverseNetUltra` docstring corrected; benchmark re-run on this
  host (dim 500 with 20 held-out samples due to disk).
* **Validation.** `test_ultra_engine_matches_torch_model` (rtol 1e-4);
  `results/benchmark_summary.md`, `results/logs/matinv_benchmark.log`.

## 8. Tests  [new]

`tests/test_encoders.py` (channel, BFP, SVD, RAS-BFP, CSEE, metrics),
`tests/test_control.py` (ACAFS, allocator), `tests/test_matinv.py`.
Run: `python -m pytest tests -q` (≈1 s).

## 9. Documentation and deliverables  [docs]

`README.md` rewritten; `docs/audit.md`, `docs/problem_formulation.md`,
`docs/research_review.md`, `docs/change_summary.md`, `docs/presentation_prep.md`
added; `docs/mid_evaluation_report.md` rewritten; `docs/mid_evaluation.pptx`
(22 slides: 15 main + 2 reference + 5 backup, speaker notes on every slide; after supervisor-style feedback the wording was simplified and the matrix-decomposition / matrix-inversion parts were given their own slides — slide 3 'what the project is built from', slide 7 'compression = decompose, keep, quantise', slides 13–14 on classical vs learned inversion) generated by
`docs/build_slides.py` from `results/data/*` so numbers cannot drift, with
`docs/mid_evaluation.pdf` exported via LibreOffice and inspected slide by slide
for overflow; literature entries live in `docs/slide_references.py` (29 sources from two merged search passes; the second pass surfaced the closest prior art — Aswathylakshmi & Ganti 2022, Li et al. 2019, Kanno et al. 2023 — now on slide 4 and in the review's gap statement); old
Markdown/HTML decks kept with a superseded notice; notebook rewritten and
executed.

Validation of the deck: rendered to PNG and checked visually (titles fit the
header band, no text under the takeaway boxes, reference list split over two
slides); every quoted number was cross-checked against
`results/data/exp5_allocation_summary.csv`, `results/benchmark_results.csv`
and the Exp1-4 JSON files (two earlier draft claims — "≈0.3 dB mean cost" for
the min-max objective and "1e-6 error" for InverseNet-Ultra at every size —
were corrected to the measured values).

## Not done / future work  [future]

* RAS-BFP distortion predictor for the allocator menu (needs a cheap
  quantisation-noise model for the factor matrices; Gram eigenvalues give the
  tail term already).
* Multi-symbol / slot-level simulation with a mix of data and reference
  symbols; MAC scheduler; latency and jitter.
* Hardware or C/SIMD timings; the numpy timings only support relative claims.
* Real traces or a ray-traced channel; only TDL-A is modelled.
* Learned components for the fronthaul path (e.g. a predictor for encoders
  without an analytical model, or RL over slots) — not justified yet because the
  analytical predictor is within 0.5 dB of measurement.
* Tighter oversampling analysis for the SRHT sketch (current bound is the
  Gaussian reference).
