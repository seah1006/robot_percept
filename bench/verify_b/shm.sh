#!/bin/bash
G=$HOME/work/robot_percept/bench/verify_g
for TREE in /tmp/rp_vg_base /tmp/rp_g_snap; do
  b=$(ls /dev/shm | grep -c '^psm_')
  SIGS="KILL" flock -w 900 /tmp/rp_measure.lock bash $G/repro_mono.sh $TREE $G/out/shm_$(basename $TREE) 3 >/dev/null 2>&1
  a=$(ls /dev/shm | grep -c '^psm_')
  echo "$TREE KILL x(ON3+OFF3): psm before=$b after=$a new=$((a-b))"
done
