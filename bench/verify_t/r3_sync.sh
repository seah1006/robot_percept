#!/bin/bash
# copy harness files to a local Windows dir (UNC \\wsl.localhost reads proved unreliable); tracker must stay the frozen copy in vt3\
B=$HOME/work/robot_percept/bench/verify_t; D=/mnt/c/Users/USER/AppData/Local/Temp/vt3/bin; mkdir -p $D
cp $B/r3_win_run.ps1 $B/r3_rec_win.ps1 $B/r3_cam_win.ps1 $B/r3_recover.py $HOME/work/robot_percept/tools/camera_acceptance.py $D/
cp /mnt/c/Users/USER/AppData/Local/Temp/vt3/teleop_tracker_win.py $D/teleop_tracker_win.py
sha256sum $D/teleop_tracker_win.py | cut -c1-16