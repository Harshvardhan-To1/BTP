# Building the MSE report

The submission PDF is `BTP_MSE_Report.pdf` in this directory. The editable source is `BTP_MSE_Report.tex`. Figures and the logo extracted from the department template are under `figures/`.

Requirements: a TeX Live installation with `article`, `geometry`, `graphicx`, `booktabs`, `amsmath`, `hyperref`, `enumitem`, `caption`, `microtype`, and `mathptmx` (Times). No BibTeX run is required; the reference list is in the TeX file.

```bash
cd report/mse
pdflatex -interaction=nonstopmode BTP_MSE_Report.tex || true
pdflatex -interaction=nonstopmode BTP_MSE_Report.tex || true
```

Run `pdflatex` twice. The first pass writes the citation numbers and exits with a nonzero status because those numbers are not yet known, so a script that stops on the first failure will leave every citation as `[?]`. The second pass fills in the numbers. After it, the PDF text must contain no `[?]`. The PDF must stay at one title page plus at most seven content pages (eight pages in total).

`validation/high_load_repro.txt` records the high-load re-execution used while writing the report. It does not replace the original logs, which remain on branch `cursor/fronthaul-load-management-prototype-4a6c` under `results/fhlm/`.
