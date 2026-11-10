# Fronthaul Load Management (B.Tech. Project)

The fronthaul is the link between a radio unit on the tower (O-RU) and the
processing unit (O-DU). In the O-RAN 7-2x split it carries raw radio samples,
so it is one of the most loaded links in a mobile network. This project looks at
the two ways to manage that load:

* **Part A: make the data smaller.** Compress the per-slot IQ matrix using its
  structure (matrix decomposition: truncated SVD, a randomised sketch + QR
  low-rank encoder, delay-domain sparsity), and measure how fast the matrix
  operations behind it (LU, QR, SVD, Newton-Schulz, learned inverters) run on a
  CPU. This part was done earlier in the project.
* **Part B: share one link well.** Several cells share a link that is smaller
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
* Part B on standards-based traffic (second, independent family: 3GPP
  TR 38.901 urban-macro channel, TS 38.214 link adaptation, FTP Model 3 and
  XR video traffic, fronthaul demand = output of a PRB scheduler; own
  forecaster, own tuning, 20 test seeds): the proposed rule is again the best
  real controller at both loads (-11 % vs the point forecast, -31 % vs the
  deadline-aware reactive controller, -50 % vs reactive proportional at load
  0.80, 20/20 seeds each) and here also under the unweighted ratio. A
  forecaster trained on the synthetic family and applied unchanged to 3GPP
  traffic still beats every reactive controller but not the in-family point
  forecast. The "oracle + KKT" reference (same rule, perfect forecast) shows
  that 24-40 % of the proposed rule's remaining loss at high load is forecast
  error.
* Honest caveat on the metric: the gain is a priority trade. Under the
  unweighted violation ratio the plain proportional controller loses fewer
  total bits at high load in the synthetic family; the LL-weight sweep
  (`weights` command) shows where the crossover is.
* A + B (same user traffic, BFP width 6 / 9 / 12 / 14 bits -> load 0.44 / 0.65 /
  0.86 / 0.99): at 0.44 almost nothing is lost whatever the rule; at 0.65 the
  proposed rule loses about half as much as the reactive controllers; at 0.86
  the proportional controller is slightly better; at 0.99 no allocation rule
  helps. Compression sets the regime; allocation helps most between ~0.5 and
  ~0.8 load.

* Extended study (after the NCC submission; journal-length manuscript in
  `paper/extended/`, 11 pages): the control problem is written as a
  finite-horizon MDP on deadline-constrained queues; for Markov-modulated
  fluid traffic a Chernoff-union tail bound on the deadline-feasible rate, its
  effective-bandwidth decay rate and a pathwise "shortfall sandwich" are
  proved and validated (bounds valid but 25-100x conservative at 2-10 ms
  deadlines); a third traffic family (Markov-modulated Gamma sources with a
  semi-Markov held-out shift) and seven controllers are added. Result, stated
  plainly: within the NCC comparison set the KKT rule still wins all 10
  scenarios and is the best controller with nothing to tune, but two
  controllers that use the same forecaster beat it: a three-parameter policy
  learned from reward (cross-entropy method) is best in 6/10 scenarios
  (e.g. 7.17 % vs 8.01 % on 3GPP high load, 3.93 % vs 4.94 % on Markov high
  load), predictive MaxWeight (forecast median + queues, no deadline model) in
  3/10, all on the bursty synthetic family (6.15 % vs 8.00 % at high load),
  and the KKT rule with one tuned weight in 1/10. Re-tuning the LL weight
  inside the KKT rule gains only 1-4 %, because at high load the KKT
  multiplier saturates at the eMBB weight in half of the intervals; the gap
  is structural. A Markov chain fitted online, with no training data, is
  within 3-9 % of the learned rule. Short control interval (<= 5 ms) ->
  reservation; 10-20 ms with short bursts -> back-pressure; long bursts ->
  reservation at every interval. Details: `docs/fhlm/extended_study.md`.

Details: `docs/fhlm/results_summary.md`. Paper (IEEE conference format,
every number generated from the CSVs): `paper/main.tex`, `paper/main.pdf`;
reviewer-style assessment of what was missing and what was added:
`docs/fhlm/review_and_response.md`.

Submission target: NCC 2027 (IISc Bengaluru, 17-20 Feb 2027), Networks track.
Rules checked against the CFP on 17 Oct 2026: six double-column IEEE pages
including references, double-blind (no author names, affiliations or
identifying links in the PDF), CMT submission, deadline 31 Oct 2026 23:59 IST
(firm), notification 24 Dec 2026, camera-ready 8 Jan 2027. The PDF in `paper/`
is anonymised; the author block and the repository link go back in at
camera-ready.

## Repository layout

| Path | Part | Purpose |
|---|---|---|
| `fhlm/config.py` | B | Units, 7-2x fronthaul constants (bits per PRB-layer incl. BFP width), cells, link |
| `fhlm/traffic.py` | B | Synthetic traffic family: smooth part + heavy-tailed ON/OFF bursts + slow load changes + spectral-efficiency drift; dispatches to the 3GPP family and caches its traces |
| `fhlm/traffic_3gpp.py` | B | Standards-based traffic family: 3GPP TR 38.901 UMa channel (best server of 7 sites, shadowing, Jakes-correlated Rayleigh fading), TR 36.942 / TS 38.214 link adaptation, FTP Model 3 (TR 36.814) for eMBB cells, XR video (TR 38.838) for low-latency cells, per-cell round-robin PRB scheduler; fronthaul demand = scheduled PRB-layers x BFP bits |
| `fhlm/demand.py` | B | Deadline-feasible rate r*(arrivals, deadline) and backlog rate |
| `fhlm/simulator.py` | B | Slot loop: queues with ages, budgets, link constraint, drops, metrics |
| `fhlm/controllers.py` | B | Reference controllers: static equal share, reactive proportional, MaxWeight, deadline-aware reactive, point-forecast water-fill, fixed-global-quantile water-fill, oracle water-fill |
| `fhlm/forecast.py` | B | Features, quantile gradient boosting, fast tree evaluation, simple window quantiles |
| `fhlm/proposed.py` | B | Proposed controller: forecast quantiles -> KKT allocation rule (+ optional online calibration) |
| `fhlm/scenarios.py` | B | Five scenarios; separate training / validation / test seed ranges |
| `fhlm/train.py` | B | Trains the forecaster on training seeds, reports validation quality |
| `fhlm/run_experiments.py` | B, A+B | `tune`, `main`, `sweep`, `delay`, `miscalibration`, `weights`, `compression`, `demo` commands (`--family 3gpp` selects the standards-based traffic family); raw JSON + CSV summaries; paired bootstrap / Wilcoxon / Holm statistics |
| `fhlm/make_figures.py`, `fhlm/make_slides.py`, `fhlm/make_paper_tables.py` | B | All figures, the editable `.pptx` deck (with speaker notes) and the paper's LaTeX tables/macros, from the saved results |
| `paper/` | B | IEEE conference paper, anonymised for double-blind review (NCC 2027 format: 6 pages incl. references, 2 figures, 4 tables). `generated/` (tables, number macros), `figures/` and `main_standalone.tex` are produced by `make_paper_tables`. For Overleaf upload either the whole `paper/` folder or `main_standalone.tex` + the `figures/` folder |
| `tests/test_fhlm.py` | B | 14 tests (link constraint, queues, accounting, zero load, overload, reproducibility, r*, KKT properties, no future leakage, fast tree evaluation, compression bridge) |
| `fhlm/traffic_markov.py`, `fhlm/theory.py`, `fhlm/theory_validation.py`, `fhlm/markov.py`, `fhlm/controllers_ext.py`, `fhlm/lambda_diagnostic.py`, `fhlm/make_extended_tables.py`, `tests/test_fhlm_extended.py` | B ext. | Extended study: Markov-modulated traffic family, Markov-fluid theory (effective bandwidth, Chernoff-union bound, shortfall sandwich) and its numerical validation, fitted-chain / bound / true-model forecasters, predictive MaxWeight and CEM policy search, KKT-multiplier diagnostic, tables and macros of `paper/extended/` (14 tests). See `docs/fhlm/extended_study.md` |
| `paper/extended/` | B ext. | Journal-length manuscript (IEEE journal format, 11 pages); `generated/` and `figures/` produced by `make_extended_tables` and `make_figures` |
| `experiments/run_extended.sh`, `experiments/run_extended_2.sh` | B ext. | The whole extended pipeline (tuning, CEM training, main runs on three families, sweeps, theory validation), append-only |
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
python -m fhlm.run_experiments main                                     # 4. controllers x 5 synthetic scenarios x 20 test seeds + paired statistics
python -m fhlm.run_experiments sweep --intervals 4 10 20 40 --num-seeds 10  # 5. control-interval sweep (retrains per interval)
python -m fhlm.run_experiments delay --delays 0 2 5 10 --num-seeds 10   # 6. telemetry-delay sweep (retrains per delay)
python -m fhlm.run_experiments miscalibration --num-seeds 10            # 7. forecast-miscalibration sweep (Proposition 4 check)
python -m fhlm.run_experiments demo --scenario high                     # 8. one run with time series (demo figure)

# Part B, standards-based traffic family (3GPP TR 38.901 UMa channel, TS 38.214 CQI, FTP-3 + XR traffic)
python -m fhlm.train --family 3gpp --out models/fhlm_quantile_gbm_T20_d2_3gpp.pkl \
       --report results/fhlm/forecast_training_T20_d2_3gpp.json          # 8a. forecaster for the 3GPP family
python -m fhlm.run_experiments tune --family 3gpp                       # 8b. tune baselines on 3GPP validation seeds
python -m fhlm.run_experiments main --family 3gpp --append \
       --methods static_equal reactive_prop maxweight queue_aware point_forecast fixed_quantile \
                 proposed_window proposed proposed_cal proposed_transfer oracle oracle_kkt   # 8c. tgpp_moderate / tgpp_high
python -m fhlm.run_experiments main --append --methods oracle_kkt       # 8d. oracle + KKT reference on the synthetic scenarios
python -m fhlm.run_experiments sweep --append --methods oracle_kkt --num-seeds 10           # 8e. ... and in the interval sweep
python -m fhlm.run_experiments weights --scenarios high tgpp_high --weights 1 2 3 5 --num-seeds 20  # 8f. LL priority-weight sweep

# A + B
python -m fhlm.run_experiments compression --scenario moderate --num-seeds 10  # 9. BFP width (6/9/12/14 bits) x allocation rule

# figures, deck, paper
python -m fhlm.make_figures                                             # 10. all figures
python -m fhlm.make_slides                                              # 11. deck; PDF: soffice --headless --convert-to pdf docs/fhlm/*.pptx
python -m fhlm.make_paper_tables && (cd paper && pdflatex main && pdflatex main)  # 12. paper tables/macros + PDF

# extended study (third family, theory, new controllers, journal manuscript)
python -m fhlm.train --family markov --out models/fhlm_quantile_gbm_T20_d2_markov.pkl --report results/fhlm/forecast_training_T20_d2_markov.json
bash experiments/run_extended.sh && bash experiments/run_extended_2.sh    # about 3 h on 4 cores
python -m fhlm.lambda_diagnostic
python -m fhlm.make_figures && python -m fhlm.make_extended_tables && (cd paper/extended && pdflatex main && pdflatex main)

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

## v2: complex-matrix inversion for split-RAN precoding

New package `cmatinv/` and `experiments_v2/` study **complex Hermitian Gram inversion for RZF precoding** under
3GPP TR 38.901 channels, with a proposed random-matrix-theory-guided warm-start inverter ("RMT-WS") and an O-RAN
fronthaul model. Read [`docs/CRITICAL_REVIEW.md`](docs/CRITICAL_REVIEW.md) for what is and is not novel, then
[`docs/NOVELTY_AND_RESULTS.md`](docs/NOVELTY_AND_RESULTS.md).

```bash
pip install numpy scipy matplotlib pandas tqdm pytest
python experiments_v2/run_all.py     # ~1 min, writes results/v2/
pytest tests
```
