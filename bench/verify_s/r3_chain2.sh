#!/bin/bash
# usage: r3_chain2.sh TREE G  -- settle=8s static, 30s-window fps for sweep/chest (monotonic mjpeg clock)
T=$1; G=$2; D=/home/user/work/robot_percept/bench/verify_s
bash $D/r3_srv_job.sh $T ${G}_stON8 "STATOPT=1 SETTLE=8" static > /dev/null 2>&1
for p in sweep chest; do bash $D/r3_srv_job.sh $T ${G}r_pat_$p "COLLPAT=$p" coll1 > /dev/null 2>&1; done
echo ALLDONE > $D/chain2_$G.done
