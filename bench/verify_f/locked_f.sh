#!/bin/bash
# 사용: locked_f.sh <kind> <라벨>
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 290 bash ~/work/robot_percept/bench/verify_f/run_f.sh "$@"
