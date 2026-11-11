"""Regenerate the MSE-report figures from the committed raw benchmark data.

Reads results/benchmark_results.csv (the committed run) and, when present,
report_mse/validation/results_rerun/benchmark_results.csv (this task's
verification rerun), and writes PDF figures into report_mse/figures/.

Run from the repository root:
    .venv/bin/python report_mse/make_figures.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report_mse" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "legend.fontsize": 7.3,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 200,
})

SHORT = {
    "LAPACK getri (numpy.linalg.inv)": "LAPACK getri (np.linalg.inv)",
    "LU decomposition (scipy lu_factor/lu_solve)": "LU (scipy lu_factor/solve)",
    "Gauss-Jordan elimination": "Gauss-Jordan (pure NumPy)",
    "QR decomposition": "QR",
    "SVD": "SVD",
    "Newton-Schulz iteration": "Newton-Schulz (to 1e-6)",
    "InverseNet-MLP": "InverseNet-MLP",
    "InverseNet-NS (learned)": "InverseNet-NS (learned, 8 steps)",
    "InverseNet-Ultra (learned high-order)": "InverseNet-Ultra (learned)",
}
LEARNED = {"InverseNet-MLP", "InverseNet-NS (learned)",
           "InverseNet-Ultra (learned high-order)"}
COLORS = {
    "LAPACK getri (numpy.linalg.inv)": "tab:blue",
    "LU decomposition (scipy lu_factor/lu_solve)": "tab:cyan",
    "Gauss-Jordan elimination": "tab:brown",
    "QR decomposition": "tab:gray",
    "SVD": "tab:olive",
    "Newton-Schulz iteration": "tab:green",
    "InverseNet-MLP": "tab:red",
    "InverseNet-NS (learned)": "tab:orange",
    "InverseNet-Ultra (learned high-order)": "tab:purple",
}

# Primary source: this task's verification rerun (accuracy identical to the
# committed run; timings from a fully documented, lightly loaded host). Falls
# back to the committed CSV when the rerun is absent.
rerun = ROOT / "report_mse" / "validation" / "results_rerun" / "benchmark_results.csv"
committed = ROOT / "results" / "benchmark_results.csv"
src = rerun if rerun.exists() else committed
print("plotting from:", src)
df = pd.read_csv(src)

# Figure 1: median inference time vs dimension -------------------------------
fig, ax = plt.subplots(figsize=(5.2, 3.1))
for method, g in df.groupby("method"):
    g = g.sort_values("dim")
    ls = "--" if method in LEARNED else "-"
    marker = "s" if method in LEARNED else "o"
    ax.plot(g["dim"], g["median_ms"], marker=marker, ms=3.5, ls=ls,
            lw=1.2, color=COLORS[method], label=SHORT[method])
ax.axhline(0.5, color="k", lw=0.8, ls=":", alpha=0.7)
ax.text(11, 0.58, "0.5 ms slot (30 kHz SCS)", fontsize=7, alpha=0.8)
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xticks([10, 100, 500])
ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
ax.set_xlabel("Matrix dimension $n$")
ax.set_ylabel("Median time per matrix (ms)")
ax.grid(True, which="both", alpha=0.25)
ax.legend(ncol=2, loc="upper left", framealpha=0.9, columnspacing=0.9,
          handlelength=1.6)
fig.tight_layout()
fig.savefig(OUT / "fig_time_vs_dim.pdf")
plt.close(fig)

# Figure 2: accuracy vs latency trade-off at n = 100 and n = 500 -------------
fig, axes = plt.subplots(1, 2, figsize=(5.4, 2.7), sharey=True)
for ax, dim in zip(axes, [100, 500]):
    g = df[df["dim"] == dim]
    for _, r in g.iterrows():
        m = r["method"]
        marker = "s" if m in LEARNED else "o"
        ax.scatter(r["median_ms"], r["rel_err_vs_true"], s=26,
                   color=COLORS[m], marker=marker, zorder=3,
                   label=SHORT[m])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title(f"$n = {dim}$")
    ax.set_xlabel("Median time (ms)")
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.grid(True, which="both", alpha=0.25)
axes[0].set_ylabel("Relative error vs. true inverse")
handles, labels = axes[1].get_legend_handles_labels()
if len(handles) < 9:  # dim 500 has no MLP row; take legend from dim 100
    handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=6.8,
           frameon=False, bbox_to_anchor=(0.5, -0.02), columnspacing=0.8,
           handletextpad=0.3)
fig.tight_layout(rect=(0, 0.14, 1, 1))
fig.savefig(OUT / "fig_accuracy_vs_time.pdf", bbox_inches="tight")
plt.close(fig)

print("wrote", sorted(p.name for p in OUT.iterdir()))
