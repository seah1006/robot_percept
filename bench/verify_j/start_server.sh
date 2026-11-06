#!/bin/bash
# 사용: start_server.sh OUTLOG  (master worktree rp_master, 포트 5094). PID는 $PIDF
M=${M_VJ:-$HOME/work/rp_master}; PORT=${PORT_VJ:-5094}; PIDF=${PIDF:-/tmp/vj_server.pid}
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $M; source sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
setsid python -m web.app >> $1 2>&1 &
echo $! > $PIDF
for i in $(seq 120); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
echo "server pid $(cat $PIDF) up after ${i} polls"
