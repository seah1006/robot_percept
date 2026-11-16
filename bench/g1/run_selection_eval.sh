#!/bin/bash
set -e
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export PYTHONPATH=/home/user/work/robot_percept
export LD_LIBRARY_PATH=/home/user/anaconda3/envs/robot_percept_g0c/lib
for ((i=0;i<450;i++)); do
  test -s bench/g1/selection_freeze.json && break
  sleep 2
done
test -s bench/g1/selection_freeze.json
for part in 0 1 2 3; do
 flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 285 /home/user/anaconda3/envs/robot_percept_g0c/bin/python bench/g1/eval_selection.py --part "$part" > /tmp/g1_selection_part${part}.log 2>&1
done
flock -w 900 /tmp/rp_measure.lock timeout 45 /home/user/anaconda3/envs/robot_percept_g0c/bin/python bench/g1/summarize_selection.py > /tmp/g1_selection_summary.log 2>&1
cat /tmp/g1_selection_summary.log
