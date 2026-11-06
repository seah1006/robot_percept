#!/bin/bash
# 재연결 시험 1회: recon.sh N  (트래커 100초, 20초 시점 SIGTERM, 10초 뒤 재기동)
N=$1; B=$HOME/work/robot_percept/bench/verify_j; O=$B/out/recon; mkdir -p $O; PORT=5094; export PIDF=/tmp/vj_server.pid
PSF=$(wslpath -w $B/win_seg.ps1); WOUT=C:\\Users\\my\\rp_tracker\\out_vj\\recon
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
echo "r$N load: $(cat /proc/loadavg) openclaw_cpu: $(ps -eo pcpu,args | grep openclaw | grep -v grep | awk "{s+=\$1} END{print s}")" >> $O/env.txt
bash $B/start_server.sh $O/server_r$N.log >> $O/env.txt
python $B/monitor.py $PORT $PIDF $O/mon_r$N ${ENABLE:-once} > $O/mon_r$N.out 2>&1 & MP=$!
sleep 4
(
 sleep 22; SP=$(cat $PIDF); T0=$(date +%s.%N); kill -TERM $SP
 while kill -0 $SP 2>/dev/null; do sleep 0.1; done; T1=$(date +%s.%N)
 echo "r$N sigterm=$T0 exited=$T1 children_left=$(ps -eo args | grep -E "multiprocessing|web\.app" | grep -v grep | wc -l)" >> $O/env.txt
 sleep 10; T2=$(date +%s.%N); bash $B/start_server.sh $O/server_r$N.restart.log >> $O/env.txt; T3=$(date +%s.%N)
 echo "r$N restart_cmd=$T2 up=$T3" >> $O/env.txt
) &
RP=$!
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 300 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSF" -Transport ws -Label r$N -Seconds 100 -Url http://127.0.0.1:$PORT -OutDir "$WOUT" > $O/r$N.ps.txt 2>&1
wait $RP; sleep 3; kill $MP; kill $(cat $PIDF); sleep 5
echo "r$N end listeners=$(ss -ltn | grep -c :$PORT) workers=$(ps -eo args | grep -E "multiprocessing|web\.app" | grep -v grep | wc -l)" >> $O/env.txt
