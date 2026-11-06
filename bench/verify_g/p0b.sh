#!/bin/bash
R=$HOME/work/robot_percept; G=$R/bench/verify_g
for i in $(seq 60); do grep -q LATE2DONE /tmp/late2_run.log && break; sleep 5; done
mkdir -p $G/out/p0b
TREE=/tmp/rp_g_snap OUTD=$G/out/p0b flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash $G/run_g.sh p0vw P0b_p0vw 2>&1 | grep -E "^done|alive_after|post_workers"
echo P0BDONE
