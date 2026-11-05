#!/bin/bash
# 사용: abwin.sh <트리> <포트> <창초> <출력접두>   (측정 락 바깥에서 호출하지 말 것: flock으로 감싸서 실행)
TREE=$1; PORT=$2; DUR=$3; OUT=$4; R=~/work/robot_percept/bench/verify_w2
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $TREE; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
python -m web.app > $OUT.server.log 2>&1 &
SP=$!
for i in $(seq 60); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
cpu(){ # 서버 트리 전체 utime+stime (jiffies)
  local pids="$SP $(pgrep -P $SP | tr "\n" " ")"; local more=$(for p in $pids; do pgrep -P $p; done | tr "\n" " "); pids="$pids $more"
  local t=0; for p in $pids; do [ -r /proc/$p/stat ] && t=$((t+$(awk "{print \$14+\$15}" /proc/$p/stat))); done; echo $t; }
sleep 3; c0=$(cpu); sleep 15; c1=$(cpu); echo "idle_cpu_pct(off,no client): $(( (c1-c0) )) jiffies/15s => $(echo "scale=2;($c1-$c0)/15" | bc)%" > $OUT.cpu
curl -s -XPOST -H "Content-Type: application/json" -d "{\"enabled\":true}" localhost:$PORT/humanoid/mode >/dev/null
for i in $(seq 60); do curl -s localhost:$PORT/humanoid/status | grep -q "\"ready\"" && break; sleep 0.5; done
sleep 2
c0=$(cpu); sleep 10; c1=$(cpu); echo "g1_on_noclient_cpu_pct: $(echo "scale=2;($c1-$c0)/10" | bc)%" >> $OUT.cpu
python $R/clock_probe_ts.py $((DUR+2)) $OUT.probe.jsonl &
PP=$!
c0=$(cpu)
python $R/mjpeg_gaps.py http://127.0.0.1:$PORT/humanoid/video $DUR $OUT.frames.json
c1=$(cpu)
echo "g1_on_client_cpu_pct: $(echo "scale=2;($c1-$c0)/$DUR" | bc)%" >> $OUT.cpu
wait $PP
curl -s -XPOST -H "Content-Type: application/json" -d "{\"enabled\":false}" localhost:$PORT/humanoid/mode >/dev/null
sleep 1; kill $SP; sleep 2
echo "load: $(cat /proc/loadavg)" >> $OUT.cpu
python $R/analyze.py $OUT.frames.json $OUT.probe.jsonl | sed "s/^walljumps.*/walljumps: $(grep -c skew_ms $OUT.probe.jsonl) events/"
cat $OUT.cpu
