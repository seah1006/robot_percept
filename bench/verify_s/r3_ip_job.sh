#!/bin/bash
# usage: r3_ip_job.sh TREE TAG "pat1 pat2" [secs]  -- in-process harness, one lock hold <=295s, OFF+ON per pattern
TREE=$1; TAG=$2; PATS=$3; SECS=${4:-24}
R=/home/user/work/robot_percept; OUTD=$R/bench/verify_s/r3raw; mkdir -p $OUTD
inner() {
  echo "locked $(date +%T) load $(cat /proc/loadavg) tag=$TAG tree=$TREE gpu $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader) others: $(ps -eo pid,pcpu,cmd --sort=-pcpu | sed -n 2,4p | cut -c1-90 | tr '\n' '|')"
  source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
  cd $R; source sim_test/gl_env.sh; cd $TREE; export PYTHONPATH=$TREE OUTD
  for p in $PATS; do for c in 0 1; do python $R/bench/verify_s/r3_inproc.py $p $c ${TAG}_${p}_c$c $SECS 2>&1 | grep -v Warning | cut -c1-700; done; done
  echo "unlocked $(date +%T) load $(cat /proc/loadavg)"
}
export -f inner; export TREE TAG PATS SECS R OUTD
flock -w 900 /tmp/rp_measure.lock timeout 295 bash -c inner 2>&1 | tee $R/bench/verify_s/log_$TAG.txt
