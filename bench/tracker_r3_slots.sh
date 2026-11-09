#!/usr/bin/env bash
# 사용: bash bench/tracker_r3_slots.sh <Windows 출력 루트> [URL]
# 서버는 별도로 기동/G1 ON. 각 슬롯 <5분, 1영상 HTTP/WS 교대 2창.
set -euo pipefail
cd /home/user/work/robot_percept
OUT=${1:?Windows output root required}; URL=${2:-http://127.0.0.1:5095}
WINPY='/mnt/c/Users/USER/AppData/Local/Programs/Python/Python312/python.exe'
SCRIPT='\\wsl.localhost\Ubuntu-24.04\home\user\work\robot_percept\bench\tracker_r3_company.py'
for VIDEO in teleop_round2_async teleop_round2_compact teleop_test_fast; do
 for PAIR in 1 2 3; do
  (
   flock -w 900 9
   echo "slot start $(date -Iseconds) video=$VIDEO pair=$PAIR"; uptime
   nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader || true
   env -u PYTHONHOME -u PYTHONPATH -u VIRTUAL_ENV -u PIP_PREFIX -u PYTHONNOUSERSITE "$WINPY" "$SCRIPT" --url "$URL" --out "${OUT}\\${VIDEO}_pair${PAIR}" --seconds 30 --order http,ws --videos "C:\Users\USER\Documents\sam_camera\${VIDEO}.mp4"
   uptime; echo "slot end $(date -Iseconds)"
  ) 9>/tmp/rp_measure.lock
 done
done
