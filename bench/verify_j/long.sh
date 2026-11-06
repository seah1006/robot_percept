#!/bin/bash
# 장시간: 서버 1회 기동, 트래커 5분 세그먼트 4개(각 측정 락). 사용: long.sh [세그먼트초=285] [n=4]
SECS=${1:-285}; N=${2:-4}; B=$HOME/work/robot_percept/bench/verify_j; O=$B/out/long; mkdir -p $O; PORT=5094
PSF=$(wslpath -w $B/win_seg.ps1); WOUT=C:\\Users\\my\\rp_tracker\\out_vj\\long
export PIDF=/tmp/vj_server.pid
{ echo "start $(date -Is) uptime: $(uptime)"; ps -eo pcpu,args --sort=-pcpu | grep openclaw | grep -v grep | head -2; } > $O/env.txt
bash $B/start_server.sh $O/server.log >> $O/env.txt
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
python $B/monitor.py $PORT $PIDF $O/mon 1 > $O/mon.out 2>&1 & MP=$!; echo $MP > /tmp/vj_mon.pid
sleep 5
for i in $(seq $N); do
  echo "seg$i load_before: $(cat /proc/loadavg) openclaw_cpu: $(ps -eo pcpu,args | grep openclaw | grep -v grep | awk "{s+=\$1} END{print s}")" >> $O/env.txt
  flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 300 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSF" -Transport ws -Label seg$i -Seconds $SECS -Url http://127.0.0.1:$PORT -OutDir "$WOUT" > $O/seg$i.ps.txt 2>&1
  echo "seg$i done $(date -Is) rc=$? t=$(date +%s.%N)" >> $O/env.txt
done
sleep 65; kill $MP
echo "end $(date -Is) load: $(cat /proc/loadavg)" >> $O/env.txt
echo LONG_DONE
