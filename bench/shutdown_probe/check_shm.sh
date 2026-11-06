#!/bin/bash
set -e
source ~/miniforge3/etc/profile.d/conda.sh;conda activate robot_percept
cd /home/my/work/robot_percept;source sim_test/gl_env.sh
export HOST=127.0.0.1 PORT=5093 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0
ss -ltnp | grep -q ":5093 " && exit 2
ls /dev/shm/psm_* 2>/dev/null | sort > /tmp/psm_before || true
python -m web.app >bench/shutdown_probe/out/shm_kill.server.log 2>&1 & SP=$!
for i in $(seq 120);do curl -sf localhost:5093/humanoid/status >/dev/null&&break;sleep .1;done
curl -sf -H "Content-Type: application/json" -X POST localhost:5093/humanoid/mode -d "{\"enabled\":true}" >/dev/null
sleep 1
kill -9 $SP;wait $SP 2>/dev/null||true;sleep 3
ls /dev/shm/psm_* 2>/dev/null | sort > /tmp/psm_after || true
comm -13 /tmp/psm_before /tmp/psm_after | tee bench/shutdown_probe/out/shm_kill_new.txt
echo new_count=$(comm -13 /tmp/psm_before /tmp/psm_after|wc -l) | tee bench/shutdown_probe/out/shm_kill_summary.txt
