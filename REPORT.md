# Matrix Inversion Benchmark Report

## 1. Purpose

Matrix inversion sits inside the signal processing chain of a radio access
network. MMSE equalization, zero-forcing precoding, and channel estimation all
need the inverse of a channel or covariance matrix, and they need it fresh
every scheduling slot. This project measures how long different inversion
techniques actually take per matrix, so the numbers can feed into fronthaul
load management decisions: what to compute where, and what fits inside a slot
deadline.

We compare classical linear algebra (LU, QR, SVD, Gauss-Jordan, Newton-Schulz)
against two neural "InverseNet" models on the same data.

## 2. Dataset

For each dimension n in {10, 100, 500} we generated 1000 samples of

```
A = G / sqrt(n) + 2 * I,   G_ij ~ N(0, 1)
```

This construction keeps every matrix well conditioned, so all methods get a
fair, solvable problem. Ground-truth inverses were computed in float64 and
both arrays stored in float32 (the precision real-time DSP pipelines and the
neural models use). The three sizes map loosely onto real workloads:

- n = 10: small antenna arrays, per-user MIMO detection
- n = 100: massive MIMO scale (64 to 128 antennas plus margin)
- n = 500: large aggregated or multi-cell covariance problems

The first 80% of each set trained the neural models. All timing below is on
the held-out 20% (200 matrices per dimension) that no model saw in training.

## 3. Methods

Classical (numpy/scipy, float32):

- LU decomposition: scipy lu_factor + lu_solve against the identity
- LAPACK getri: numpy.linalg.inv, also LU based, the tuned reference
- Gauss-Jordan elimination: vectorized numpy with partial pivoting
- QR decomposition: invert R, multiply by Q transpose
- SVD: invert the singular values
- Newton-Schulz iteration: multiply-only iteration run until the residual
  drops below 1e-6

Neural (PyTorch, CPU):

- InverseNet-MLP: flatten the matrix, regress the flattened inverse with a
  3-layer fully connected net. Only trained for n = 10 and n = 100. At
  n = 500 the input and output layers alone would need over 2 billion
  parameters, so this design cannot scale.
- InverseNet-NS: a learned Newton-Schulz network. The iteration is unrolled
  for a fixed 8 steps and the step coefficients are trained. The parameter
  count does not depend on matrix size, so it runs at every dimension.

Timing is per single matrix (batch size 1) with warmup, on a 4-core CPU.
Accuracy is the mean relative error against the true inverse.

## 4. Results

Median inference time per matrix, in milliseconds:

| Method | n = 10 | n = 100 | n = 500 |
|---|---:|---:|---:|
| LAPACK getri (numpy.linalg.inv) | 0.005 | 0.13 | 5.6 |
| LU decomposition (scipy) | 0.015 | 0.09 | 4.2 |
| QR decomposition | 0.014 | 0.26 | 12.2 |
| Newton-Schulz iteration | 0.037 | 0.40 | 18.2 |
| SVD | 0.021 | 1.20 | 36.6 |
| Gauss-Jordan (pure numpy) | 0.044 | 1.41 | 187.5 |
| InverseNet-MLP | 0.051 | 0.77 | n/a |
| InverseNet-NS (learned) | 0.117 | 0.36 | 117.0 |

Relative error against the true inverse:

| Method | n = 10 | n = 100 | n = 500 |
|---|---:|---:|---:|
| All classical methods | ~1e-7 | ~1e-7 | ~1e-7 |
| InverseNet-MLP | 0.36 | 0.53 | n/a |
| InverseNet-NS (learned) | 5e-4 | 4e-4 | 7e-3 |

Full tables including mean and p95 times are in `results/benchmark_summary.md`
and `results/benchmark_results.csv`. The plot `results/inference_time.png`
shows time against dimension on log scales.

## 5. Findings

1. LU-based inversion through LAPACK is the method to beat. It is the fastest
   accurate option at every size and reaches float32 machine precision.
2. QR costs about 2 to 3 times LU, SVD about 7 to 10 times, with no accuracy
   gain on well conditioned inputs. Use them only when you need their extra
   structure (rank information, numerical rescue on bad matrices).
3. Hand-rolled Gauss-Jordan is fine at n = 10 but the per-pivot Python loop
   makes it the slowest method at n = 500. Library routines win.
4. InverseNet-MLP fails as an inverse. It fits the training set but its
   held-out error (0.36 to 0.53 relative) makes the output unusable, and the
   design cannot reach n = 500 at all. Learning a direct map from matrix to
   inverse is a hard problem.
5. InverseNet-NS works much better (errors around 5e-4) because it keeps the
   Newton-Schulz algorithm structure and only learns the coefficients. It has
   a fixed, predictable cost of 8 matrix multiplies. On CPU that does not beat
   LU, but the workload is pure batched matmuls, which is exactly what GPUs
   and NPUs accelerate.

## 6. Relevance to fronthaul load management

In a split RAN (for example a 7.2x split), channel-dependent matrix work runs
in the distributed unit, and its output rides the fronthaul to the radio unit.
Inversion time and inversion placement both shape fronthaul load. What these
numbers say for that work:

**Slot budgets.** A 5G slot at 30 kHz spacing is 500 microseconds. At n = 100
(massive MIMO scale) LU inversion takes about 0.1 ms on a plain CPU core, so
per-slot re-inversion of a 100 by 100 covariance matrix is realistic even
without accelerators. At n = 500 the 4 to 6 ms LU time no longer fits in one
slot, so matrices of that size must be inverted at a slower cadence (per
channel-coherence interval, not per slot), tracked incrementally, or offloaded
to an accelerator.

**Predictability matters as much as speed.** Fronthaul scheduling needs firm
compute deadlines. The iterative and learned methods have a fixed operation
count, so their latency is flat (InverseNet-NS p95 is within 5% of its
median). LAPACK calls are faster on average but showed occasional large
outliers under CPU contention (LU at n = 500: median 4.2 ms, p95 110 ms when
threads collide). On a shared DU server, pinning cores or fixing the BLAS
thread count is necessary before trusting the median.

**Where the learned approach fits.** Do not use a direct-regression network to
produce precoding or equalization weights; the MLP error levels here would
destroy link quality. The learned Newton-Schulz style is the credible option:
it meets a fixed compute budget, batches many users' matrices into one GPU
call, and its 1e-3 level error is within reach of tolerable for interference
suppression if the step count is raised. A practical pattern for load
management is a warm-start loop: reuse the previous slot's inverse as the
starting point, spend 1 to 2 Newton-Schulz steps per slot to track the
channel, and only pay for a full LU inversion when the channel changes
sharply. That converts a spiky compute load into a smooth one, which is
exactly what a fronthaul scheduler wants.

**Compression side effect.** If the DU sends inverses (or weights derived from
them) over the fronthaul, a learned fixed-step method also caps the bit-exact
recompute cost at the far end, since the RU can rerun the same cheap iteration
instead of receiving a full matrix. Whether that trade is worth it depends on
your split and link budget, but the fixed cost measured here (0.36 ms at
n = 100 on CPU) gives a concrete starting number.

## 7. Reproducing

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m matinv_bench.generate_dataset --dims 10 100 500 --num-samples 1000
.venv/bin/python -m matinv_bench.train_inversenet --dims 10 100 500
.venv/bin/python -m matinv_bench.benchmark --dims 10 100 500
```
