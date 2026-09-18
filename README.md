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
  slot each cell may send. We built a simulator, five reference controllers and
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
* Part B (this term, 5 test seeds, priority-weighted deadline-violation ratio,
  same traffic for every controller): the proposed rule is the best real
  controller in all 5 scenarios. It cuts the score by 10-53 % compared with
  the same controller using a single predicted number, and by 18-79 % compared
  with the deadline-aware reactive controller, winning every seed. It ties with
  the plain proportional controller under flash crowds, loses to it when
  budgets are held for 20 ms, gains little from the ML model under a
  distribution shift, and online calibration did not help.
* A + B (same user traffic, BFP width 6 / 9 / 12 / 14 bits -> load 0.43 / 0.63 /
  0.83 / 0.97): at 0.43 almost nothing is lost whatever the rule; at 0.63 the
  proposed rule loses about half as much as the reactive controllers; at 0.83
  it ties; at 0.97 no allocation rule helps. Compression sets the regime;
  allocation helps most between ~0.5 and ~0.8 load.

Details: `docs/fhlm/results_summary.md`.

## Repository layout

| Path | Part | Purpose |
|---|---|---|
| `fhlm/config.py` | B | Units, 7-2x fronthaul constants (bits per PRB-layer incl. BFP width), cells, link |
| `fhlm/traffic.py` | B | Synthetic traffic: smooth part + heavy-tailed ON/OFF bursts + slow load changes + spectral-efficiency drift |
| `fhlm/demand.py` | B | Deadline-feasible rate r*(arrivals, deadline) and backlog rate |
| `fhlm/simulator.py` | B | Slot loop: queues with ages, budgets, link constraint, drops, metrics |
| `fhlm/controllers.py` | B | Reference controllers: static equal share, reactive proportional, deadline-aware reactive, point-forecast water-fill, oracle water-fill |
| `fhlm/forecast.py` | B | Features, quantile gradient boosting, fast tree evaluation, simple window quantiles |
| `fhlm/proposed.py` | B | Proposed controller: forecast quantiles -> KKT allocation rule (+ optional online calibration) |
| `fhlm/scenarios.py` | B | Five scenarios; separate training / validation / test seed ranges |
| `fhlm/train.py` | B | Trains the forecaster on training seeds, reports validation quality |
| `fhlm/run_experiments.py` | B, A+B | `tune`, `main`, `sweep`, `compression`, `demo` commands; raw JSON + CSV summaries |
| `fhlm/make_figures.py`, `fhlm/make_slides.py` | B | All figures and the editable `.pptx` deck (with speaker notes) from the saved results |
| `tests/test_fhlm.py` | B | 14 tests (link constraint, queues, accounting, zero load, overload, reproducibility, r*, KKT properties, no future leakage, fast tree evaluation, compression bridge) |
| `docs/fhlm/` | B | `method.md`, `literature_review.md`, `results_summary.md`, `presentation_notes.md`, the deck (`.pptx`, `.pdf`) |
| `results/fhlm/` | B | Raw per-run metrics, CSV summaries, forecast reports, `figures/` |
| `models/fhlm_quantile_gbm_T20_d2.pkl` | B | Trained forecaster for the default 10 ms interval |
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

CPU only. On a 4-core VM: tests 6 s, training 25 s, tuning 90 s, main
comparison 135 s, interval sweep ~6 min, compression sweep 35 s, figures +
slides 10 s. Peak memory < 4 GB.

## Commands

```bash
# Part B
python -m pytest tests/test_fhlm.py -q                                  # 1. tests
python -m fhlm.train --out models/fhlm_quantile_gbm_T20_d2.pkl \
       --report results/fhlm/forecast_training_T20_d2.json               # 2. train the forecaster (training seeds) + validation report
python -m fhlm.run_experiments tune                                     # 3. tune baselines on validation seeds (never on test)
python -m fhlm.run_experiments main                                     # 4. 8 controllers x 5 scenarios x 5 test seeds + seed-by-seed analysis
python -m fhlm.run_experiments sweep --intervals 4 10 20 40 --num-seeds 3   # 5. control-interval sweep (retrains per interval)
python -m fhlm.run_experiments demo --scenario high                     # 6. one run with time series (demo figure)

# A + B
python -m fhlm.run_experiments compression --scenario moderate          # 7. BFP width (6/9/12/14 bits) x allocation rule

# figures and deck
python -m fhlm.make_figures                                             # 8. all figures
python -m fhlm.make_slides                                              # 9. deck; PDF: soffice --headless --convert-to pdf docs/fhlm/*.pptx

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
figure); Part B simulator, traffic model, five reference controllers, forecast
pipeline with separate training / validation / test seeds, proposed controller
with a feasibility proof, tuning on validation seeds, 200-run main comparison,
seed-by-seed analysis, interval sweep, ablations (single number vs range, ML
vs simple quantiles, calibration on/off), the A + B compression experiment,
figures, presentation.

Not done (future work): restore the Part A `src/` package into the repository
and re-run Exp 1-4; benchmark inversion on realistic channel matrices; make the
compression width a second knob of the allocation rule; real or public traffic
traces; a skill-weighted mix of trained and simple quantiles as the fallback;
a switch-level packet queue; uplink; more seeds; a compiled implementation of
the decision (currently 3.2 ms in Python).
