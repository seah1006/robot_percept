#!/usr/bin/env bash
set -eo pipefail
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
set -u
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 PORT=5083 PERCEPTION=fp RP_GPU_SERIALIZE=0 RP_PERCEPTION_WARMUP=0 RP_PERCEPTION_CPU_THREADS=1
mode=${1:-cancel}
out=${2:?new output directory required}
mkdir "$out"
if ss -ltn 'sport = :5083' | grep -q ':5083'; then echo '5083 occupied'; exit 1; fi
export RP_WARMUP_DEFER_TEST=0 RP_WARMUP_START_THEN_G1=0 RP_WARMUP_GUARD_ONLY=0 RP_PERCEPTION_NICE=19
case "$mode" in
 cancel) export RP_WARMUP_START_THEN_G1=1 RP_PERCEPTION_NICE=10;;
 defer) export RP_WARMUP_DEFER_TEST=1;;
 guard) export RP_WARMUP_GUARD_ONLY=1;;
 *) exit 2;;
esac
export R3_WARMUP_OUT="$out"
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash -c '
 date; uptime; nvidia-smi; ps -eo pid,pcpu,pmem,args --sort=-pcpu | head -20
 timeout --signal=INT --kill-after=10s 280s python bench/eval/r3_warmup.py > "$R3_WARMUP_OUT/result.jsonl"
 code=$?; nvidia-smi; exit "$code"
' > "$out/env.txt" 2>&1