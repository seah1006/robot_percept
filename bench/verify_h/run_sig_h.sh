#!/bin/bash
# usage: run_sig_h.sh <ROOT> <TAG> <N> [SEED]
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $1; source sim_test/gl_env.sh
uptime
ROOT=$1 TAG=$2 N=$3 SEED=${4:-1} flock -w 900 /tmp/rp_measure.lock timeout 290 python ~/work/robot_percept/bench/verify_h/sig_h.py > ~/work/robot_percept/bench/verify_h/sig_h_$2.log 2>&1
tail -1 ~/work/robot_percept/bench/verify_h/sig_h_$2.log; uptime; ss -ltnp | grep 5092; echo listener_done
