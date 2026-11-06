#!/bin/bash
R=$HOME/work/robot_percept; T=/tmp/rp_vg_base
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $T || exit 1; source $R/sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$T PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=5092
python -m web.app > /tmp/dbg_server.log 2>&1 & SP=$!
for k in $(seq 80); do curl -s localhost:5092/humanoid/status >/dev/null && break; sleep 0.5; done
curl -s -m 70 -H 'Content-Type: application/json' -X POST localhost:5092/humanoid/mode -d '{"enabled":true}'; echo
curl -s localhost:5092/humanoid/status | cut -c1-400; echo
grep -v "GET /\|bogus" /tmp/dbg_server.log | tail -12 | cut -c1-250
ls $T | head -30; diff <(ls $R) <(ls $T) | head
for p in $(pgrep -P $SP) $SP; do kill -9 $p; done; sleep 1
echo workers=$(ps -eo args | grep -E 'multiprocessing|web\.app' | grep -v grep | wc -l) listener=$(ss -ltn | grep -c :5092)
