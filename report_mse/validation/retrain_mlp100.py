"""Retrain only the dim-100 InverseNet-MLP checkpoint.

The original checkpoint (models/inversenet_mlp_dim100.pt, ~86 MB) is
gitignored, so the committed repository cannot run the dim-100 MLP row of the
benchmark. This driver reproduces it with the exact committed recipe from
matinv_bench/train_inversenet.py (epochs=15, batch=32, lr=1e-3,
torch.manual_seed(0)) and saves it into report_mse/validation/models/.

Run from the repository root:
    .venv/bin/python report_mse/validation/retrain_mlp100.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import torch

from matinv_bench.train_inversenet import load_split, train_one

matrices, inverses = load_split(Path("data"), 100)
model = train_one("mlp", 100, matrices, inverses, epochs=15, batch_size=32, lr=1e-3)
out = Path("report_mse/validation/models/inversenet_mlp_dim100.pt")
torch.save(model.state_dict(), out)
print(f"saved -> {out}")
