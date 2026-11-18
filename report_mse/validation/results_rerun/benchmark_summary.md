# Matrix inversion benchmark

- Host: x86_64, 4 torch threads, CPU only
- Dataset: random well-conditioned matrices `A = G/sqrt(n) + 2I`, float32
- Timing: per matrix (batch size 1), warmup 5, held-out split
- `residual` = mean of `||X @ A - I||_F / sqrt(n)`; `rel err` = mean of `||X - A^-1||_F / ||A^-1||_F`

## Dimension 10 (200 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| LAPACK getri (numpy.linalg.inv) | 0.005 | 0.005 | 0.006 | 3.32e-08 | 4.76e-08 |
| QR decomposition | 0.015 | 0.015 | 0.017 | 1.88e-07 | 1.81e-07 |
| LU decomposition (scipy lu_factor/lu_solve) | 0.016 | 0.015 | 0.019 | 8.78e-08 | 8.55e-08 |
| SVD | 0.022 | 0.022 | 0.023 | 8.19e-08 | 8.11e-08 |
| InverseNet-Ultra (learned high-order) | 0.028 | 0.028 | 0.029 | 1.02e-01 | 1.73e-01 |
| Newton-Schulz iteration | 0.039 | 0.038 | 0.044 | 1.08e-07 | 9.25e-08 |
| Gauss-Jordan elimination | 0.047 | 0.046 | 0.049 | 1.07e-07 | 1.01e-07 |
| InverseNet-MLP | 0.051 | 0.050 | 0.054 | 4.16e-01 | 3.57e-01 |
| InverseNet-NS (learned) | 0.118 | 0.116 | 0.130 | 2.82e-02 | 4.02e-02 |

## Dimension 100 (200 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| LU decomposition (scipy lu_factor/lu_solve) | 0.116 | 0.107 | 0.147 | 1.60e-07 | 1.38e-07 |
| LAPACK getri (numpy.linalg.inv) | 0.131 | 0.130 | 0.141 | 3.39e-08 | 4.81e-08 |
| InverseNet-Ultra (learned high-order) | 0.208 | 0.204 | 0.233 | 1.07e-06 | 1.39e-06 |
| QR decomposition | 0.264 | 0.261 | 0.281 | 3.53e-07 | 3.26e-07 |
| InverseNet-NS (learned) | 0.373 | 0.369 | 0.412 | 3.60e-04 | 4.03e-04 |
| Newton-Schulz iteration | 0.402 | 0.399 | 0.434 | 2.75e-07 | 2.17e-07 |
| InverseNet-MLP | 1.093 | 0.782 | 0.844 | 5.82e-01 | 5.21e-01 |
| SVD | 1.215 | 1.207 | 1.270 | 1.80e-07 | 1.48e-07 |
| Gauss-Jordan elimination | 1.337 | 1.376 | 1.444 | 3.39e-07 | 3.04e-07 |

## Dimension 500 (200 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| LAPACK getri (numpy.linalg.inv) | 5.945 | 5.717 | 5.924 | 3.43e-08 | 4.84e-08 |
| InverseNet-Ultra (learned high-order) | 9.055 | 8.917 | 9.689 | 1.50e-06 | 1.44e-06 |
| Newton-Schulz iteration | 17.872 | 17.966 | 18.503 | 4.67e-07 | 3.64e-07 |
| LU decomposition (scipy lu_factor/lu_solve) | 20.581 | 4.206 | 109.965 | 2.63e-07 | 2.16e-07 |
| SVD | 36.735 | 36.564 | 37.996 | 3.23e-07 | 2.55e-07 |
| QR decomposition | 48.551 | 12.246 | 115.874 | 4.00e-07 | 3.56e-07 |
| InverseNet-NS (learned) | 115.620 | 117.757 | 123.942 | 4.82e-03 | 7.29e-03 |
| Gauss-Jordan elimination | 151.164 | 150.272 | 156.800 | 7.71e-07 | 6.88e-07 |
