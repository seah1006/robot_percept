#!/bin/bash
# usage: run_cand.sh TAG parts   (hash sim/web humanoid sources, then measure)
cd /home/user/work/robot_percept
md5sum sim/humanoid_*.py web/humanoid*.py > bench/verify_s/hash_$1.txt
bash bench/verify_s/measure.sh $1 $2 2>&1 | grep -v "^{'pose'" | tee bench/verify_s/log_$1.txt
