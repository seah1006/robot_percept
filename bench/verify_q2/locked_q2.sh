#!/bin/bash
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 290 bash ~/work/robot_percept/bench/verify_q2/run_q2.sh "$@"
