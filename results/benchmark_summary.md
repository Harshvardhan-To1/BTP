# Matrix inversion benchmark

- Host: x86_64, 4 torch threads, CPU only
- Dataset: random well-conditioned matrices `A = G/sqrt(n) + 2I`, float32
- Timing: per matrix (batch size 1), warmup 5, held-out split
- `residual` = mean of `||X @ A - I||_F / sqrt(n)`; `rel err` = mean of `||X - A^-1||_F / ||A^-1||_F`

## Dimension 10 (200 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| LAPACK getri (numpy.linalg.inv) | 0.006 | 0.006 | 0.006 | 3.32e-08 | 4.76e-08 |
| QR decomposition | 0.014 | 0.014 | 0.017 | 1.88e-07 | 1.81e-07 |
| SVD | 0.022 | 0.021 | 0.027 | 8.19e-08 | 8.11e-08 |
| LU decomposition (scipy lu_factor/lu_solve) | 0.024 | 0.015 | 0.021 | 8.78e-08 | 8.55e-08 |
| InverseNet-Ultra (learned high-order) | 0.039 | 0.038 | 0.042 | 9.93e-02 | 1.67e-01 |
| Newton-Schulz iteration | 0.043 | 0.042 | 0.049 | 1.08e-07 | 9.25e-08 |
| Gauss-Jordan elimination | 0.044 | 0.044 | 0.046 | 1.07e-07 | 1.01e-07 |
| InverseNet-NS (learned) | 0.116 | 0.114 | 0.124 | 2.82e-02 | 4.02e-02 |
| InverseNet-MLP | 0.490 | 0.050 | 0.056 | 4.16e-01 | 3.57e-01 |

## Dimension 100 (200 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| LU decomposition (scipy lu_factor/lu_solve) | 0.093 | 0.092 | 0.102 | 1.60e-07 | 1.38e-07 |
| LAPACK getri (numpy.linalg.inv) | 0.139 | 0.138 | 0.148 | 3.39e-08 | 4.81e-08 |
| QR decomposition | 0.260 | 0.258 | 0.273 | 3.53e-07 | 3.26e-07 |
| InverseNet-NS (learned) | 0.332 | 0.328 | 0.355 | 3.60e-04 | 4.03e-04 |
| InverseNet-Ultra (learned high-order) | 0.400 | 0.397 | 0.409 | 8.46e-07 | 1.15e-06 |
| Newton-Schulz iteration | 0.401 | 0.403 | 0.425 | 2.75e-07 | 2.17e-07 |
| SVD | 1.236 | 1.230 | 1.275 | 1.80e-07 | 1.48e-07 |
| Gauss-Jordan elimination | 1.382 | 1.383 | 1.403 | 3.39e-07 | 3.04e-07 |

## Dimension 500 (20 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| LAPACK getri (numpy.linalg.inv) | 6.032 | 5.865 | 7.126 | 3.43e-08 | 4.83e-08 |
| Newton-Schulz iteration | 17.900 | 18.147 | 18.238 | 4.66e-07 | 3.63e-07 |
| InverseNet-Ultra (learned high-order) | 17.903 | 17.886 | 18.028 | 1.32e-06 | 1.31e-06 |
| SVD | 35.695 | 35.750 | 36.311 | 3.24e-07 | 2.56e-07 |
| LU decomposition (scipy lu_factor/lu_solve) | 46.534 | 3.317 | 110.856 | 2.63e-07 | 2.15e-07 |
| QR decomposition | 53.518 | 25.957 | 113.175 | 4.00e-07 | 3.56e-07 |
| InverseNet-NS (learned) | 112.129 | 116.988 | 126.597 | 4.85e-03 | 7.41e-03 |
| Gauss-Jordan elimination | 188.806 | 188.724 | 189.417 | 7.68e-07 | 6.87e-07 |
