source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; cd ~/work/robot_percept; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=$PWD
bash bench/verify_q/env_snap.sh before_pytest; date +%T; python -m pytest -q 2>&1 | tail -15; bash bench/verify_q/env_snap.sh after_pytest
