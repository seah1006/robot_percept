#!/bin/bash
# usage: server.sh DIR   (DIR = /tmp/vs_base for baseline, or repo for candidate); port 5094 only
DIR=${1:-/home/user/work/robot_percept}
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; source sim_test/gl_env.sh
cd $DIR
[ -e assets/mujoco_menagerie ] || ln -s /home/user/work/robot_percept/assets/mujoco_menagerie assets/mujoco_menagerie
export HOST=0.0.0.0 PYTHONPATH=$PWD PORT=5094 PERCEPTION=stub
exec python -m web.app
