#!/bin/bash
# 사용: run_t2.sh <라벨> <창초> <순서>   서버는 master 7f96fec worktree(rp_master). 포트 PORT_VT(기본 5092).
L=$1; SECS=$2; ORDER=$3; R=$HOME/work/robot_percept; M=$HOME/work/rp_master; B=$R/bench/verify_t2; O=$B/out; PORT=${PORT_VT:-5092}
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $M; source sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
nwork() { ps -eo args | grep -E "multiprocessing|web\.app" | grep -v grep | wc -l; }
echo "git $(git rev-parse --short HEAD) dirty_tracked=$(git status --short --untracked-files=no | wc -l) port=$PORT pre_workers=$(nwork) pre_listener=$(ss -ltn | grep -c ":$PORT ")" > $O/$L.env
bash $R/bench/verify_f/env_snap.sh before_$L >> $O/$L.env
echo "GPU: AMD Radeon RX 7600 via Mesa D3D12 (WSLg), nvidia-smi 없음, 사용률 N/A" >> $O/$L.env
python -m web.app > $O/$L.server.log 2>&1 & SP=$!
for i in $(seq 80); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
echo "win->wsl reach: $(powershell.exe -NoProfile -Command "try{(Invoke-WebRequest http://127.0.0.1:$PORT/humanoid/status -UseBasicParsing -TimeoutSec 5).StatusCode}catch{\"FAIL \"+\$_.Exception.Message}" | tr -d '\r')" >> $O/$L.env
python $B/t2_win.py http://127.0.0.1:$PORT $SP $O/$L "$SECS" "$ORDER" > $O/$L.out 2>$O/$L.err
bash $R/bench/verify_f/env_snap.sh after_$L >> $O/$L.env
ALL=$(python - <<PY
import os
ch={}
for d in os.listdir("/proc"):
    if d.isdigit():
        try: ch.setdefault(int(open(f"/proc/{d}/stat").read().rsplit(")",1)[1].split()[1]),[]).append(int(d))
        except Exception: pass
o=[$SP];i=0
while i<len(o): o+=ch.get(o[i],[]); i+=1
print(" ".join(map(str,o[1:])))
PY
)
kill $SP 2>/dev/null; sleep 3
LEFT=""; for p in $ALL; do [ -d /proc/$p ] && LEFT="$LEFT $p"; done
echo "children_at_kill=[$ALL] alive_after_SIGTERM+3s=[$LEFT]" >> $O/$L.env
for p in $LEFT; do kill -9 $p 2>/dev/null; done; kill -9 $SP 2>/dev/null; sleep 1
echo "post_workers=$(nwork) post_listener=$(ss -ltn | grep -c ":$PORT ")" >> $O/$L.env
echo done_$L; cat $O/$L.env; cat $O/$L.out; tail -5 $O/$L.err
