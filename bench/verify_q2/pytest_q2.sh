#!/bin/bash
cd ~/work/robot_percept; O=bench/verify_q2/out
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; source sim_test/gl_env.sh 2>/dev/null; export PYTHONPATH=$PWD
echo "pre_workers=$(ps -eo args | grep -E "multiprocessing|web\.app" | grep -v grep | wc -l) $(uptime)" > $O/pytest.env
python -m pytest -q > $O/pytest_full.txt 2>&1; tail -8 $O/pytest_full.txt > $O/pytest.txt
echo "post_workers=$(ps -eo args | grep -E "multiprocessing|web\.app" | grep -v grep | wc -l)" >> $O/pytest.env
