#!/usr/bin/env bash
# Extended-study experiment pipeline (adds the new controllers and the Markov-modulated family to the
# existing results without re-running what is already there). Run from the repository root:
#     bash experiments/run_extended.sh
# Every step logs to results/fhlm/ext_<step>.log and is idempotent (append mode).
set -euo pipefail
cd "$(dirname "$0")/.."
R=results/fhlm
W=${WORKERS:-4}
NEW="pred_maxweight cem_policy eb_kkt markov_kkt proposed_vc"
step() { echo "=== $(date -u +%H:%M:%S) $*"; }

step tune-new-S;   python3 -m fhlm.run_experiments tune --family synthetic --methods pred_maxweight markov_kkt eb_kkt --workers $W > $R/ext_tune_S.log 2>&1
step tune-new-G;   python3 -m fhlm.run_experiments tune --family 3gpp      --methods pred_maxweight markov_kkt eb_kkt --workers $W > $R/ext_tune_G.log 2>&1
step tune-M;       python3 -m fhlm.run_experiments tune --family markov    --workers $W > $R/ext_tune_M.log 2>&1
step cem-S;        python3 -m fhlm.run_experiments cem --family synthetic --num-seeds 4 --workers $W > $R/ext_cem_S.log 2>&1
step cem-G;        python3 -m fhlm.run_experiments cem --family 3gpp      --num-seeds 4 --workers $W > $R/ext_cem_G.log 2>&1
step cem-M;        python3 -m fhlm.run_experiments cem --family markov    --num-seeds 4 --workers $W > $R/ext_cem_M.log 2>&1
step main-S-new;   python3 -m fhlm.run_experiments main --family synthetic --methods $NEW --append --workers $W > $R/ext_main_S.log 2>&1
step main-G-new;   python3 -m fhlm.run_experiments main --family 3gpp      --methods $NEW --append --workers $W > $R/ext_main_G.log 2>&1
step main-M;       python3 -m fhlm.run_experiments main --family markov    --append --workers $W > $R/ext_main_M.log 2>&1
step main-M-ref;   python3 -m fhlm.run_experiments main --family markov    --methods markov_oracle_kkt proposed_transfer --append --workers $W > $R/ext_main_M_ref.log 2>&1
step sweep-new;    python3 -m fhlm.run_experiments sweep --methods pred_maxweight markov_kkt --num-seeds 10 --append --workers $W > $R/ext_sweep.log 2>&1
step delay-new;    python3 -m fhlm.run_experiments delay --methods pred_maxweight markov_kkt --num-seeds 10 --append --workers $W > $R/ext_delay.log 2>&1
step weights-new;  python3 -m fhlm.run_experiments weights --methods pred_maxweight --scenarios high tgpp_high mm_high --num-seeds 20 --append --workers $W > $R/ext_weights.log 2>&1
step weights-M;    python3 -m fhlm.run_experiments weights --methods reactive_prop maxweight queue_aware point_forecast proposed oracle oracle_kkt --scenarios mm_high --num-seeds 20 --append --workers $W > $R/ext_weights_M.log 2>&1
step compression-new; python3 -m fhlm.run_experiments compression --methods pred_maxweight --num-seeds 10 --append --workers $W > $R/ext_compression.log 2>&1
step theory;       python3 -m fhlm.theory_validation > $R/ext_theory.log 2>&1
step done
