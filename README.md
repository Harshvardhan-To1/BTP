# Fronthaul Load Management (B.Tech. Project)

The fronthaul is the link between a radio unit on the tower (O-RU) and the
processing unit (O-DU). In the O-RAN 7-2x split it carries raw radio samples,
so it is one of the most loaded links in a mobile network. This project looks at
the two ways to manage that load:

* **Part A — make the data smaller.** Compress the per-slot IQ matrix using its
  structure (matrix decomposition: truncated SVD, a randomised sketch + QR
  low-rank encoder, delay-domain sparsity), and measure how fast the matrix
  operations behind it (LU, QR, SVD, Newton-Schulz, learned inverters) run on a
  CPU. This part was done earlier in the project.
* **Part B — share one link well.** Several cells share a link that is smaller
  than their total peak. Every 10 ms a controller decides how many bits per
  slot each cell may send. We built a simulator, seven reference controllers and
  a new rule that uses a *forecast range* of each cell's need. This is the main
  work of this term.
* **A + B.** One experiment runs both levers on the same traffic: the
  compression setting decides how much load reaches the link, the allocation
  rule decides who loses data when bursts coincide.

## Headline results (plain words)

* Part A (earlier, quoted from the saved report and figures): compared with the
  O-RAN standard block-floating-point (BFP) compression (~4x), matrix-structure
  encoders reach 13-16x at about -20 dB error; the sketch + QR encoder is 3-4x
  faster than a full SVD, the delay-domain encoder 4-6x faster. In the
  inversion benchmark LU through LAPACK is the fastest exact method
  (0.17 ms at n = 100); a direct neural network that outputs the inverse fails
  (~50 % error); a learned Newton-Schulz iteration works (~1e-6 error) with a
  fixed, predictable cost.
* Part B (this term, 20 test seeds, priority-weighted deadline-violation
  ratio, same traffic for every controller, paired bootstrap CIs and
  Holm-corrected Wilcoxon tests): the proposed rule is the best real
  controller in all 5 scenarios. It cuts the score by 11-43 % compared with
  the same controller using a single predicted number, by 22-54 % compared
  with a tuned single global quantile, by 19-70 % compared with the
  deadline-aware reactive controller and by 18-83 % compared with MaxWeight,
  winning every seed (p < 0.01). It is only 4 % better than the plain
  proportional controller under flash crowds, loses to it when budgets are
  held for 20 ms, when telemetry is 5 ms old or above ~0.85 load, gains little
  from the ML model under a distribution shift, degrades gracefully when the
  forecast is miscalibrated, and online calibration did not help.
* A + B (same user traffic, BFP width 6 / 9 / 12 / 14 bits -> load 0.44 / 0.65 /
  0.86 / 0.99): at 0.44 almost nothing is lost whatever the rule; at 0.65 the
  proposed rule loses about half as much as the reactive controllers; at 0.86
  the proportional controller is slightly better; at 0.99 no allocation rule
  helps. Compression sets the regime; allocation helps most between ~0.5 and
  ~0.8 load.

Details: `docs/fhlm/results_summary.md`. Paper draft (IEEE conference format,
every number generated from the CSVs): `paper/main.tex`, `paper/main.pdf`;
reviewer-style assessment of what was missing and what was added:
`docs/fhlm/review_and_response.md`.

## Repository layout

| Path | Part | Purpose |
|---|---|---|
| `fhlm/config.py` | B | Units, 7-2x fronthaul constants (bits per PRB-layer incl. BFP width), cells, link |
| `fhlm/traffic.py` | B | Synthetic traffic: smooth part + heavy-tailed ON/OFF bursts + slow load changes + spectral-efficiency drift |
| `fhlm/demand.py` | B | Deadline-feasible rate r*(arrivals, deadline) and backlog rate |
| `fhlm/simulator.py` | B | Slot loop: queues with ages, budgets, link constraint, drops, metrics |
| `fhlm/controllers.py` | B | Reference controllers: static equal share, reactive proportional, MaxWeight, deadline-aware reactive, point-forecast water-fill, fixed-global-quantile water-fill, oracle water-fill |
| `fhlm/forecast.py` | B | Features, quantile gradient boosting, fast tree evaluation, simple window quantiles |
| `fhlm/proposed.py` | B | Proposed controller: forecast quantiles -> KKT allocation rule (+ optional online calibration) |
| `fhlm/scenarios.py` | B | Five scenarios; separate training / validation / test seed ranges |
| `fhlm/train.py` | B | Trains the forecaster on training seeds, reports validation quality |
| `fhlm/run_experiments.py` | B, A+B | `tune`, `main`, `sweep`, `delay`, `miscalibration`, `compression`, `demo` commands; raw JSON + CSV summaries; paired bootstrap / Wilcoxon / Holm statistics |
| `fhlm/make_figures.py`, `fhlm/make_slides.py`, `fhlm/make_paper_tables.py` | B | All figures, the editable `.pptx` deck (with speaker notes) and the paper's LaTeX tables/macros, from the saved results |
| `paper/` | B | IEEE conference paper draft (`main.tex`; `generated/` is produced by `make_paper_tables`) |
| `tests/test_fhlm.py` | B | 14 tests (link constraint, queues, accounting, zero load, overload, reproducibility, r*, KKT properties, no future leakage, fast tree evaluation, compression bridge) |
| `docs/fhlm/` | B | `method.md`, `literature_review.md`, `results_summary.md`, `review_and_response.md`, `study_guide.md`, `presentation_notes.md`, the deck (`.pptx`, `.pdf`) |
| `results/fhlm/` | B | Raw per-run metrics, CSV summaries, forecast reports, `figures/` |
| `models/fhlm_quantile_gbm_T20_d2.pkl` | B | Trained forecaster for the default 10 ms interval (the sweeps retrain their own per T / tau; those files are git-ignored) |
| `matinv_bench/` | A | Matrix-inversion benchmark: LU, QR, SVD, Gauss-Jordan, Newton-Schulz, learned inverters (needs PyTorch) |
| `results/benchmark_results.csv`, `results/benchmark_summary.md`, `results/inference_time.png`, `REPORT.md` | A | Benchmark output and report |
| `results/figures/exp1..4_*.png`, `docs/mid_evaluation_report.md`, `docs/mid_evaluation_slides.md` | A | Compression study figures and earlier report (BFP, truncated SVD, CSEE, RAS-BFP, ACAFS) |
| `experiments/exp1..4_*.py` | A | Scripts of the compression study. They import a `src/` package that is **not in this repository**, so they cannot be re-run as committed |

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # numpy, scipy, pandas, matplotlib, scikit-learn, pytest, python-pptx
pip install torch --index-url https://download.pytorch.org/whl/cpu   # only for matinv_bench (Part A)
```

CPU only. On a 4-core VM: tests 6 s, training 25 s, tuning ~3 min, main
comparison ~12 min (1000 runs), interval sweep ~7 min, telemetry-delay sweep
~4 min, miscalibration sweep ~3 min, compression sweep ~2 min, figures +
slides 10 s. Peak memory < 4 GB. Paper: `pdflatex` with the IEEEtran class
(`texlive-publishers`, `texlive-science`).

## Commands

```bash
# Part B
python -m pytest tests/test_fhlm.py -q                                  # 1. tests
python -m fhlm.train --out models/fhlm_quantile_gbm_T20_d2.pkl \
       --report results/fhlm/forecast_training_T20_d2.json               # 2. train the forecaster (training seeds) + validation report
python -m fhlm.run_experiments tune                                     # 3. tune baselines on validation seeds (never on test)
python -m fhlm.run_experiments main                                     # 4. 10 controllers x 5 scenarios x 20 test seeds + paired statistics
python -m fhlm.run_experiments sweep --intervals 4 10 20 40 --num-seeds 10  # 5. control-interval sweep (retrains per interval)
python -m fhlm.run_experiments delay --delays 0 2 5 10 --num-seeds 10   # 6. telemetry-delay sweep (retrains per delay)
python -m fhlm.run_experiments miscalibration --num-seeds 10            # 7. forecast-miscalibration sweep (Proposition 4 check)
python -m fhlm.run_experiments demo --scenario high                     # 8. one run with time series (demo figure)

# A + B
python -m fhlm.run_experiments compression --scenario moderate --num-seeds 10  # 9. BFP width (6/9/12/14 bits) x allocation rule

# figures, deck, paper
python -m fhlm.make_figures                                             # 10. all figures
python -m fhlm.make_slides                                              # 11. deck; PDF: soffice --headless --convert-to pdf docs/fhlm/*.pptx
python -m fhlm.make_paper_tables && (cd paper && pdflatex main && pdflatex main)  # 12. paper tables/macros + PDF

# Part A (matrix-inversion benchmark; needs torch)
python -m matinv_bench.generate_dataset --dims 10 100 500 --num-samples 1000
python -m matinv_bench.train_inversenet --dims 10 100 500
python -m matinv_bench.benchmark --dims 10 100 500
```

A 30-second demonstration: `python -m fhlm.run_experiments demo --scenario high --slots 6000`.

## How Part B works, in one paragraph

Traffic is generated first (`traffic.py`) and is identical for every controller
in a comparison. The simulator (`simulator.py`) runs slot by slot: arrivals
join a queue per cell in the O-DU, every T slots it builds an `Observation`
that only contains information that is tau slots old, asks the controller for
budgets, clips them so that they add up to at most the link capacity and never
exceed a cell's own peak, serves each queue first-in-first-out within its
budget, drops bits that waited longer than their deadline and records metrics.
Controllers (`controllers.py`, `proposed.py`) are functions of the observation
only; the forecast-based ones call a `QuantileGBMForecaster` (`forecast.py`)
trained beforehand on training seeds.

## What is done / what is not

Done: Part A compression study (figures, report) and inversion benchmark (CSV,
figure); Part B simulator, traffic model, seven reference controllers, forecast
pipeline with separate training / validation / test seeds, proposed controller
with four proved properties (feasibility, equal weighted risk, backlog first,
bounded loss under miscalibration), tuning on validation seeds, 1000-run main
comparison with paired statistics, interval / telemetry-delay /
miscalibration sweeps, ablations (single number vs range, per-cell vs global
quantile, ML vs simple quantiles, calibration on/off), the A + B compression
experiment, figures, presentation, IEEE-format paper draft with a reviewer
checklist.

Not done (future work): restore the Part A `src/` package into the repository
and re-run Exp 1-4; benchmark inversion on realistic channel matrices; make the
compression width a second knob of the allocation rule; real or public traffic
traces; a skill-weighted mix of trained and simple quantiles as the fallback;
a switch-level packet queue; uplink; a compiled implementation of the
decision (currently 3.5 ms in Python).
