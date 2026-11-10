#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source ~/miniforge3/etc/profile.d/conda.sh
mkdir -p bench/g0
if [[ ! -x ~/miniforge3/envs/robot_percept_g0/bin/python ]]; then
 flock -w 900 /tmp/rp_measure.lock timeout 280 conda create -y -n robot_percept_g0 --clone robot_percept
fi
conda activate robot_percept_g0
[[ "$CONDA_DEFAULT_ENV" == robot_percept_g0 ]]
python -m pip freeze > bench/g0/clone_before.txt
for v in 4.57.6 4.45.2; do
 if flock -w 900 /tmp/rp_measure.lock timeout 280 python -m pip install -c notes/constraints/cu130.txt "transformers==$v" > bench/g0/install_transformers_$v.log 2>&1; then break; fi
done
python -m pip freeze > bench/g0/clone_after.txt
diff -u bench/g0/clone_before.txt bench/g0/clone_after.txt > bench/g0/freeze.diff || true
python - <<'PY'
import importlib.metadata as m,json
before=dict(x.strip().split('==',1) for x in open('bench/g0/clone_before.txt') if '==' in x)
after=dict(x.strip().split('==',1) for x in open('bench/g0/clone_after.txt') if '==' in x)
for n in ['torch','numpy','torchvision']: assert after.get(n)==before.get(n),(n,after.get(n),before.get(n))
print(json.dumps({n:after.get(n) for n in ['torch','numpy','torchvision','transformers']}))
PY
