#!/bin/bash
# real-camera acceptance (single command, 30s) under measure lock. usage: r3_cam_run.sh <label> [mode]. Other pairs must not open the camera.
L=$1; MODE=${2:-humanoid}; R=$HOME/work/robot_percept; B=$R/bench/verify_t; O=$B/out_r3/$L; PORT=5092
bash $B/r3_sync.sh
mkdir -p $O
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd $R; source sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
if ss -ltn | grep -q ":$PORT "; then echo "5092 occupied"; exit 1; fi
bash $R/bench/verify_f/env_snap.sh before_$L > $O/env.txt
top -bn1 -w 160 | sed -n 7,12p | cut -c1-140 >> $O/env.txt
sha256sum tools/teleop_tracker_win.py | cut -c1-16 >> $O/env.txt
python -m web.app > $O/server.log 2>&1 & SP=$!
for i in $(seq 80); do curl -s localhost:$PORT/status >/dev/null && break; sleep 0.5; done
if [ "$MODE" = humanoid ]; then curl -s -X POST -H 'Content-Type: application/json' -d '{"enabled":true}' localhost:$PORT/humanoid/mode >/dev/null; else curl -s -X POST -H 'Content-Type: application/json' -d '{"enabled":true}' localhost:$PORT/teleop/mode >/dev/null; fi
sleep 8
WPS='C:\Users\USER\AppData\Local\Temp\vt3\bin\r3_cam_win.ps1'; OUTW='C:\Users\USER\AppData\Local\Temp\vt3_cam'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WPS" -Url http://127.0.0.1:$PORT -Mode $MODE -OutDir "$OUTW" -Label $L 2>&1 | tee $O/stdout.txt
cp /mnt/c/Users/USER/AppData/Local/Temp/vt3_cam/$L.json $O/ 2>/dev/null
bash $R/bench/verify_f/env_snap.sh after_$L >> $O/env.txt
kill $SP 2>/dev/null; sleep 4; [ -d /proc/$SP ] && kill -9 $SP
echo "post_listener=$(ss -ltn | grep -c ":$PORT ") leftover=$(ps -eo args | grep -E 'web\.app|multiprocessing' | grep -v grep | wc -l)" >> $O/env.txt
cat $O/env.txt; head -c 3000 $O/stdout.txt; tail -c 500 $O/stderr.txt
