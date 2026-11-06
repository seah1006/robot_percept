#!/bin/bash
set -e
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; source sim_test/gl_env.sh
export HOST=127.0.0.1 PORT=5093 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0
ss -ltnp | grep -q ":5093 " && exit 2
python -m web.app >/tmp/rp_thread_cpu.log 2>&1 & SP=$!; trap "kill $SP 2>/dev/null || true" EXIT
for i in $(seq 120); do curl -sf localhost:5093/humanoid/status >/dev/null && break;sleep .1;done
curl -sf -H "Content-Type: application/json" -X POST localhost:5093/humanoid/mode -d "{\"enabled\":true}" >/dev/null
sleep 5
CH=$(pgrep -P $SP | tr "\n" "," | sed "s/,$//")
echo server=$SP children=$CH
ps -L -p $SP,$CH -o pid,tid,ppid,pcpu,time,comm
kill $SP; wait $SP || true; trap - EXIT
