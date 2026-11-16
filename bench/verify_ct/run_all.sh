#!/bin/bash
# V-CT 판정 실행: 측정 락 안. 사용: bash run_all.sh [full]
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export PYTHONPATH=$PWD
echo "load: $(cat /proc/loadavg)"; nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>&1 | head -1
sha1sum perception/interfaces.py web/cell_state.py tests/test_contracts_r5.py
python bench/verify_ct/verify_state.py | tail -8
python bench/verify_ct/mutate.py --pytest 2>&1 | tail -45
python -m pytest tests/test_contracts_r5.py -q -p no:cacheprovider 2>&1 | tail -3
if [ "$1" = full ]; then
  python -m pytest tests -q -p no:cacheprovider 2>&1 | tail -8
fi
echo "--- git diff 운영/공유 파일"
git diff --stat -- web/app.py web/sim_worker.py web/realtime.py web/perception_stub.py web/static sim perception/sam_runner.py perception/fp_runner.py web/teleop.py
git status --short | grep -v -e '^?? notes' -e bench/ -e '^ M notes'
