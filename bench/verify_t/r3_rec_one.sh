#!/bin/bash
# usage: r3_rec_one.sh <label> <bs> <be> <secs>   single recovery scenario (worst-case phase), server 5092. Run under measure lock.
L=$1; BS=$2; BE=$3; SECS=$4; R=$HOME/work/robot_percept; B=$R/bench/verify_t; O=$B/out_r3/$L; PORT=5092
bash $B/r3_sync.sh
mkdir -p $O
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd $R; source sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
if ss -ltn | grep -q ":$PORT "; then echo "5092 occupied"; exit 1; fi
python -m web.app > $O/server.log 2>&1 & SP=$!
for i in $(seq 80); do curl -s localhost:$PORT/status >/dev/null && break; sleep 0.5; done
curl -s -X POST -H 'Content-Type: application/json' -d '{"enabled":true}' localhost:$PORT/humanoid/mode >/dev/null; sleep 8
TRK='C:\Users\USER\AppData\Local\Temp\vt3\teleop_tracker_win.py'; VID='C:\Users\USER\Documents\sam_camera\teleop_final_hand.mp4'; WO='C:\Users\USER\AppData\Local\Temp\vt3_rec'
WPS='C:\Users\USER\AppData\Local\Temp\vt3\bin\r3_rec_win.ps1'
echo "tracker_sha=$(sha256sum "$(wslpath "$TRK")" | cut -c1-16) git=$(git rev-parse --short HEAD) load=$(cut -d' ' -f1-3 /proc/loadavg)" > $O/env.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WPS" -Server http://127.0.0.1:$PORT -Out "$WO\\$L" -Tracker "$TRK" -Video "$VID" -Bs $BS -Be $BE -Secs $SECS -Label $L
bash $B/r3_sync.sh
mkdir -p $O/win; cp -r /mnt/c/Users/USER/AppData/Local/Temp/vt3_rec/$L/* $O/win/
grep -c "tracker/ws" $O/server.log >> $O/env.txt
kill $SP 2>/dev/null; sleep 4; [ -d /proc/$SP ] && kill -9 $SP
echo "post_listener=$(ss -ltn | grep -c ":$PORT ") leftover=$(ps -eo args | grep -E 'web\.app|multiprocessing' | grep -v grep | wc -l)" >> $O/env.txt
cat $O/env.txt
