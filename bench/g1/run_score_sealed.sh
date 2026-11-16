#!/bin/bash
set -e
cd /home/user/work/robot_percept
for ((i=0;i<900;i++)); do
 if test -s bench/g1/selection_freeze_v2.json && grep -q '^complete part 3 ' /tmp/g1_selection_part3.log 2>/dev/null; then break; fi
 sleep 2
done
test -s bench/g1/selection_freeze_v2.json
grep -q '^complete part 3 ' /tmp/g1_selection_part3.log
flock -w 900 /tmp/rp_measure.lock timeout 45 /home/user/anaconda3/envs/robot_percept_g0c/bin/python bench/g1/score_sealed_v2.py > /tmp/g1_selection_v2_summary.log 2>&1
cat /tmp/g1_selection_v2_summary.log
