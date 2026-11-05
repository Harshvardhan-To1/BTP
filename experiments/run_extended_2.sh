#!/usr/bin/env bash
# Second extended-study pass: the tuned-LL-weight KKT variant (proposed_tw) and the policy-search controller in
# the sweeps. Run after experiments/run_extended.sh from the repository root:
#     bash experiments/run_extended_2.sh
set -euo pipefail
cd "$(dirname "$0")/.."
R=results/fhlm
W=${WORKERS:-4}
step() { echo "=== $(date -u +%H:%M:%S) $*"; }

step tune-tw-S;    python3 -m fhlm.run_experiments tune --family synthetic --methods proposed_tw --workers $W > $R/ext2_tune_S.log 2>&1
step tune-tw-G;    python3 -m fhlm.run_experiments tune --family 3gpp      --methods proposed_tw --workers $W > $R/ext2_tune_G.log 2>&1
step tune-tw-M;    python3 -m fhlm.run_experiments tune --family markov    --methods proposed_tw --workers $W > $R/ext2_tune_M.log 2>&1
step main-tw-S;    python3 -m fhlm.run_experiments main --family synthetic --methods proposed_tw --append --workers $W > $R/ext2_main_S.log 2>&1
step main-tw-G;    python3 -m fhlm.run_experiments main --family 3gpp      --methods proposed_tw --append --workers $W > $R/ext2_main_G.log 2>&1
step main-tw-M;    python3 -m fhlm.run_experiments main --family markov    --methods proposed_tw --append --workers $W > $R/ext2_main_M.log 2>&1
step sweep-2;      python3 -m fhlm.run_experiments sweep --methods cem_policy proposed_tw --num-seeds 10 --append --workers $W > $R/ext2_sweep.log 2>&1
step delay-2;      python3 -m fhlm.run_experiments delay --methods cem_policy proposed_tw --num-seeds 10 --append --workers $W > $R/ext2_delay.log 2>&1
step weights-2;    python3 -m fhlm.run_experiments weights --methods cem_policy proposed_tw --scenarios high tgpp_high mm_high --num-seeds 20 --append --workers $W > $R/ext2_weights.log 2>&1
step compression-2; python3 -m fhlm.run_experiments compression --scenario moderate --methods cem_policy proposed_tw --num-seeds 10 --append --workers $W > $R/ext2_compression.log 2>&1
step done
