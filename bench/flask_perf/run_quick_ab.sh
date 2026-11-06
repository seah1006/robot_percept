#!/bin/bash
set -euo pipefail
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate robot_percept
cd "$HOME/work/robot_percept"
source sim_test/gl_env.sh
export HOST=127.0.0.1 PORT=5093 PERCEPTION=stub PYTHONPATH=$PWD
rm -rf /tmp/rp_flask_payload
python bench/verify_f/gen_payloads.py /tmp/rp_flask_payload >/dev/null
python -m web.app >/tmp/rp_f_ab.log 2>&1 & pid=$!
cleanup(){ kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 100); do curl -sf http://127.0.0.1:5093/status >/dev/null && break; sleep .1; done
python bench/flask_perf/quick_ab.py "$pid" | tee bench/flask_perf/out/quick_ab.json
