#!/bin/bash
set -e
exec 9>/tmp/rp_measure.lock
flock -w 900 9
exec 8>/tmp/rp_gpu.lock
flock -w 30 8
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export HOST=0.0.0.0 PYTHONPATH=$PWD
OUT=/mnt/c/Users/USER/.aside/u/0/sessions/2026-11-02_1NIgF2z2BvfBSkOh/tmp/tracker_panda_viewer_1105.log
exec > >(tee "$OUT") 2>&1
date;uptime;nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
ps -eo pid,args | grep -E 'bench|verify' || true
if ss -ltnp | grep -q ':5095 ';then echo '5095 occupied';exit 1;fi
PORT=5095 PERCEPTION=stub python -m web.app > /mnt/c/Users/USER/.aside/u/0/sessions/2026-11-02_1NIgF2z2BvfBSkOh/tmp/tracker_panda_viewer_server_1105.log 2>&1 &
server_pid=$!
cleanup() {
 if ss -ltnp | grep ':5095 ' | grep -q "pid=$server_pid,"; then kill "$server_pid";fi
 rm -f bench/tracker_panda_viewer_temp.sh
}
trap cleanup EXIT
for i in $(seq 1 120);do
 if curl -sf http://127.0.0.1:5095/status >/dev/null;then break;fi
 sleep 1
done
curl -sf -H 'Content-Type: application/json' -d '{"enabled":false}' http://127.0.0.1:5095/humanoid/mode
curl -sf -H 'Content-Type: application/json' -d '{"enabled":false}' http://127.0.0.1:5095/teleop/mode
sed 's/5092/5095/g' bench/verify_w/panda_viewer_base.sh >bench/tracker_panda_viewer_temp.sh
bash bench/tracker_panda_viewer_temp.sh
date;uptime;nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv