#!/bin/bash
# V-K 기준선: 5096 기동·종료, 잔존 프로세스 확인
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; source sim_test/gl_env.sh
export PYTHONPATH=/home/user/work/robot_percept PORT=5096 HOST=127.0.0.1
snap(){ ps -eo pid,ppid,etimes,cmd | grep -E 'web\.(app|sim_worker|perception)|multiprocessing|spawn_main|resource_tracker' | grep -v grep; }
echo "== before"; snap
setsid python -m web.app > /tmp/vk_base.log 2>&1 &
for i in $(seq 1 60); do c=$(curl -s -o /dev/null -w '%{http_code}' localhost:5096/status); [ "$c" = 200 ] && break; sleep 1; done
echo "ready_after=${i}s code=$c"
PID=$(ss -ltnp | grep ':5096' | sed -E 's/.*pid=([0-9]+).*/\1/' | head -1); echo PID=$PID
echo "== running"; snap
t0=$(date +%s.%N); kill -TERM $PID
while kill -0 $PID 2>/dev/null; do sleep 0.05; done
t1=$(date +%s.%N); echo "term_s=$(python -c "print(round($t1-$t0,3))")"
sleep 1; echo "== after"; snap; ss -ltnp | grep 5096 || echo "port free"
tail -3 /tmp/vk_base.log
