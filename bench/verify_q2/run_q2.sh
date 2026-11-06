#!/bin/bash
# 사용: run_q2.sh <kind> <라벨> [인자...]   kind: win(ws|http, push|poll) | p0ws | p0vw | killws
# 서버 기동 -> 실행 -> 서버+자식 트리 전체 정리(SIGTERM 후 남으면 -9) -> 잔존 python worker 수 기록. 포트 PORT_VF(기본 5092).
KIND=$1; L=$2; R=$HOME/work/robot_percept; Q=$R/bench/verify_q2; F=$R/bench/verify_f; O=$Q/out; PORT=${PORT_VF:-5092}
WD_W="C:\\Users\\my\\rp_vf"; WD_L=/mnt/c/Users/my/rp_vf
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $R; source sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
nwork() { ps -eo args | grep -E "multiprocessing|web\.app" | grep -v grep | wc -l; }
echo "git $(git rev-parse --short HEAD) dirty=$(git status --short | wc -l) port=$PORT pre_workers=$(nwork) pre_listener=$(ss -ltn | grep -c ":$PORT ")" > $O/$L.env
bash $F/env_snap.sh before_$L >> $O/$L.env
python -m web.app > $O/$L.server.log 2>&1 & SP=$!
for i in $(seq 80); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
case $KIND in
 win) TR=$3; STM=$4; mkdir -p $WD_L; cp $Q/sender_q2.py $WD_L/; python $F/gen_payloads.py $WD_L >/dev/null
      python $Q/q2_win.py http://127.0.0.1:$PORT $SP $L $O/$L.json $WD_L "$WD_W" $TR $STM > $O/$L.out 2>$O/$L.err;;
 wsl) TR=$3; STM=$4; python $F/gen_payloads.py $WD_L >/dev/null
      python $Q/q3_wsl.py http://127.0.0.1:$PORT $SP $L $O/$L.json $WD_L "$WD_W" $TR $STM > $O/$L.out 2>$O/$L.err;;
 p0vw) python bench/verify_w/vw_measure.py http://127.0.0.1:$PORT $L 15 > $O/$L.vw.json 2>$O/$L.vw.err
       ROOT=$R PORT=$PORT bash bench/verify_w/crash_test.sh > $O/$L.crash.txt 2>&1;;
 p0ws) python $F/gen_payloads.py $O/pl >/dev/null; python $F/p0_ws.py http://127.0.0.1:$PORT $SP $O/$L.json > $O/$L.out 2>$O/$L.err
       mkdir -p $WD_L; cp $F/huge_win.py $WD_L/; /mnt/c/Users/my/rp_vf/venv/Scripts/python.exe "C:\\Users\\my\\rp_vf\\huge_win.py" http://127.0.0.1:$PORT > $O/$L.huge_win.json 2>$O/$L.huge_win.err;;
 killws) mkdir -p $WD_L; cp $Q/sender_q2.py $WD_L/; python $F/gen_payloads.py $WD_L >/dev/null
      python $Q/p0_killws.py http://127.0.0.1:$PORT $SP $L $O/$L.json "$WD_W" > $O/$L.out 2>$O/$L.err;;
esac
bash $F/env_snap.sh after_$L >> $O/$L.env
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
echo done_$L; cat $O/$L.env
