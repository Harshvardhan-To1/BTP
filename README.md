# Matrix Inversion Benchmark

Dataset generation and inference-time benchmarking of matrix inversion
techniques — classical linear algebra (LU, QR, SVD, Gauss-Jordan,
Newton-Schulz) versus neural **InverseNet** models — on matrices of
dimension **10, 100 and 500**.

## What's here

| Path | Purpose |
|---|---|
| `matinv_bench/generate_dataset.py` | Generates 1000 (matrix, inverse) pairs per dimension |
| `matinv_bench/inversenet.py` | InverseNet architectures (MLP and learned Newton-Schulz) |
| `matinv_bench/train_inversenet.py` | Trains the InverseNet models |
| `matinv_bench/methods.py` | Classical inversion techniques |
| `matinv_bench/benchmark.py` | Times every method, writes CSV / markdown / plot |
| `results/` | Benchmark outputs (`benchmark_results.csv`, `benchmark_summary.md`, `inference_time.png`) |
| `models/` | Trained InverseNet checkpoints (the 86 MB dim-100 MLP is gitignored; retrain to reproduce) |

## Dataset

For each dimension `n ∈ {10, 100, 500}` we draw 1000 samples

```
A = G / sqrt(n) + 2·I,    G_ij ~ N(0, 1)
```

By the circular law the eigenvalues of `G/sqrt(n)` lie in the unit disk, so
`A`'s spectrum lives in a disk centered at 2 — every sample is safely
invertible and well conditioned. Inverses are computed in float64 and both
arrays are stored as float32 in `data/matrices_dim{n}.npz` (~2 GB for
dim 500, hence `data/` is gitignored — regenerate with one command below).
The first 80% of each file is the training split for the neural models; all
benchmarking happens on the held-out last 20%.

## Methods benchmarked

**Classical** (numpy / scipy, float32):

- **LU decomposition** — `scipy.linalg.lu_factor` + `lu_solve` against the identity
- **LAPACK getri** — `numpy.linalg.inv` (also LU-based; the tuned reference)
- **Gauss-Jordan elimination** — vectorized numpy with partial pivoting
- **QR decomposition** — `A⁻¹ = R⁻¹Qᵀ`
- **SVD** — `A⁻¹ = V S⁻¹ Uᵀ`
- **Newton-Schulz iteration** — classic `X ← X(2I − AX)` to a 1e-6 residual

**Neural (InverseNet)** (PyTorch, float32, CPU):

- **InverseNet-MLP** — flatten the matrix, regress the flattened inverse with a
  3-layer MLP. Only practical for dims 10 and 100: at dim 500 the input/output
  layers alone would need >2 billion parameters.
- **InverseNet-NS** — a *learned* Newton-Schulz network: the iteration
  `X ← X(βₖI − γₖAX)` is unrolled for 8 steps with the per-step scalars and the
  initial-guess scale learned. Parameter count is dimension-independent, so it
  scales to dim 500.

Timing is per matrix (batch size 1) with 5 warmup calls, on CPU. Accuracy is
reported as the identity residual `‖XA − I‖_F / √n` and the relative error
against the stored true inverse.

## Reproduce

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # or install torch from the CPU index
.venv/bin/python -m matinv_bench.generate_dataset --dims 10 100 500 --num-samples 1000
.venv/bin/python -m matinv_bench.train_inversenet --dims 10 100 500
.venv/bin/python -m matinv_bench.benchmark --dims 10 100 500
```

Results land in `results/`. See `results/benchmark_summary.md` for the tables
and `results/inference_time.png` for the time-vs-dimension plot.

## Headline findings (this machine: 4-core CPU, float32)

Exact tables: `results/benchmark_summary.md`. Medians are the robust statistic
here — occasional CPU contention skews a few means (e.g. LU at dim 500:
median 4.2 ms vs mean 25 ms).

- **LAPACK-backed LU** (`numpy.linalg.inv` / scipy `lu_factor`+`lu_solve`) is
  the fastest accurate method at every dimension: ~5 µs (dim 10), ~0.1 ms
  (dim 100), ~4-6 ms (dim 500), with residuals at float32 machine-precision
  level (~1e-7).
- **QR** is ~2-3× slower than LU and **SVD** ~7-10× slower at dims 100-500,
  with no accuracy benefit on these well-conditioned inputs.
- **Pure-numpy Gauss-Jordan** is fine at dim 10 (0.045 ms) but its Python-level
  pivot loop makes it the slowest classical method at dim 500 (~188 ms).
- **Classical Newton-Schulz** (iterate to 1e-6) is surprisingly competitive on
  well-conditioned matrices: ~18 ms at dim 500.
- **InverseNet-MLP** trains to low loss but generalizes poorly: held-out
  relative error is ~0.36 (dim 10) and ~0.53 (dim 100) — unusable as an
  inverse — and the architecture cannot scale to dim 500 (>2B parameters).
  Direct regression of matrix inverses is a hard learning problem.
- **InverseNet-NS** (learned 8-step Newton-Schulz) generalizes far better
  (relative error ~5e-4 at dims 10/100, ~7e-3 at dim 500) because it embeds
  the algorithmic structure, but at 115 ms per dim-500 matrix on CPU it does
  not beat LU. Being pure batched matmuls, it is the one method whose relative
  standing would improve dramatically on a GPU with batched inference.
