#!/bin/bash
# 사용: p0.sh <트리> <포트> <라벨> <vw초>
TREE=$1; PORT=$2; L=$3; S=$4
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $TREE; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
python -m web.app > /home/my/work/robot_percept/bench/verify_w2/out/p0_$L.server.log 2>&1 & SP=$!
for i in $(seq 60); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
python ~/work/robot_percept/bench/verify_w2/clock_probe_ts.py $((S+150)) /home/my/work/robot_percept/bench/verify_w2/out/p0_$L.probe.jsonl & PP=$!
python bench/verify_w/vw_measure.py http://127.0.0.1:$PORT $L $S > /home/my/work/robot_percept/bench/verify_w2/out/p0_$L.vw.json 2>/home/my/work/robot_percept/bench/verify_w2/out/p0_$L.vw.err; echo vw_exit=$?
if [ -n "$RUN_CRASH" ]; then ROOT=$TREE PORT=$PORT bash $TREE/bench/verify_w/crash_test.sh > /home/my/work/robot_percept/bench/verify_w2/out/p0_$L.crash.txt 2>&1; echo crash_exit=$?; fi
kill $PP 2>/dev/null; kill $SP; sleep 2; ss -ltnp | grep :$PORT
