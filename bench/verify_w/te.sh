#!/bin/bash
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /tmp/vw_base; source /home/user/work/robot_percept/sim_test/gl_env.sh; export PYTHONPATH=$PWD
python -m pytest -q tests/test_env.py 2>&1 | tail -4
