#!/bin/bash
# usage: r3_srv_job.sh TREE TAG "ENV=.. ENV2=.." PARTS  -- own server on 5094 from TREE under the measure lock (<=295s)
TREE=$1; TAG=$2; ENVS=$3; PARTS=$4
R=/home/user/work/robot_percept
inner() {
  echo "locked $(date +%T) load $(cat /proc/loadavg) tag=$TAG tree=$TREE gpu $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader) others: $(ps -eo pid,pcpu,cmd --sort=-pcpu | sed -n 2,4p | cut -c1-90 | tr '\n' '|')"
  source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
  cd $R; source sim_test/gl_env.sh; cd $TREE; mkdir -p bench/verify_s
  HOST=0.0.0.0 PYTHONPATH=$TREE PORT=5094 PERCEPTION=stub setsid python -m web.app > /tmp/vs3r3_server_$TAG.log 2>&1 &
  for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:5094/humanoid/status && break; sleep 1; done
  env $ENVS RADII_MM=118,53,45,57 python $R/bench/verify_s/r3_base_s.py http://127.0.0.1:5094 $TAG $PARTS 2>&1 | grep -v "^{.pose" | cut -c1-700
  cp bench/verify_s/out_$TAG.json $R/bench/verify_s/ 2>/dev/null
  pid=$(ss -ltnp | grep ":5094 " | grep -o "pid=[0-9]*" | head -1 | cut -d= -f2); [ -n "$pid" ] && kill $pid
  sleep 3; ss -ltnp | grep ":5094 " || echo "5094 closed"
  echo "unlocked $(date +%T) load $(cat /proc/loadavg)"
}
export -f inner; export TREE TAG ENVS PARTS R
flock -w 900 /tmp/rp_measure.lock timeout 295 bash -c inner 2>&1 | tee $R/bench/verify_s/log_$TAG.txt
