"""Shared plotting style and result-saving helpers for the experiment scripts."""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIG_DIR = os.path.join(ROOT, "results", "figures")
DATA_DIR = os.path.join(ROOT, "results", "data")

matplotlib.rcParams.update({
    "font.family": "DejaVu Serif", "font.size": 11,
    "axes.labelsize": 12, "axes.titlesize": 12, "legend.fontsize": 9,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "figure.dpi": 150,
    "axes.grid": True, "grid.alpha": 0.3, "lines.linewidth": 2.0, "lines.markersize": 6,
})
COLORS = {"BFP": "#7f8c8d", "SVD": "#2980b9", "CSEE": "#e74c3c", "RAS-BFP": "#27ae60",
          "uniform-CSEE": "#7f8c8d", "uniform-BFP": "#34495e", "greedy-sum": "#e74c3c",
          "greedy-max": "#8e44ad", "oracle": "#27ae60"}
MARKERS = {"BFP": "s", "SVD": "^", "CSEE": "o", "RAS-BFP": "D",
           "uniform-CSEE": "s", "uniform-BFP": "v", "greedy-sum": "o", "greedy-max": "P", "oracle": "D"}


def _to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    return obj


def save_json(name: str, payload: dict) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = dict(payload)
    payload["_meta"] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "numpy": np.__version__,
        "host": platform.processor() or platform.machine(), "cpu_count": os.cpu_count(),
    }
    path = os.path.join(DATA_DIR, name)
    with open(path, "w") as f:
        json.dump(_to_jsonable(payload), f, indent=1)
    return path


def save_fig(fig, stem: str) -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.tight_layout()
    for ext, kw in (("pdf", {}), ("png", {"dpi": 220})):
        fig.savefig(os.path.join(FIG_DIR, f"{stem}.{ext}"), bbox_inches="tight", **kw)
    print(f"[fig] results/figures/{stem}.pdf|png")
    plt.close(fig)
