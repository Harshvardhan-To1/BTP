"""Generate a dataset of well-conditioned random matrices and their inverses.

For each dimension n we draw

    A = G / sqrt(n) + 2 * I,   G_ij ~ N(0, 1)

By the circular law the eigenvalues of G/sqrt(n) concentrate in the unit
disk, so the spectrum of A lives in a disk centered at 2 with radius ~1.
This keeps every sample safely invertible and well conditioned, which is
required both for a meaningful ground-truth inverse and for iterative /
learned methods to have a fair shot.

Inverses are computed in float64 and both arrays are stored as float32
(.npz, one file per dimension) to keep disk usage reasonable
(dim 500: ~2 GB total).

Usage:
    python -m matinv_bench.generate_dataset --dims 10 100 500 --num-samples 1000
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np


def generate_pairs(n: int, num_samples: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    matrices = np.empty((num_samples, n, n), dtype=np.float32)
    inverses = np.empty((num_samples, n, n), dtype=np.float32)
    for i in range(num_samples):
        g = rng.standard_normal((n, n))
        a = g / np.sqrt(n) + 2.0 * np.eye(n)
        inv = np.linalg.inv(a)
        # Guard against a rare badly conditioned draw.
        residual = np.linalg.norm(a @ inv - np.eye(n)) / np.sqrt(n)
        if residual > 1e-8:
            raise RuntimeError(f"sample {i} (n={n}) poorly conditioned, residual={residual:.2e}")
        matrices[i] = a.astype(np.float32)
        inverses[i] = inv.astype(np.float32)
    return matrices, inverses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dims", type=int, nargs="+", default=[10, 100, 500])
    parser.add_argument("--num-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for n in args.dims:
        out_path = args.out_dir / f"matrices_dim{n}.npz"
        if out_path.exists():
            print(f"[skip] {out_path} already exists")
            continue
        t0 = time.perf_counter()
        matrices, inverses = generate_pairs(n, args.num_samples, seed=args.seed + n)
        np.savez(out_path, matrices=matrices, inverses=inverses)
        size_mb = out_path.stat().st_size / 1e6
        print(
            f"[done] dim={n}: {args.num_samples} samples -> {out_path} "
            f"({size_mb:.1f} MB, {time.perf_counter() - t0:.1f}s)"
        )


if __name__ == "__main__":
    main()
