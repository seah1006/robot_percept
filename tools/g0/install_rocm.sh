#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source ~/miniforge3/etc/profile.d/conda.sh
mkdir -p bench/g0
# A single invocation is bounded below 2h; each compute slot <=280s.
START=$(date +%s)
if [[ ! -x ~/miniforge3/envs/robot_percept_rocm/bin/python ]]; then
 flock -w 900 /tmp/rp_measure.lock timeout 280 conda create -y -n robot_percept_rocm python=3.12 pip
fi
conda activate robot_percept_rocm
[[ "$CONDA_DEFAULT_ENV" == robot_percept_rocm ]]
export HSA_ENABLE_DXG_DETECTION=1
flock -w 900 /tmp/rp_measure.lock timeout 280 python -m pip install --index-url https://stable.repo.amd.com/rocm/whl-next/ -c notes/constraints/rocm.txt 'torch[device-gfx1102]==2.14.0+rocm10.1.0' > bench/g0/install_rocm.log 2>&1
(( $(date +%s)-START < 7200 )) || exit 124
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 60 python tools/g0/probe_gpu.py > bench/g0/gpu_probe.log 2>&1
