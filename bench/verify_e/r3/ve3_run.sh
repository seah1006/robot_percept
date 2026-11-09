#!/usr/bin/env bash
# usage: ve3_run.sh {defer|cancel|protect} TAG   (V-E3, port 5084, measure->gpu double lock, <=285s)
MODE=$1; TAG=$2
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export HOST=127.0.0.1 PORT=5084 PYTHONPATH=$PWD PERCEPTION=fp
OUT=bench/verify_e/r3/out; mkdir -p $OUT
if ss -ltn 'sport = :5084' | grep -q ':5084'; then echo '5084 occupied'; exit 1; fi
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash -c '
 date; uptime; nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv; ps aux --sort=-%cpu | head -6
 python -m web.app > '$OUT'/server_'$TAG'.log 2>&1 &
 SP=$!
 timeout 270 python bench/verify_e/r3/ve3_warm.py '$MODE' $SP '$OUT'/'$MODE'_'$TAG'.json
 echo rc=$?
 kill -INT $SP; for i in $(seq 1 15); do kill -0 $SP 2>/dev/null || break; sleep 1; done
 kill -0 $SP 2>/dev/null && { echo "server still alive after 15s: killing pid $SP"; kill -9 $SP; }
 sleep 1; ss -ltnp | grep :5084 || echo "5084 closed"
 date; uptime
' > $OUT/env_${MODE}_${TAG}.txt 2>&1