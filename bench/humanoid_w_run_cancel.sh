#!/usr/bin/env bash
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export PYTHONPATH=$PWD RP_GPU_SERIALIZE=0 RP_PERCEPTION_WARMUP=0
export RP_WARMUP_DEFER_TEST=0 RP_WARMUP_START_THEN_G1=1 RP_PERCEPTION_NICE=10 RP_PERCEPTION_CPU_THREADS=1
export RP_WARMUP_GUARD_ONLY=${RP_WARMUP_GUARD_ONLY:-0}
export RP_WARMUP_TAG=${RP_WARMUP_TAG:-cancel_repeat}
if ss -ltn 'sport = :5091' | grep -q ':5091'; then echo '5091 occupied, refusing'; exit 1; fi
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash -c '
 date; uptime; nvidia-smi
 timeout --signal=INT --kill-after=10s 285s python bench/humanoid_w_warmup.py > "notes/humanoid_w_${RP_WARMUP_TAG}_result.json"
 code=$?
 nvidia-smi
 exit "$code"
' > "notes/humanoid_w_${RP_WARMUP_TAG}_env.txt" 2>&1