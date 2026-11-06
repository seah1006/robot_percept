#!/bin/bash
set -euo pipefail
source "$HOME/miniforge3/etc/profile.d/conda.sh";conda activate robot_percept
cd "$HOME/work/robot_percept";source sim_test/gl_env.sh
export HOST=0.0.0.0 PORT=5095 PERCEPTION=stub PYTHONPATH=$PWD
python -m web.app >/tmp/rp_huge5095.log 2>&1 & pid=$!
cleanup(){ kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; };trap cleanup EXIT
for _ in $(seq 1 100);do curl -sf http://127.0.0.1:5095/status >/dev/null&&break;sleep .1;done
cp bench/flask_perf/windows_huge_live.py /mnt/c/Users/my/rp_vf/huge_live.py
/mnt/c/Users/my/rp_vf/venv/Scripts/python.exe 'C:\Users\my\rp_vf\huge_live.py' 5095
