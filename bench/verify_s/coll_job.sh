#!/bin/bash
# usage: coll_job.sh TAG  -- patterns chest,jump,twist x collision off/on (one lock hold <=295s)
TAG=$1
cd /home/user/work/robot_percept
md5sum sim/humanoid_*.py web/humanoid*.py > bench/verify_s/hash_$TAG.txt
git hash-object sim/humanoid_env.py sim/humanoid_teleop.py sim/humanoid_collision.py sim/humanoid_ik.py >> bench/verify_s/hash_$TAG.txt
inner() {
  echo "locked at $(date +%T) load $(cat /proc/loadavg) gpu $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader)"
  setsid bash bench/verify_s/server.sh /home/user/work/robot_percept > /tmp/vs_server_$TAG.log 2>&1 &
  for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:5094/humanoid/status && break; sleep 1; done
  source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; export PYTHONPATH=$PWD
  for pat in ${PATS:-chest jump twist}; do
    COLLPAT=$pat python bench/verify_s/base_s.py http://127.0.0.1:5094 ${TAG}_$pat coll0,coll1 2>&1 | grep -E "^.n.: |DONE|Traceback|Error"
  done
  bash bench/verify_s/kill5094.sh
  echo "unlocked load $(cat /proc/loadavg) gpu $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader)"
}
export -f inner; export TAG
flock -w 900 /tmp/rp_measure.lock timeout 295 bash -c inner 2>&1 | tee bench/verify_s/log_$TAG.txt
