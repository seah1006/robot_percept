#!/bin/bash
# asym with reset between runs and long settle (history/local-minimum check)
cd /home/user/work/robot_percept
RESET=1 SETTLE=6 bash bench/verify_s/measure.sh cand1_dbg asym 2>&1 | grep -v "^{'pose'" | tee bench/verify_s/log_cand1_dbg.txt
