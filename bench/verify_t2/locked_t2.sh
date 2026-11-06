#!/bin/bash
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 300 bash ~/work/robot_percept/bench/verify_t2/run_t2.sh "$@"
