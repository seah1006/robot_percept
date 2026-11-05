#!/bin/bash
# 사용: repro.sh <트리경로> <포트> <초> <출력접두>
TREE=$1; PORT=$2; DUR=$3; OUT=$4
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $TREE; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
python -m web.app > $OUT.server.log 2>&1 &
SP=$!
for i in $(seq 60); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
curl -s -XPOST -H "Content-Type: application/json" -d "{\"enabled\":true}" localhost:$PORT/humanoid/mode >$OUT.on.json
for i in $(seq 60); do curl -s localhost:$PORT/humanoid/status | grep -q "\"ready\"" && break; sleep 0.5; done
sleep 2
R=~/work/robot_percept/bench/verify_w2
echo "load: $(cat /proc/loadavg)" > $OUT.meta
python $R/clock_probe_ts.py $((DUR+2)) $OUT.probe.jsonl &
PP=$!
python $R/mjpeg_gaps.py http://127.0.0.1:$PORT/humanoid/video $DUR $OUT.frames.json
wait $PP
echo "load_end: $(cat /proc/loadavg)" >> $OUT.meta
curl -s -XPOST -H "Content-Type: application/json" -d "{\"enabled\":false}" localhost:$PORT/humanoid/mode >/dev/null
sleep 1; kill $SP; sleep 1; ss -ltnp | grep :$PORT
python $R/analyze.py $OUT.frames.json $OUT.probe.jsonl
cat $OUT.meta
