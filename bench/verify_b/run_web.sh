#!/bin/bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate robot_percept
cd ~/work/robot_percept
source sim_test/gl_env.sh
export HOST=0.0.0.0 PYTHONPATH=$PWD
PORT=${PORT:-5091} PERCEPTION=stub RP_PERCEPTION_WARMUP=0 exec python -m web.app
