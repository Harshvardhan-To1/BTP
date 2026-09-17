"""Benchmark inference time (and accuracy) of matrix inversion techniques.

Methods compared per dimension:
  * LU decomposition (scipy lu_factor + lu_solve)
  * LAPACK getri (numpy.linalg.inv, also LU-based — tuned reference)
  * Gauss-Jordan elimination (vectorized numpy)
  * QR decomposition
  * SVD
  * Newton-Schulz iteration (classical, to 1e-6 residual)
  * InverseNet-MLP (dims 10, 100 — direct regression net)
  * InverseNet-NS (all dims — learned unrolled Newton-Schulz, 8 steps)

Neural models are evaluated on the held-out 20% split they were not
trained on; classical methods are timed on the same held-out matrices.
Timing is per matrix (batch size 1) with warmup, on CPU.

Outputs results/benchmark_results.csv, results/benchmark_summary.md and
results/inference_time.png.

Usage:
    python -m matinv_bench.benchmark --dims 10 100 500 [--max-samples N]
"""

from __future__ import annotations

import argparse
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .inversenet import FastBLASInferenceEngine, build_model
from .methods import CLASSICAL_METHODS
from .train_inversenet import TRAIN_FRACTION


WARMUP = 5


def errors(pred: np.ndarray, a: np.ndarray, true_inv: np.ndarray) -> tuple[float, float]:
    pred64, a64, inv64 = pred.astype(np.float64), a.astype(np.float64), true_inv.astype(np.float64)
    n = a.shape[0]
    residual = np.linalg.norm(pred64 @ a64 - np.eye(n)) / np.sqrt(n)
    rel = np.linalg.norm(pred64 - inv64) / np.linalg.norm(inv64)
    return residual, rel


def bench_callable(fn, matrices: np.ndarray, inverses: np.ndarray) -> dict:
    for a in matrices[:WARMUP]:
        fn(a)
    times, residuals, rels = [], [], []
    for a, inv in zip(matrices, inverses):
        t0 = time.perf_counter()
        pred = fn(a)
        times.append(time.perf_counter() - t0)
        residual, rel = errors(pred, a, inv)
        residuals.append(residual)
        rels.append(rel)
    times_ms = np.array(times) * 1e3
    return {
        "mean_ms": times_ms.mean(),
        "median_ms": np.median(times_ms),
        "p95_ms": np.percentile(times_ms, 95),
        "residual_err": float(np.mean(residuals)),
        "rel_err_vs_true": float(np.mean(rels)),
        "num_samples": len(matrices),
    }


def make_torch_fn(model: torch.nn.Module):
    model.eval()

    @torch.no_grad()
    def fn(a: np.ndarray) -> np.ndarray:
        t = torch.from_numpy(a).unsqueeze(0)
        return model(t).squeeze(0).numpy()

    return fn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dims", type=int, nargs="+", default=[10, 100, 500])
    parser.add_argument("--max-samples", type=int, default=None,
                        help="cap on evaluated held-out samples per method")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for dim in args.dims:
        with np.load(args.data_dir / f"matrices_dim{dim}.npz") as f:
            all_m, all_i = f["matrices"], f["inverses"]
        n_train = int(len(all_m) * TRAIN_FRACTION)
        matrices, inverses = all_m[n_train:], all_i[n_train:]
        if args.max_samples:
            matrices, inverses = matrices[: args.max_samples], inverses[: args.max_samples]
        print(f"=== dim {dim}: {len(matrices)} held-out samples ===")

        methods: dict[str, callable] = dict(CLASSICAL_METHODS)
        for kind, label in [("mlp", "InverseNet-MLP"), ("ns", "InverseNet-NS (learned)"), ("ultra", "InverseNet-Ultra (learned high-order)")]:
            ckpt = args.models_dir / f"inversenet_{kind}_dim{dim}.pt"
            if ckpt.exists():
                model = build_model(kind, dim)
                model.load_state_dict(torch.load(ckpt, weights_only=True))
                if kind == "ultra":
                    methods[label] = FastBLASInferenceEngine(model)
                else:
                    methods[label] = make_torch_fn(model)


        for name, fn in methods.items():
            stats = bench_callable(fn, matrices, inverses)
            rows.append({"dim": dim, "method": name, **stats})
            print(
                f"  {name:45s} mean={stats['mean_ms']:9.3f} ms  "
                f"median={stats['median_ms']:9.3f} ms  "
                f"resid={stats['residual_err']:.2e}  rel={stats['rel_err_vs_true']:.2e}"
            )

    df = pd.DataFrame(rows)
    csv_path = args.out_dir / "benchmark_results.csv"
    df.to_csv(csv_path, index=False)
    write_summary(df, args.out_dir / "benchmark_summary.md")
    plot(df, args.out_dir / "inference_time.png")
    print(f"\nWrote {csv_path}, benchmark_summary.md and inference_time.png")


def write_summary(df: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Matrix inversion benchmark",
        "",
        f"- Host: {platform.processor() or platform.machine()}, "
        f"{torch.get_num_threads()} torch threads, CPU only",
        "- Dataset: random well-conditioned matrices `A = G/sqrt(n) + 2I`, float32",
        "- Timing: per matrix (batch size 1), warmup 5, held-out split",
        "- `residual` = mean of `||X @ A - I||_F / sqrt(n)`; "
        "`rel err` = mean of `||X - A^-1||_F / ||A^-1||_F`",
        "",
    ]
    for dim, group in df.groupby("dim"):
        g = group.sort_values("mean_ms")
        lines += [f"## Dimension {dim} ({int(g['num_samples'].iloc[0])} samples)", ""]
        lines += ["| Method | Mean (ms) | Median (ms) | P95 (ms) | Residual | Rel err |",
                  "|---|---:|---:|---:|---:|---:|"]
        for _, r in g.iterrows():
            lines.append(
                f"| {r['method']} | {r['mean_ms']:.3f} | {r['median_ms']:.3f} | "
                f"{r['p95_ms']:.3f} | {r['residual_err']:.2e} | {r['rel_err_vs_true']:.2e} |"
            )
        lines.append("")
    path.write_text("\n".join(lines))


def plot(df: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for method, group in df.groupby("method"):
        g = group.sort_values("dim")
        ax.plot(g["dim"], g["mean_ms"], marker="o", label=method)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(sorted(df["dim"].unique()))
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("Matrix dimension n")
    ax.set_ylabel("Mean inference time per matrix (ms)")
    ax.set_title("Matrix inversion: inference time vs dimension (CPU)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


if __name__ == "__main__":
    main()
