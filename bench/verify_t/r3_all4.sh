#!/bin/bash
B=$HOME/work/robot_percept/bench/verify_t
flock -w 3000 /tmp/rp_measure.lock timeout 280 bash $B/r3_cam_run.sh cam2 humanoid; echo "cam2 rc=$?"
bash $B/r3_chain.sh fh4 teleop_final_hand humanoid
flock -w 1800 /tmp/rp_measure.lock timeout 290 bash $B/r3_rec_one.sh rec3 25 56 100; echo "rec3 rc=$?"
echo ALL4_DONE
