#!/bin/bash
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export PYTHONPATH=$PWD
flock /tmp/rp_measure.lock python -m pytest -q tests 2>&1 | tail -8
ls tools
for f in tools/*.sh bench/verify_w/*.sh; do bash -n $f && echo ok $f; done
git check-ignore -v cad_uploads/web/x
sed -n 1,80p README.md
