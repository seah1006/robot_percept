#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/../.."
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept_g0c
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
export HSA_ENABLE_DXG_DETECTION=1
source sim_test/gl_env.sh
export PYTHONPATH="$PWD:$PWD/FoundationPose:$PWD/FoundationPose/mycpp/build:${PYTHONPATH:-}"
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 280 python tools/g0/bench_gpu.py "$@"