# Fronthaul Load Management (BTP) — shared O-RAN 7-2x fronthaul, uncertainty-aware budget coordination

This repository contains a research prototype for **fronthaul load management**:
N O-RAN split 7-2x cells share one packet-switched fronthaul aggregation link
that is deliberately oversubscribed (statistical multiplexing). A coordinator
decides, once per control interval, how much of the link each cell may use.
The prototype implements a slot-level simulator, four baselines, an oracle, a
gradient-boosted **quantile** forecaster of each cell's *deadline-feasible*
fronthaul rate, and the proposed **uncertainty-aware KKT allocation rule**, plus
the experiment pipeline, tests and the mid-evaluation presentation.

Everything in `fhlm/`, `tests/`, `docs/fhlm/`, `results/fhlm/` and
`models/fhlm_*` was built for this. The pre-existing `matinv_bench/` (matrix
inversion timing benchmark) and the older `docs/`, `experiments/` and
`results/figures` files are kept untouched as historical material; note that
`experiments/exp*.py` import a `src/` package that is not present in the
repository, so those scripts are not runnable as committed.

## Repository layout (new work)

| Path | Purpose |
|---|---|
| `fhlm/config.py` | Network / traffic / control configuration and derived fronthaul constants (bits per PRB-layer, link capacity per slot) |
| `fhlm/traffic.py` | Synthetic traffic generator (Gamma background + heavy-tailed ON/OFF bursts + regimes + SE drift) |
| `fhlm/demand.py` | Deadline-feasible rate r*(a, D) and backlog-rate conversion |
| `fhlm/simulator.py` | Slot-level simulator: age-tracked DU queues, budgets, capacity constraint, violation accounting, metrics |
| `fhlm/controllers.py` | Baselines: static equal share, reactive proportional, deadline-aware reactive, point-forecast water-fill, oracle |
| `fhlm/forecast.py` | Feature construction, dataset builder, GBM quantile forecaster, window-quantile reference, forecast metrics |
| `fhlm/proposed.py` | Proposed controller: quantile forecasts -> constrained-newsvendor / KKT allocation (+ optional online calibration) |
| `fhlm/scenarios.py` | Scenario definitions and disjoint train / validation / test seed ranges |
| `fhlm/train.py` | Trains the forecaster on training seeds, reports validation quality |
| `fhlm/run_experiments.py` | `tune`, `main`, `sweep`, `demo` commands; writes raw JSON + CSV summaries |
| `fhlm/make_figures.py` | Generates the figures used in the slides from saved results |
| `fhlm/make_slides.py` | Builds the editable mid-evaluation deck (`.pptx`, speaker notes) from the saved results |
| `tests/test_fhlm.py` | 13 tests: capacity compliance, non-negative queues, accounting, zero load, overload, reproducibility, r* tightness, KKT properties, no-future-leakage, compiled-GBM equality |
| `docs/fhlm/` | `method.md` (system model, formulation, propositions), `literature_review.md`, `results_summary.md`, `presentation_notes.md` (opening, demo script, Q&A), `BTP_midterm_fronthaul_load_management.pptx` / `.pdf` |
| `results/fhlm/` | Raw per-run metrics (`raw/*.json`), summaries (`*.csv`, `tuning.json`), forecast reports, `figures/` |
| `models/fhlm_quantile_gbm_T20_d2.pkl` | Trained quantile forecaster for the default interval (the sweep retrains T = 4/10/40 automatically, ~1-2 min each) |

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # numpy, scipy, pandas, matplotlib, scikit-learn, pytest, python-pptx
```

CPU only. Measured on a 4-core VM: tests 6 s, training 25 s, tuning 90 s, main
comparison 135 s, interval sweep ~6 min (includes training three forecasters),
figures + slides 10 s. Peak memory < 4 GB (the T = 4 forecaster).

## Exact commands

```bash
# 1. tests (~15 s)
python -m pytest tests/test_fhlm.py -q

# 2. train the quantile forecaster on TRAIN seeds, validate on VAL seeds (~25 s)
python -m fhlm.train --out models/fhlm_quantile_gbm_T20_d2.pkl --report results/fhlm/forecast_training_T20_d2.json

# 3. tune baseline margins/windows and the ACI rate on VALIDATION seeds (never on test)
python -m fhlm.run_experiments tune

# 4. main comparison: 8 controllers x 5 scenarios x 5 test seeds, identical traces (+ paired analysis)
python -m fhlm.run_experiments main

# 5. control-interval sweep (trains a forecaster per interval automatically)
python -m fhlm.run_experiments sweep --intervals 4 10 20 40 --num-seeds 3

# 6. single demonstration run with time series (used for the demo figure)
python -m fhlm.run_experiments demo --scenario high

# 7. figures for the slides
python -m fhlm.make_figures

# 8. rebuild the presentation from the saved results (PDF: soffice --headless --convert-to pdf docs/fhlm/*.pptx)
python -m fhlm.make_slides
```

A 30-second demonstration: `python -m fhlm.run_experiments demo --scenario high --slots 6000`.

## Architecture in one paragraph

Traffic is exogenous (`traffic.py`) and identical for every controller of a
comparison. The simulator (`simulator.py`) advances slot by slot: arrivals join
age-tracked DU queues, every T slots it builds an `Observation` containing only
information that is tau slots old, asks the controller for budgets, projects
them onto {sum r_i <= C_u, r_i <= cap_i}, then serves each queue FIFO within
its budget and air-interface cap, drops bits that exceeded their deadline and
records metrics. Controllers (`controllers.py`, `proposed.py`) are pure
functions of the observation; the forecast-based ones call a
`QuantileGBMForecaster` (`forecast.py`) trained offline on training seeds.

## What is done / what is not

Done and tested: simulator, traffic model, five baselines + oracle, forecasting
pipeline (train/validation/test separation, no data-fitted preprocessing),
proposed controller with feasibility guarantee, tuning on validation seeds,
main comparison over 5 scenarios x 5 seeds, interval sweep, ablations (point vs
quantile, ML vs window quantiles, calibration on/off), figures, presentation.

Headline result (test seeds, priority-weighted deadline-violation ratio, paired
on identical traces): the proposed rule beats the point-forecast controller by
10-53 % and the deadline-aware reactive controller by 18-79 % on 5/5 seeds in
every scenario including the held-out shift; it is a tie with the plain
proportional controller under flash crowds (3/5), loses to it when budgets are
held for 20 ms, gains little from the ML forecaster under shift, and online ACI
calibration did not help. See `docs/fhlm/results_summary.md`.

Not done (future work): real or public traffic traces; skill-weighted
GBM/window blend as the fallback (replacing ACI); adaptive compression as a
second lever; switch-level packet queue and T2a window; uplink direction; more
seeds; a compiled implementation of the decision (currently 3.2 ms in Python).

## Historical material (not part of the current work)

`matinv_bench/` and `REPORT.md` describe an earlier matrix-inversion timing
benchmark; `docs/mid_evaluation_*.md|html` and `experiments/exp*.py` refer to a
CSEE/RAS-BFP/ACAFS compression study whose source package (`src/`) is not in
this repository. They are left unchanged.
