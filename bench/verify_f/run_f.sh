#!/bin/bash
# 사용: run_f.sh <g1|scen|scen_wsl> <라벨>  (locked_f.sh 로 락 안에서 실행). 포트 5092, PERCEPTION=stub.
KIND=$1; L=$2; R=${ROOT:-$HOME/work/robot_percept}; F=$HOME/work/robot_percept/bench/verify_f; O=$F/out; PORT=${PORT_VF:-5092}
WD_W='C:\Users\my\rp_vf'; WD_L=/mnt/c/Users/my/rp_vf
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
cd $R; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
echo "git $(git rev-parse --short HEAD) dirty=$(git status --short | wc -l)" > $O/$L.env
bash $F/env_snap.sh before_$L | tee -a $O/$L.env
python -m web.app > $O/$L.server.log 2>&1 & SP=$!
for i in $(seq 80); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
case $KIND in
 g1) python $F/g1_window.py http://127.0.0.1:$PORT 30 $O/$L.json > $O/$L.out 2>$O/$L.err;;
 scen) mkdir -p $WD_L; cp $F/sender_f.py $WD_L/; python $F/gen_payloads.py $WD_L >/dev/null; python $F/scen_f.py http://127.0.0.1:$PORT $SP $L $O/$L.json $WD_L win "$WD_W" > $O/$L.out 2>$O/$L.err;;
  p0ws) python $F/gen_payloads.py $O/pl >/dev/null; python $F/p0_ws.py http://127.0.0.1:$PORT $SP $O/$L.json > $O/$L.out 2>$O/$L.err; mkdir -p $WD_L; cp $F/huge_win.py $WD_L/; /mnt/c/Users/my/rp_vf/venv/Scripts/python.exe "C:\Users\my\rp_vf\huge_win.py" http://127.0.0.1:$PORT > $O/$L.huge_win.json 2>$O/$L.huge_win.err;;
 scen_wsl) python $F/gen_payloads.py $O/pl >/dev/null; python $F/scen_f.py http://127.0.0.1:$PORT $SP $L $O/$L.json $O/pl wsl > $O/$L.out 2>$O/$L.err;;
esac
bash $F/env_snap.sh after_$L | tee -a $O/$L.env
CH=$(pgrep -P $SP); kill $SP 2>/dev/null; sleep 2; [ -n "$CH" ] && kill $CH 2>/dev/null; sleep 1; [ -n "$CH" ] && kill -9 $CH 2>/dev/null; echo "leftover_mp=$(ps -eo args | grep -c "[m]ultiprocessing")" >> $O/$L.env
ss -ltnp | grep ":$PORT " >> $O/$L.env; echo done_$L
