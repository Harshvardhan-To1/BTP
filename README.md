# Fronthaul Load Management in 5G C-RAN / O-RAN — B.Tech. Project

A pure-Python (numpy/scipy) simulator for the uplink fronthaul between radio
units (RUs) and a distributed unit (DU). The project has three parts, and two
of them are linear algebra:

* **A. Compression by matrix decomposition.** The 64 × 1200 received matrix
  has structure (about 23 propagation paths → low rank, sparse in the delay
  domain). Each encoder decomposes it, keeps the important part and quantises
  it with O-RAN block floating point: truncated SVD, a randomised SVD
  (RAS-BFP), and a delay-domain / IFFT truncation (CSEE). A rank-adaptive
  controller (ACAFS) decides how many spatial streams to send.
* **B. Cost of matrix inversion** (`matinv_bench/`). The receiver inverts a
  matrix per resource-block group every slot; where that can run decides
  which functional split is possible. Classical methods (LU, QR, SVD,
  Gauss–Jordan, Newton–Schulz) are timed against three neural "InverseNet"
  models that try to learn the inverse.
* **C. Sharing one link.** A capacity-constrained allocator gives each RU a
  compression setting so that the total rate fits the link, using a formula
  for the error instead of trial encoding.

Everything is evaluated on 3GPP TR 38.901 TDL-A channels in simulation.

Status labels used throughout the docs and slides:
**[repo]** present in the original repository · **[new]** implemented and
validated in this change set · **[prelim]** preliminary · **[future]** not done.

## What the project does

| Layer | Method | Role | Status |
|---|---|---|---|
| Channel | TR 38.901 TDL-A, M=64 antennas, N=1200 subcarriers, exponential antenna correlation; *data* symbols (random QPSK) vs *reference* symbols (known sequence removed) | workload | [new] (scripts existed, code did not) |
| Compression | O-RAN block floating point (BFP) | baseline | [new] |
| Compression | Truncated SVD + BFP (economy SVD) | strong baseline | [new] |
| Compression | **CSEE** — delay-domain top-K + BFP, with an analytical rate-distortion predictor (Prop. 1) | proposed | [new] |
| Compression | **RAS-BFP** — SRHT/Gaussian sketch + QR + small SVD + BFP (randomised low-rank), Theorem-2 reference bound | proposed | [new] |
| Split | **ACAFS** — numerical rank -> beam-space streams / antenna-space / split 6, with a corrected bandwidth model | proposed | [new] |
| Load management | **Greedy multiple-choice-knapsack allocator**: per-cell operating point under a shared link capacity, sum / min-max / noise-aware objectives; uniform static baselines; oracle ablation | proposed | [new] |
| Compute | LU / QR / SVD / Gauss-Jordan / Newton-Schulz vs InverseNet-MLP / -NS / -Ultra timing and accuracy | side benchmark | [repo], re-run and bug-fixed |

Key findings (all from simulation, details in `docs/mid_evaluation_report.md`):

* Delay-domain compression (CSEE) only works on reference symbols
  (−17 to −21 dB at 6–78x CR at 20 dB SNR); on data-bearing symbols it fails
  (−0.3 to −4 dB) because per-subcarrier modulation whitens the delay domain.
  Spatial low rank survives modulation, so SVD / RAS-BFP work on both.
* RAS-BFP encodes ~5x faster than the economy SVD at M=64 (2.6 vs 12.6 ms
  in numpy) for 1–4 dB more distortion at the same payload.
* NMSE measured against the noisy transported matrix saturates at −SNR for any
  truncating encoder; against the noiseless channel the same encoders act as
  denoisers at low SNR. Both are reported.
* The Prop.-1 predictor is within 0.1–0.5 dB of the measured NMSE, so a
  greedy allocator driven only by predictions matches an oracle that encodes
  every candidate; it beats uniform static allocation by up to 11 dB at equal
  capacity, and a noise-aware objective improves signal distortion by a
  further 3–6 dB while releasing unused capacity.
* Matrix inversion: LAPACK LU is fastest at every size (0.14 ms for 100×100,
  5.9 ms for 500×500 on one CPU core). The learned inverters (unrolled
  Newton–Schulz, 17 parameters; InverseNet-Ultra) generalise across sizes and
  reach 4e-4 / 1e-6 relative error at n=100, but never beat LU — a clear
  negative result for "learning the inverse" on well-conditioned matrices.

## Repository layout

    src/
      channel/tdl_a.py        TDL-A channel, received signal, rank estimators
      encoder/bfp.py          O-RAN BFP + quantisation-noise predictor
      encoder/svd_encoder.py  truncated SVD baseline
      encoder/csee.py         CSEE + Prop. 1 predictor (pointwise and whole-menu)
      encoder/ras_bfp.py      RAS-BFP + Thm. 2 reference bound
      split/acafs.py          ACAFS controller + split bandwidth model
      control/allocator.py    capacity-constrained allocation (greedy / uniform)
      metrics/nmse.py         NMSE, effective SNR, bit accounting
    experiments/exp1..exp5    reproducible experiments -> results/figures, results/data
    tests/                    pytest suite (42 tests)
    matinv_bench/             matrix-inversion benchmark (dataset, training, timing)
    notebooks/mid_evaluation_demo.ipynb   executed demo notebook
    results/figures/          current figures        results/data/  raw metrics (json/csv)
    results/logs/             run logs               results/original_snapshot/  figures/tables as found in the repo
    docs/                     audit, problem formulation, research review, change summary,
                              mid-evaluation report, presentation (.pptx) and preparation notes

## Setup

    python3 -m venv .venv && . .venv/bin/activate      # or use --user installs
    pip install -r requirements.txt                     # numpy scipy pandas matplotlib tqdm pytest
    pip install torch --index-url https://download.pytorch.org/whl/cpu   # only for matinv_bench

Python 3.10+; no GPU; everything below runs on a 4-core laptop in a few
minutes. `python-pptx` and `nbconvert` are only needed to rebuild the slides /
notebook.

## Minimal demo (≈1 minute)

    python -m pytest tests -q                              # 42 tests
    python experiments/exp1_nmse_vs_cr.py                  # ~10 s
    python experiments/exp5_fronthaul_allocation.py        # ~8 s, 8 cells x 5 seeds
    jupyter nbconvert --to notebook --execute notebooks/mid_evaluation_demo.ipynb --inplace

Full figure regeneration:

    for e in 1 2 3 4 5; do python experiments/exp${e}_*.py; done

Each script writes `results/figures/exp<i>_*.{png,pdf}` and a raw-metrics
file `results/data/exp<i>_*.json|csv` with configuration, host and timestamp.

## Matrix-inversion benchmark (optional)

    python -m matinv_bench.generate_dataset --dims 10 100 --num-samples 1000
    python -m matinv_bench.generate_dataset --dims 500 --num-samples 100   # 1000 needs ~2 GB
    python -m matinv_bench.train_inversenet --dims 10 100 500              # optional; checkpoints are committed
    python -m matinv_bench.benchmark --dims 10 100 500

See `REPORT.md` for method descriptions and `results/benchmark_summary.md`
for the current numbers (dim-500 rows use 20 held-out matrices).

## Evaluation procedure and metrics

* **NMSE (dB)** = 10 log10(‖Y − Ŷ‖²_F / ‖Y‖²_F). Reported against the
  transported matrix `Y` and, for reference symbols, against the noiseless `H`.
* **Compression ratio** = 2·M·N·16 / bits used (16-bit I/Q reference, exact
  bit accounting including BFP exponents and support / rank headers).
* **Encode time** = median of repeated numpy calls (relative comparison only).
* **Allocation**: utilisation = used / capacity, dropped cells, decision time,
  |predicted − measured| NMSE; 5 seeds, mean ± std.
* Learned models (`matinv_bench`) are evaluated on the held-out last 20 % of
  each dataset; no traffic-dependent ML is used in the fronthaul simulator
  because the analytical predictors are exact enough (see docs).

## Documentation

* `docs/audit.md` — what the repository contained, verified problems, ranking of fixes
* `docs/problem_formulation.md` — system model, decision variables, constraints, propositions
* `docs/research_review.md` — verified literature review with source links
* `docs/change_summary.md` — every modification, why, files, validation
* `docs/mid_evaluation_report.md` — the mid-evaluation report (rewritten)
* `docs/mid_evaluation.pptx` / `.pdf` — the presentation (15 main + 2 reference + 5 backup slides, speaker notes on every slide), regenerated from `results/` by `python docs/build_slides.py`; `docs/presentation_prep.md` — 60–90 s intro, slide guide, 17 Q&A, demo script with expected outputs
* `docs/mid_evaluation_slides.md|.html` — the **superseded** decks found in the repo (kept for the record; their claims are not endorsed)

## Troubleshooting (issues actually hit)

* `ModuleNotFoundError: src` — run scripts from the repository root, or the
  scripts' own `sys.path` insertion handles it; the notebook must be started
  from `notebooks/`.
* `python3 -m venv` fails with "ensurepip is not available" on minimal
  Ubuntu — `apt install python3.12-venv`, or `pip install --user`.
* `matinv_bench.benchmark` needs `data/matrices_dim*.npz`; generate them
  first (the directory is gitignored). Dim 500 with 1000 samples is ~2 GB.
* Timing numbers vary with BLAS thread count; set `OMP_NUM_THREADS=4` for
  comparable runs.
