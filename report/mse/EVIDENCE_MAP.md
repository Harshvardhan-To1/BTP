# Evidence map (not part of the eight-page report)

This map links claims in `BTP_MSE_Report.pdf` to repository evidence. The checked-out default branch `main` (commit `86ad6e3`, message `view`) does **not** contain the allocation package. That package, its tests, and its raw logs are on `origin/cursor/fronthaul-load-management-prototype-4a6c` at commit `616c1d3`. The matrix-inversion code and `results/benchmark_results.csv` are on both trees. Compression experiment scripts on `main` import a `src/` package that is not in that tree; those NMSE figures are therefore not used as results in the report.

## Identity

| Claim | Evidence | Status |
|---|---|---|
| Students Harshvardhan Choudhary (230002027) and Mayank Yadav (230002041); supervisor Dr. Sumit Gautam | Supplied in the report task, 24 Sep 2026 | Confirmed by the user for this report |
| Project No. P22; title “Fronthaul Load Management for B5G Wireless Communications”; specialization CSP | Supplied by the students on 24 Sep 2026 | Printed on the title page. Not inferred from the repository |

## System model

| Claim | Source |
|---|---|
| 8 cells, 25 Gbit/s, 3% control reserve, \(C_u=24.25\) Gbit/s, 0.5 ms slot, 273 PRBs, 4 layers, \(\beta=3387\) bit at BFP-9, peak 7.4 Gbit/s, aggregate about \(2.4 C_u\) | `fhlm/config.py` and `docs/fhlm/method.md` on the prototype branch |
| Deadlines 2 ms / 10 ms, priorities 3 and 1, \(T=20\) slots, \(\tau=2\) slots | `docs/fhlm/method.md`, `fhlm/config.py` |
| \(r^\star\) formula | `fhlm/demand.py`; statement and network-calculus attribution in `docs/fhlm/method.md` |
| KKT budget \(r_i(\lambda)=B_i+F_i^{-1}(1-\lambda/w_i)\) | `fhlm/proposed.py`; derivation notes in `docs/fhlm/method.md` §5 |
| Quantiles 0.05–0.95, 28 features, separate seed ranges 1000–1015 / 2000–2003 / 3000–3004 | `fhlm/forecast.py`, `fhlm/scenarios.py`, `docs/fhlm/method.md` §6–7 |
| Zero margin selected on validation | `results/fhlm/tuning.json` as summarised in `docs/fhlm/results_summary.md` |

## Main numerical table

All means are from `results/fhlm/main_summary.csv` (200 runs: 8 controllers × 5 scenarios × 5 seeds). Relative reductions were recomputed from those means as \((v_{\text{base}}-v_{\text{proposed}})/v_{\text{base}}\), and they match `docs/fhlm/results_summary.md`.

| Report figure | CSV value (ratio) | Report (%) |
|---|---|---|
| High, proposed | 0.078884 | 7.89 |
| High, point forecast | 0.096268 | 9.63 |
| High, deadline-aware reactive (`queue_aware`) | 0.108567 | 10.86 |
| High, reactive proportional | 0.089405 | 8.94 |
| High, low-latency / eMBB for proposed | 0.031900 / 0.123496 | 3.2 / 12.3 |
| High, utilisation proposed / point / deadline-aware | 0.7201 / 0.7000 / 0.6924 | 72.0 / 70.0 / 69.2 |

Paired win counts (5/5 against the point forecast and the deadline-aware reactive controller; 3/5 against reactive proportional under flash crowds) are from `results/fhlm/main_paired.csv` as transcribed in `docs/fhlm/results_summary.md`.

**Reproduced during this task:** the high-load subset (proposed, point forecast, deadline-aware reactive, reactive proportional; five test seeds; 20,000 slots). Ratios matched the CSV. See `validation/high_load_repro.txt`. Decision time on this host was 3.47 ms per epoch for the proposed rule, against 3.36 ms in the saved high-load row. The report says “about 3.5 ms” for this host.

**Not re-simulated:** low, moderate, flash-crowd, and shift scenarios; taken from the saved CSV and checked arithmetically. No significance test exists in the code, and none is claimed.

## Other experiments

| Claim | Source | Re-run? |
|---|---|---|
| Interval sweep at \(T=4,10,20,40\) (3 seeds, high load): −62%, −27%, −57% at \(T=4\); +12% vs reactive proportional at \(T=40\) | `results/fhlm/sweep_summary.csv`. Reductions recomputed from the means | No |
| Mantissa sweep loads 0.43 / 0.63 / 0.83 / 0.97 and the violation ratios in the report | `results/fhlm/compression_summary.csv` (`realised_load_mean`, `weighted_violation_ratio_mean`) | No |
| Forecast coverage 5.6/25.6/50.7/75.3/89.9/94.9% and median relative MAE 37% vs persistence 52% | `results/fhlm/forecast_training_T20_d2.json` (`gbm_validation`, `persistence_median_mae_rel`) | Not re-trained. The report cites the coverage only indirectly via the method; the 37% figure is in the notes, not as a headline table |
| 14 unit tests passed | `tests/test_fhlm.py` on commit `616c1d3`, re-run 24 Sep 2026 (14 passed) | Yes |
| Inversion medians: LAPACK 0.174 ms / 18.0 ms at \(n=100/500\); relative error about \(4.8\times 10^{-8}\); MLP relative error 0.357 and 0.521; learned iteration 0.459 ms and 33.8 ms with relative error \(1.38\times 10^{-6}\) and \(1.43\times 10^{-6}\); \(n=10\) learned-iteration relative error 0.173 | `results/benchmark_results.csv` on `main` (same bytes as the prototype branch) | Not re-timed. No dataset or claim of a new benchmark |
| I/Q compression NMSE and compression-ratio curves | `results/figures/exp1_nmse_vs_cr.png` exists, but `experiments/exp1_nmse_vs_cr.py` imports missing `src/`. Prototype README states these numbers were not regenerated | Omitted from the report as results |

## Citations

Bibliographic details follow `docs/fhlm/literature_review.md` on the prototype branch, except Cohen *et al.*, which that note places in *IEEE Wireless Communications Letters*. A publisher record checked on 24 Sep 2026 places the same paper in *IEEE Signal Processing Letters*, vol. 30, pp. 473–477, 2023, doi:10.1109/LSP.2023.3264939. The report uses the publisher record. Full texts were not re-read for every item while writing this report; the report states that limitation in Section 3.

## What is not claimed

No hardware trial, no real traffic trace, no statistical significance, no statement that the rule is optimal or uniformly best, and no statement that a Python decision time is real-time operation inside an O-DU.
