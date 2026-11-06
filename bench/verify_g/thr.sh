#!/bin/bash
# 스냅샷 트리에서 요청 스레드가 띄운 G1 worker가 요청 종료 후에도 사는지(PDEATHSIG 부모 스레드 함정)
R=$HOME/work/robot_percept; T=/tmp/rp_g_snap; rm -rf $T; mkdir $T
cd $R; cp -r web sitecustomize.py $T/; for d in sim sim_test assets downloads tools; do [ -e $R/$d ] && ln -s $R/$d $T/$d; done
ls $R | head -30 > /dev/null
for f in $(ls $R); do [ -e $T/$f ] || ln -s $R/$f $T/$f; done
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $T; source $R/sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$T PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=5092
python -c "import signal,os;signal.signal(signal.SIGINT,signal.default_int_handler);os.execvp('python',['python','-m','web.app'])" > /tmp/thr_server.log 2>&1 & SP=$!
for k in $(seq 80); do curl -s localhost:5092/humanoid/status >/dev/null && break; sleep 0.5; done
echo "children_before: $(pgrep -P $SP | wc -l)"
curl -s -m 70 -H 'Content-Type: application/json' -X POST localhost:5092/humanoid/mode -d '{"enabled":true}'; echo
for t in 1 3 6; do sleep $t; echo "t+$t children=$(pgrep -P $SP | wc -l) status=$(curl -s localhost:5092/humanoid/status | python -c 'import sys,json;d=json.load(sys.stdin);print(d.get("state"),d.get("enabled"),(d.get("error") or "")[:60])')"; done
kill -INT $SP; sleep 6
echo "after INT: parent=$(kill -0 $SP 2>/dev/null && echo alive || echo dead) workers=$(ps -eo args | grep -E 'multiprocessing|web\.app' | grep -v grep | wc -l)"
for p in $(pgrep -P $SP) $SP; do kill -9 $p 2>/dev/null; done
sleep 1; echo "final workers=$(ps -eo args | grep -E 'multiprocessing|web\.app' | grep -v grep | wc -l) listener=$(ss -ltn | grep -c :5092)"
