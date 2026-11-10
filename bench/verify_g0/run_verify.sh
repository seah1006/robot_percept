#!/usr/bin/env bash
cd /home/my/work/robot_percept
source ~/miniforge3/etc/profile.d/conda.sh
V=bench/verify_g0
T=/mnt/c/Users/my/.aside/u/0/sessions/2026-11-10_C2eSNBuQGeoBYteD/tmp
conda activate robot_percept_rocm
export HSA_ENABLE_DXG_DETECTION=1 PYTHONUNBUFFERED=1
echo "== probe WITHOUT LD_LIBRARY_PATH" > $V/probe_nold.log
timeout 60 python tools/g0/probe_gpu.py >> $V/probe_nold.log 2>&1; echo "rc=$?" >> $V/probe_nold.log
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 60 python tools/g0/probe_gpu.py > $V/probe.log 2>&1; echo "rc=$?" >> $V/probe.log
pip freeze | grep -E "^(torch|numpy|transformers)" > $V/rocm_numpy.log
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 285 python $T/bench_gpu.py --n 20 --output $V/rocm_gpu.json > $V/rocm_gpu.log 2>&1; echo "rc=$?" >> $V/rocm_gpu.log
conda deactivate
conda activate robot_percept_cpu
echo "env=$CONDA_DEFAULT_ENV" > $V/cpu.log
pip freeze | grep -E "^(torch|numpy|transformers)" >> $V/cpu.log
echo "load=$(cat /proc/loadavg)" >> $V/cpu.log
flock -w 900 /tmp/rp_measure.lock timeout 285 python tools/g0/bench_cpu.py --threads 4 --n 20 --output $V/cpu.json >> $V/cpu.log 2>&1; echo "rc=$?" >> $V/cpu.log
echo DONE > $V/done.flag
