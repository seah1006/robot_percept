#!/usr/bin/env bash
set -euo pipefail
cd /home/user/work/robot_percept
set +u
source /home/user/anaconda3/etc/profile.d/conda.sh
set -u
mkdir -p bench/g0/company
/home/user/anaconda3/envs/robot_percept/bin/python -m pip freeze > bench/g0/company/original_before.txt
if [[ -d /home/user/anaconda3/envs/robot_percept_g0c && ! -x /home/user/anaconda3/envs/robot_percept_g0c/bin/python ]]; then
 echo 'Partial clone prefix: inspect /home/user/anaconda3/envs/robot_percept_g0c; do not overwrite or delete automatically' >&2
 exit 3
fi
if [[ ! -x /home/user/anaconda3/envs/robot_percept_g0c/bin/python ]]; then
 flock -w 900 /tmp/rp_measure.lock timeout 280 conda create -y -n robot_percept_g0c --clone robot_percept
fi
set +u
conda activate robot_percept_g0c
set -u
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
export HSA_ENABLE_DXG_DETECTION=1
python -m pip freeze > bench/g0/company/clone_before.txt
flock -w 900 /tmp/rp_measure.lock timeout 280 python -m pip install -c notes/constraints/common.txt -c notes/constraints/cu130.txt transformers==4.57.6
python -m pip freeze > bench/g0/company/clone_after.txt
/home/user/anaconda3/envs/robot_percept/bin/python -m pip freeze > bench/g0/company/original_after.txt
cmp bench/g0/company/original_before.txt bench/g0/company/original_after.txt
sha256sum bench/g0/company/original_*.txt
python - <<'PY'
from pathlib import Path
for name in ('torch','torchvision','numpy'):
 before=sorted(x for x in Path('bench/g0/company/clone_before.txt').read_text().splitlines() if x.lower().startswith(name+'=='))
 after=sorted(x for x in Path('bench/g0/company/clone_after.txt').read_text().splitlines() if x.lower().startswith(name+'=='))
 assert before==after,(name,before,after)
print('clone torch/torchvision/numpy freeze unchanged')
PY