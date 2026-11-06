#!/bin/bash
# usage: job.sh TREE TAG "ENV=.. ENV2=.." PARTS  -- own server on 5092 from TREE, under measure lock (<=295s)
TREE=$1; TAG=$2; ENVS=$3; PARTS=$4
R=$HOME/work/robot_percept; OUTD=$R/bench/verify_s3
inner() {
  echo "locked $(date +%T) load $(cat /proc/loadavg) tag=$TAG tree=$TREE"
  source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
  cd $R; source sim_test/gl_env.sh; cd $TREE
  HOST=0.0.0.0 PYTHONPATH=$TREE PORT=5092 PERCEPTION=stub setsid python -m web.app > /tmp/vs3_server_$TAG.log 2>&1 &
  for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:5092/humanoid/status && break; sleep 1; done
  export PYTHONPATH=$TREE
  env $ENVS RADII_MM=118,53,45,57 python $OUTD/base_s.py http://127.0.0.1:5092 $TAG $PARTS 2>&1 | grep -v "^{.pose" 
  pid=$(ss -ltnp | grep ":5092 " | grep -o "pid=[0-9]*" | head -1 | cut -d= -f2); [ -n "$pid" ] && kill $pid
  sleep 3; ss -ltnp | grep ":5092 " || echo "5092 closed"
  echo "unlocked $(date +%T) load $(cat /proc/loadavg)"
}
export -f inner; export TREE TAG ENVS PARTS R OUTD; export OUTD
flock -w 900 /tmp/rp_measure.lock timeout 295 bash -c inner 2>&1 | tee $OUTD/log_$TAG.txt
