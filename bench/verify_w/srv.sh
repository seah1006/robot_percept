#!/bin/bash
# usage: srv.sh [ROOT] [LOGTAG]   (port 5092 only)
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
ROOT=${1:-/home/user/work/robot_percept}; cd $ROOT; source sim_test/gl_env.sh
export HOST=0.0.0.0 PYTHONPATH=$PWD PORT=5092 PERCEPTION=stub
exec python -m web.app > /home/user/work/robot_percept/bench/verify_w/server_${2:-cur}.log 2>&1
