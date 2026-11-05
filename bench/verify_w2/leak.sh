#!/bin/bash
TREE=$1; PORT=$2
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $TREE; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
python -m web.app > /home/my/work/robot_percept/bench/verify_w2/out/leak.log 2>&1 & SP=$!
for i in $(seq 60); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
sleep 3; th(){ grep Threads /proc/$SP/status | awk "{print \$2}"; }
echo "threads_start $(th)"
for path in /video /teleop/preview.mjpg /humanoid/video; do
  curl -s -m 1 localhost:$PORT$path -o /dev/null -w "$path http=%{http_code}\n" ; done
for k in 1 2 3; do for i in $(seq 8); do curl -s -m 1 localhost:$PORT/video -o /dev/null; done; done
sleep 4; echo "threads_after_video_x24 $(th)"
grep -n "teleop.*get\|route\|get(" web/teleop.py | grep -i "preview\|video\|mjpeg" | head -3
kill $SP; sleep 2
