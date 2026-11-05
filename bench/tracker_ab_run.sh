#!/bin/bash
set -e
exec 9>/tmp/rp_measure.lock
flock -w 900 9
exec 8>/tmp/rp_gpu.lock
flock -w 30 8
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
ps -eo pid,args | grep -E 'bench|verify' || true
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export HOST=0.0.0.0 PYTHONPATH=$PWD
uptime
if ss -ltnp | grep -q ':5095 '; then echo '5095 already occupied';exit 1;fi
git show 1da4b93:tools/teleop_tracker_win.py > bench/tracker_baseline_temp.py
PORT=5095 PERCEPTION=stub python -m web.app > /mnt/c/Users/USER/.aside/u/0/sessions/2026-11-02_1NIgF2z2BvfBSkOh/tmp/tracker_ab_opt_server.log 2>&1 &
server_pid=$!
cleanup() {
 if ss -ltnp | grep ':5095 ' | grep -q "pid=$server_pid,"; then kill "$server_pid";fi
 rm -f bench/tracker_baseline_temp.py
}
trap cleanup EXIT
env -u PYTHONHOME -u PYTHONPATH -u VIRTUAL_ENV -u PIP_PREFIX -u PYTHONNOUSERSITE OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0 /mnt/c/Users/USER/AppData/Local/Programs/Python/Python312/python.exe '//wsl.localhost/Ubuntu-24.04/home/user/work/robot_percept/bench/tracker_ab.py' 'C:\Users\USER\.aside\u\0\sessions\2026-11-02_1NIgF2z2BvfBSkOh\tmp\tracker_ab_opt.json'
uptime