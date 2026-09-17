"""Train InverseNet models on the generated dataset.

Trains, per dimension:
  * InverseNetMLP for dims where it is practical (10, 100)
  * InverseNetNS (learned Newton-Schulz) for every dimension

The first 80% of each dataset is used for training, the rest is held out;
the benchmark script evaluates on the held-out split only.

Usage:
    python -m matinv_bench.train_inversenet --dims 10 100 500
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from .inversenet import build_model

TRAIN_FRACTION = 0.8


def load_split(data_dir: Path, dim: int) -> tuple[torch.Tensor, torch.Tensor]:
    with np.load(data_dir / f"matrices_dim{dim}.npz") as f:
        matrices = torch.from_numpy(f["matrices"])
        inverses = torch.from_numpy(f["inverses"])
    n_train = int(len(matrices) * TRAIN_FRACTION)
    return matrices[:n_train], inverses[:n_train]


def train_one(
    kind: str,
    dim: int,
    matrices: torch.Tensor,
    inverses: torch.Tensor,
    epochs: int,
    batch_size: int,
    lr: float,
) -> nn.Module:
    torch.manual_seed(0)
    model = build_model(kind, dim)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    n = len(matrices)
    eye = torch.eye(dim)
    t0 = time.perf_counter()
    for epoch in range(epochs):
        perm = torch.randperm(n)
        total = 0.0
        for start in range(0, n, batch_size):
            idx = perm[start : start + batch_size]
            a, target = matrices[idx], inverses[idx]
            pred = model(a)
            # MSE to ground truth plus residual ||pred @ A - I||^2 keeps the
            # prediction a *left* inverse, not just close in Frobenius norm.
            loss = nn.functional.mse_loss(pred, target)
            loss = loss + 0.1 * (pred @ a - eye).square().mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        if epoch == 0 or (epoch + 1) % max(1, epochs // 5) == 0:
            print(
                f"  [{kind} dim={dim}] epoch {epoch + 1}/{epochs} "
                f"loss={total / n:.3e} ({time.perf_counter() - t0:.0f}s)"
            )
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dims", type=int, nargs="+", default=[10, 100, 500])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    args = parser.parse_args()

    args.models_dir.mkdir(parents=True, exist_ok=True)
    for dim in args.dims:
        matrices, inverses = load_split(args.data_dir, dim)
        kinds = ["ns", "ultra"] if dim > 100 else ["mlp", "ns", "ultra"]
        for kind in kinds:
            if kind == "mlp":
                epochs, batch_size, lr = (200, 64, 1e-3) if dim == 10 else (15, 32, 1e-3)

            elif kind == "ns":
                epochs, batch_size, lr = {10: (60, 64, 3e-2), 100: (30, 32, 3e-2)}.get(
                    dim, (3, 4, 3e-2)
                )
            else:  # ultra
                epochs, batch_size, lr = {10: (80, 64, 1e-2), 100: (40, 32, 1e-2)}.get(
                    dim, (15, 16, 1e-2)
                )
            train_m, train_i = matrices, inverses
            if (kind == "ns" or kind == "ultra") and dim > 100:
                train_m, train_i = matrices[:200], inverses[:200]
            print(f"Training InverseNet-{kind.upper()} for dim={dim} ...")
            model = train_one(kind, dim, train_m, train_i, epochs, batch_size, lr)
            out = args.models_dir / f"inversenet_{kind}_dim{dim}.pt"
            torch.save(model.state_dict(), out)
            print(f"  saved -> {out}")



if __name__ == "__main__":
    main()
