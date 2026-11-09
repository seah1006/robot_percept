#!/bin/bash
# usage: r3_chain.sh <tag> <video-basename> <mode> ; runs pair slots A(http,ws,http,ws) then B(ws,http) each under the measure lock (<=5min)
TAG=$1; V=$2; MODE=${3:-humanoid}; B=$HOME/work/robot_percept/bench/verify_t
VID="C:\\Users\\USER\\Documents\\sam_camera\\$V.mp4"; TRK='C:\Users\USER\AppData\Local\Temp\vt3\teleop_tracker_win.py'
for part in "A http,ws,http,ws" "B ws,http"; do
  set -- $part
  flock -w 1800 /tmp/rp_measure.lock timeout 290 bash $B/r3_run.sh ${TAG}_$1 30 $2 "$VID" $MODE "$TRK"
  echo "chain ${TAG}_$1 rc=$?"
done
