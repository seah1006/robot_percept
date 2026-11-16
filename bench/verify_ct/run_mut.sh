#!/bin/bash
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; export PYTHONPATH=/home/user/work/robot_percept
python bench/verify_ct/mutate.py --pytest 2>&1 | tail -42
