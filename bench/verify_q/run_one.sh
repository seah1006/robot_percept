#!/bin/bash
# 사용: run_one.sh <종류> <라벨>  종류: window|window_col|vw|crash|panda|leak . 이중 락 안에서 실행할 것.
KIND=$1; L=$2; R=~/work/robot_percept; Q=$R/bench/verify_q; O=$Q/out; PORT=5092
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $R; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
bash $Q/env_snap.sh before_$L | tee -a $O/$L.env
python -c "import os;print(\"GL\",os.environ.get(\"MESA_D3D12_DEFAULT_ADAPTER_NAME\"))" >> $O/$L.env
python -m web.app > $O/$L.server.log 2>&1 & SP=$!
for i in $(seq 80); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
case $KIND in
 window) python $Q/q_window.py http://127.0.0.1:$PORT 30 $O/$L.json > $O/$L.out 2>$O/$L.err;;
 window_col) python $Q/q_window.py http://127.0.0.1:$PORT 30 $O/$L.json collision > $O/$L.out 2>$O/$L.err;;
 vw) python bench/verify_w/vw_measure.py http://127.0.0.1:$PORT $L 20 > $O/$L.out 2>$O/$L.err; cp bench/verify_w/$L.json $O/$L.vw.json;;
 crash) ROOT=$R PORT=$PORT bash bench/verify_w/crash_test.sh > $O/$L.crash.txt 2>&1;;
 panda) (timeout 40 curl -s -N localhost:$PORT/video -o /dev/null &) ; sleep 6
   python $R/bench/verify_w2/mjpeg_gaps.py http://127.0.0.1:$PORT/video 30 $O/$L.frames.json & MP=$!
   python - <<PY > $O/$L.out
import json,time,urllib.request,statistics
v=[];t0=time.monotonic()
while time.monotonic()-t0<30:
    v.append(json.load(urllib.request.urlopen("http://127.0.0.1:$PORT/status",timeout=2)).get("fps"));time.sleep(.2)
v=[x for x in v if isinstance(x,(int,float))]
print("panda status fps mean %.2f min %.1f max %.1f n=%d"%(statistics.mean(v),min(v),max(v),len(v)))
PY
   wait $MP; python - <<PY >> $O/$L.out
import json;d=json.load(open("$O/$L.frames.json"));ts=d["ts"];w=[t for t in ts if t>=d["t0"]]
import numpy as np;g=np.diff(w)*1000
print("panda mjpeg frames",len(w),"fps_count",round(len(w)/30,2),"max_gap_ms",round(g.max(),1))
PY
   ;;
 leak) th(){ grep Threads /proc/$SP/status | awk "{print \$2}"; }
   echo "threads_start $(th)" > $O/$L.out
   for k in 1 2 3; do for i in $(seq 8); do curl -s -m 1 localhost:$PORT/video -o /dev/null; done; done
   for k in 1 2 3; do for i in $(seq 8); do curl -s -m 1 localhost:$PORT/humanoid/video -o /dev/null; done; done
   sleep 4; echo "threads_after_24video_24humanoid $(th)" >> $O/$L.out
   curl -s -XPOST -H "Content-Type: application/json" -d "{\"enabled\":true}" localhost:$PORT/humanoid/mode >/dev/null; sleep 8
   for k in 1 2 3; do for i in $(seq 8); do curl -s -m 1 localhost:$PORT/humanoid/video -o /dev/null; done; done
   echo "threads_g1on_after_24humanoid $(th)" >> $O/$L.out; curl -s -XPOST -H "Content-Type: application/json" -d "{\"enabled\":false}" localhost:$PORT/humanoid/mode >/dev/null; sleep 3
   echo "threads_after_off $(th)" >> $O/$L.out;;
esac
bash $Q/env_snap.sh after_$L | tee -a $O/$L.env
kill $SP 2>/dev/null; sleep 3
ss -ltnp | grep ":$PORT " >> $O/$L.env; echo done_$L
