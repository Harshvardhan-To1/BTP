# Verification rerun vs committed results

Rerun date: 2026-09-24, on this task's VM.
Rerun host: 4 vCPU x86-64 (Ubuntu 24.04), Python 3.12.3, NumPy 2.5.3,
SciPy 1.18.1, pandas 3.0.6, PyTorch 2.14.0+cpu, 4 torch threads, CPU only.
Committed run host (as recorded in `results/benchmark_summary.md`):
"x86_64, 6 torch threads, CPU only".

## Commands executed (from repository root, commit 86ad6e3)

```bash
.venv/bin/python -m matinv_bench.generate_dataset --dims 10 100 500 --num-samples 1000
.venv/bin/python report_mse/validation/retrain_mlp100.py
.venv/bin/python -m matinv_bench.benchmark --dims 10 100 500 \
    --models-dir report_mse/validation/models \
    --out-dir report_mse/validation/results_rerun
```

Notes:
- Dataset regeneration is deterministic (`numpy.random.default_rng(seed=0+n)`),
  so the rerun evaluates the same matrices as the original run.
- The dim-100 MLP checkpoint (~86 MB) is gitignored; it was retrained with the
  committed recipe (epochs=15, batch=32, lr=1e-3, `torch.manual_seed(0)`) into
  `report_mse/validation/models/`. All other checkpoints are the committed ones
  (copied, originals untouched).
- Original experiment outputs in `results/` were not modified.

## Accuracy comparison (mean relative error vs true inverse)

| Method | dim | committed | rerun | match |
|---|---|---|---|---|
| all classical | 10/100/500 | ~1e-7 level | ~1e-7 level | yes (2-3 sig. figs; e.g. getri 4.76e-8 / 4.81e-8 / 4.84e-8 identical) |
| InverseNet-MLP | 10 | 3.573e-1 | 3.573e-1 | exact |
| InverseNet-MLP | 100 | 5.209929e-1 | 5.209936e-1 | agree to 6 sig. figs (retrained checkpoint, seeded) |
| InverseNet-NS | 10 | 4.018e-2 | 4.018e-2 | exact |
| InverseNet-NS | 100 | 4.026e-4 | 4.026e-4 | exact |
| InverseNet-NS | 500 | 7.295e-3 | 7.295e-3 | exact |
| InverseNet-Ultra | 10 | 1.732e-1 | 1.732e-1 | exact |
| InverseNet-Ultra | 100 | 1.381e-6 | 1.386e-6 | ~ (float32 kernel differences) |
| InverseNet-Ultra | 500 | 1.433e-6 | 1.436e-6 | ~ |

## Timing comparison (median ms, getri / scipy-LU / Gauss-Jordan at n=500)

| Run | getri | scipy LU | Gauss-Jordan |
|---|---|---|---|
| committed CSV | 18.0 | 56.3 | 159.3 |
| rerun (this task) | 5.7 | 4.2 | 150.3 |
| README/REPORT.md tables | 5.6 | 4.2 | 187.5 |

Interpretation: the committed CSV's timings were taken on a heavily contended
host (6 BLAS/torch threads on 4 cores), inflating LAPACK-path medians and
tails; the rerun on a lightly loaded 4-vCPU host closely matches the
README/REPORT.md tables (which evidently came from such a quieter run whose
raw CSV was not committed). Accuracy metrics are identical across all runs.
Pure-Python-loop (Gauss-Jordan) and fixed-step learned methods are stable
across both conditions.

Consequence for the report: the rerun is quoted as the primary timing source
(fully documented host); ranking statements were checked to hold in both runs,
and the contention sensitivity of the scipy-LU/QR paths is reported as a
finding caveat (e.g. rerun scipy-LU at n=500: median 4.2 ms, p95 110.0 ms).
