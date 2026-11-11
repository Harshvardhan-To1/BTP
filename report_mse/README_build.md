# Build and provenance record — BTP MSE report

## Manuscript version

- Repository snapshot: commit `86ad6e3` (branch `main`), plus this
  `report_mse/` directory added by the report-production task.
- Report source: `report_mse/BTP_MSE_Report.tex` (LaTeX, single file;
  bibliography embedded via `thebibliography`).
- Final PDF: `report_mse/BTP_MSE_Report.pdf`, 7 pages
  (1 title page + 6 content pages).
- Final PDF SHA-256:
  `6ab2c0de345d9695572c955deb647d4cfa5110d819c55a821b7a2a159e471745`
- Any later edit to the .tex or figures invalidates this hash and any
  similarity report obtained for this version; recompute and re-check.

## Build prerequisites

- TeX Live with `latexmk`, `geometry`, `mathptmx` (psnfss), `booktabs`,
  `caption`, `titlesec`, `enumitem`, `microtype`, `hyperref`
  (Ubuntu: `texlive-latex-base texlive-latex-recommended texlive-latex-extra
  texlive-fonts-recommended latexmk`).
- Figures are pre-built PDFs in `report_mse/figures/`; rebuilding them needs
  Python with numpy, pandas, matplotlib (see below).

## Exact build commands (from the repository root)

```bash
cd report_mse
latexmk -pdf -interaction=nonstopmode BTP_MSE_Report.tex
```

To regenerate the figures from raw data first:

```bash
.venv/bin/python report_mse/make_figures.py   # reads the rerun CSV; falls back to results/benchmark_results.csv
```

## Validation provenance (Phase B verification rerun)

Environment: 4 vCPU x86-64, Ubuntu 24.04, Python 3.12.3, NumPy 2.5.3,
SciPy 1.18.1, pandas 3.0.6, matplotlib 3.11.2, PyTorch 2.14.0+cpu
(CPU-only, 4 torch threads). Executed 2026-09-24.

```bash
python3 -m venv .venv && .venv/bin/pip install numpy scipy pandas matplotlib tqdm
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m matinv_bench.generate_dataset --dims 10 100 500 --num-samples 1000
.venv/bin/python report_mse/validation/retrain_mlp100.py
.venv/bin/python -m matinv_bench.benchmark --dims 10 100 500 \
    --models-dir report_mse/validation/models \
    --out-dir report_mse/validation/results_rerun
```

Outputs: `report_mse/validation/results_rerun/` (CSV, summary, plot),
`report_mse/validation/models/inversenet_mlp_dim100.pt` (retrained, seeded).
Original experiment outputs in `results/` and checkpoints in `models/` were
not modified. Run-to-run comparison: `report_mse/validation/comparison.md`.
Claim-to-evidence mapping: `report_mse/evidence_map.md`.

Note: `data/` (regenerated, ~2 GB) and the retrained 86 MB checkpoint are
reproducible from seeds and are not intended for version control (data/ is
gitignored; the checkpoint path matches the original gitignore entry pattern
only in `models/`, so the copy under validation is kept out via gitignore
update if size is a concern).
