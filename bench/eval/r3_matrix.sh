#!/usr/bin/env bash
set -eo pipefail
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
set -u
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1
export RP_E_CONCURRENT_CONTEXT="${RP_E_CONCURRENT_CONTEXT:-}"
exec python -m eval.r3_batch "$@"