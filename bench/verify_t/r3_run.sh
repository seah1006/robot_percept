#!/bin/bash
# usage: r3_run.sh <label> <secs> <order> <video(Windows path)> <mode> <tracker(Windows path)>   server = repo worktree, port 5092. Run under measure lock.
L=$1; SECS=$2; ORDER=$3; VIDEO=$4; MODE=$5; TRK=$6; R=$HOME/work/robot_percept; B=$R/bench/verify_t; O=$B/out_r3; PORT=5092
bash $B/r3_sync.sh
mkdir -p $O
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd $R; source sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
if ss -ltn | grep -q ":$PORT "; then echo "5092 occupied"; exit 1; fi
echo "git $(git rev-parse --short HEAD) dirty=$(git status --short --untracked-files=no | wc -l) port=$PORT mode=$MODE video=$VIDEO tracker=$TRK" > $O/$L.env
echo "tracker_sha=$(sha256sum "$(wslpath "$TRK")" | cut -c1-16) server_web_sha=$(cat web/*.py | sha256sum | cut -c1-16)" >> $O/$L.env
bash $R/bench/verify_f/env_snap.sh before_$L >> $O/$L.env
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader >> $O/$L.env 2>&1
ps -eo pid,pcpu,args --sort=-pcpu | head -6 | cut -c1-120 >> $O/$L.env
python -m web.app > $O/$L.server.log 2>&1 & SP=$!
for i in $(seq 80); do curl -s localhost:$PORT/status >/dev/null && break; sleep 0.5; done
python $B/r3_cross.py --url http://127.0.0.1:$PORT --pid $SP --out $O/$L --secs $SECS --order $ORDER --video "$VIDEO" --mode $MODE --tracker "$TRK" > $O/$L.out 2>$O/$L.err
bash $R/bench/verify_f/env_snap.sh after_$L >> $O/$L.env
kill $SP 2>/dev/null; sleep 4
[ -d /proc/$SP ] && kill -9 $SP
echo "post_listener=$(ss -ltn | grep -c ":$PORT ") leftover=$(ps -eo args | grep -E 'web\.app|multiprocessing' | grep -v grep | wc -l)" >> $O/$L.env
cat $O/$L.env $O/$L.out; tail -3 $O/$L.err
