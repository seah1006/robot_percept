#!/bin/bash
# usage: run.sh <mode>  (측정 락 안에서 실행, 5096만)
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; source sim_test/gl_env.sh
export PYTHONPATH=/home/user/work/robot_percept
mkdir -p bench/verify_k/out
echo "load: $(cat /proc/loadavg)" 
flock -w 900 /tmp/rp_measure.lock timeout 115 python bench/verify_k/vk_live.py "$1" > bench/verify_k/out/$1.log 2>&1
echo exit=$?
grep '^RESULT' bench/verify_k/out/$1.log | sed 's/^RESULT //' > bench/verify_k/out/$1.json
cat bench/verify_k/out/$1.json | head -c 6000; echo
grep -v '^RESULT' bench/verify_k/out/$1.log | tail -5
echo "residual:"; ps -eo pid,cmd | grep -E 'vk_live|spawn_main|resource_tracker' | grep -v grep; ss -ltnp | grep 5096 || echo "port free"
