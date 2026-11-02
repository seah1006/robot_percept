#!/usr/bin/env bash
set -e
cd /home/user/work/robot_percept
source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
source sim_test/gl_env.sh
export HOST=0.0.0.0 PORT=${PORT:-5080} PERCEPTION=${PERCEPTION:-fp}
export FP_INPLANE_STEP=${FP_INPLANE_STEP:-120}
exec python -m web.app
