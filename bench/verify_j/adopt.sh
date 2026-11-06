#!/bin/bash
# 기본값 전환 확인. 사용: adopt.sh   (I-J 수정 tools/teleop_tracker_win.py 를 Windows vj_new 로 복사해 실행)
B=$HOME/work/robot_percept/bench/verify_j; O=$B/out/adopt; mkdir -p $O /mnt/c/Users/my/rp_tracker/vj_new; PORT=5094; export PIDF=/tmp/vj_server.pid
cp $HOME/work/robot_percept/tools/teleop_tracker_win.py /mnt/c/Users/my/rp_tracker/vj_new/; sha256sum $HOME/work/robot_percept/tools/teleop_tracker_win.py > $O/tracker.sha
PSF=$(wslpath -w $B/win_new.ps1); WOUT=C:\\Users\\my\\rp_tracker\\out_vj\\adopt
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
run() { # label server_dir transport
  L=$1; export M_VJ=$2; T=$3
  bash $B/start_server.sh $O/server_$L.log > $O/$L.srv.txt
  [ "$L" != "B_cc37144_default" ] && curl -s -X POST -H "Content-Type: application/json" -d "{\"enabled\":true}" localhost:$PORT/humanoid/mode >/dev/null
  sleep 3
  flock -w 900 /tmp/rp_measure.lock timeout 200 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSF" -Transport $T -Label $L -Seconds 30 -Url http://127.0.0.1:$PORT -OutDir "$WOUT" > $O/$L.ps.txt 2>&1
  curl -s localhost:$PORT/humanoid/status | head -c 300 > $O/$L.status_after.txt
  kill $(cat $PIDF); sleep 5; echo "$L end listeners=$(ss -ltn | grep -c :$PORT) workers=$(ps -eo args | grep -E "multiprocessing|web\.app" | grep -v grep | wc -l)" >> $O/env.txt
}
run A_master_default $HOME/work/rp_master default
run C_master_http $HOME/work/rp_master http
run B_cc37144_default $HOME/work/rp_cc37144 default
run D_cc37144_http $HOME/work/rp_cc37144 http
echo ADOPT_DONE
