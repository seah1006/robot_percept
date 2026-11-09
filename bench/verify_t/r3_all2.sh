#!/bin/bash
B=$HOME/work/robot_percept/bench/verify_t
flock -w 1800 /tmp/rp_measure.lock timeout 290 bash $B/r3_rec_run.sh rec2; echo "rec2 rc=$?"
flock -w 1800 /tmp/rp_measure.lock timeout 200 bash $B/r3_panda_base.sh pdbase; echo "pdbase rc=$?"
bash $B/r3_chain.sh fh3 teleop_final_hand humanoid
echo ALL2_DONE
