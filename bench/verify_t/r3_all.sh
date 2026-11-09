#!/bin/bash
# sequential driver: each part takes the measure lock itself (<=290s)
B=$HOME/work/robot_percept/bench/verify_t
bash $B/r3_chain.sh fh2 teleop_final_hand humanoid
flock -w 1800 /tmp/rp_measure.lock timeout 290 bash $B/r3_rec_run.sh rec1; echo "rec1 rc=$?"
bash $B/r3_chain.sh cp teleop_round2_compact humanoid
bash $B/r3_chain.sh pd teleop_final_hand panda
echo ALL_DONE
