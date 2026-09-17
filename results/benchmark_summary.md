# Matrix inversion benchmark

- Host: x86_64, 6 torch threads, CPU only
- Dataset: random well-conditioned matrices `A = G/sqrt(n) + 2I`, float32
- Timing: per matrix (batch size 1), warmup 5, held-out split
- `residual` = mean of `||X @ A - I||_F / sqrt(n)`; `rel err` = mean of `||X - A^-1||_F / ||A^-1||_F`

## Dimension 10 (200 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| LAPACK getri (numpy.linalg.inv) | 0.018 | 0.018 | 0.020 | 3.32e-08 | 4.76e-08 |
| LU decomposition (scipy lu_factor/lu_solve) | 0.020 | 0.016 | 0.028 | 9.46e-08 | 9.02e-08 |
| InverseNet-Ultra (learned high-order) | 0.068 | 0.058 | 0.131 | 1.02e-01 | 1.73e-01 |
| SVD | 0.070 | 0.070 | 0.080 | 8.06e-08 | 7.97e-08 |
| QR decomposition | 0.140 | 0.074 | 0.278 | 1.85e-07 | 1.80e-07 |
| Gauss-Jordan elimination | 0.152 | 0.150 | 0.167 | 1.07e-07 | 1.01e-07 |
| Newton-Schulz iteration | 0.169 | 0.167 | 0.192 | 9.75e-08 | 8.43e-08 |
| InverseNet-MLP | 0.226 | 0.193 | 0.239 | 4.16e-01 | 3.57e-01 |
| InverseNet-NS (learned) | 0.294 | 0.283 | 0.350 | 2.82e-02 | 4.02e-02 |

## Dimension 100 (200 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| InverseNet-Ultra (learned high-order) | 0.473 | 0.459 | 0.569 | 1.06e-06 | 1.38e-06 |
| LAPACK getri (numpy.linalg.inv) | 0.571 | 0.174 | 1.134 | 3.39e-08 | 4.81e-08 |
| InverseNet-NS (learned) | 0.971 | 0.951 | 1.061 | 3.60e-04 | 4.03e-04 |
| Newton-Schulz iteration | 1.268 | 1.015 | 1.711 | 2.54e-07 | 2.01e-07 |
| Gauss-Jordan elimination | 1.970 | 1.787 | 3.400 | 3.39e-07 | 3.04e-07 |
| LU decomposition (scipy lu_factor/lu_solve) | 3.362 | 2.866 | 6.093 | 1.49e-07 | 1.32e-07 |
| InverseNet-MLP | 4.658 | 4.577 | 5.291 | 5.82e-01 | 5.21e-01 |
| SVD | 10.233 | 2.764 | 20.769 | 1.66e-07 | 1.38e-07 |
| QR decomposition | 20.293 | 3.944 | 64.547 | 3.48e-07 | 3.23e-07 |

## Dimension 500 (200 samples)

| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |
|---|---:|---:|---:|---:|---:|
| LAPACK getri (numpy.linalg.inv) | 28.611 | 18.004 | 45.087 | 3.43e-08 | 4.84e-08 |
| InverseNet-Ultra (learned high-order) | 36.994 | 33.789 | 52.680 | 1.49e-06 | 1.43e-06 |
| LU decomposition (scipy lu_factor/lu_solve) | 56.345 | 56.293 | 87.077 | 2.35e-07 | 1.98e-07 |
| Newton-Schulz iteration | 78.041 | 70.296 | 122.735 | 4.47e-07 | 3.49e-07 |
| InverseNet-NS (learned) | 89.621 | 92.116 | 100.927 | 4.82e-03 | 7.29e-03 |
| QR decomposition | 110.758 | 102.231 | 152.946 | 3.58e-07 | 3.24e-07 |
| SVD | 113.034 | 106.916 | 147.254 | 3.09e-07 | 2.45e-07 |
| Gauss-Jordan elimination | 160.281 | 159.288 | 166.070 | 7.71e-07 | 6.88e-07 |
