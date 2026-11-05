#!/bin/bash
# usage: cand_job.sh TAG parts  -- under the measure lock (<=295s): start own 5094 server, run base_s, kill only own server
TAG=$1; PARTS=$2
cd /home/user/work/robot_percept
md5sum sim/humanoid_*.py web/humanoid*.py > bench/verify_s/hash_$TAG.txt
inner() {
  echo "locked at $(date +%T) load $(cat /proc/loadavg) gpu $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader)"
  setsid bash bench/verify_s/server.sh /home/user/work/robot_percept > /tmp/vs_server_$TAG.log 2>&1 &
  for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:5094/humanoid/status && break; sleep 1; done
  source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; export PYTHONPATH=$PWD
  python bench/verify_s/base_s.py http://127.0.0.1:5094 $TAG $PARTS 2>&1 | grep -v "^{'pose'"
  bash bench/verify_s/kill5094.sh
  echo "unlocked load $(cat /proc/loadavg) gpu $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader)"
}
export -f inner; export TAG PARTS
flock -w 900 /tmp/rp_measure.lock timeout 295 bash -c inner 2>&1 | tee bench/verify_s/log_$TAG.txt
