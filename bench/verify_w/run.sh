#!/bin/bash
# usage: run.sh LABEL [SEC]   -- serialized measurement against :5092
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; export PYTHONPATH=$PWD
echo load_before $(cut -d' ' -f1-3 /proc/loadavg); nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
flock /tmp/rp_measure.lock python bench/verify_w/vw_measure.py http://127.0.0.1:5092 "$1" "${2:-20}"
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
