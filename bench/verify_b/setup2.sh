#!/bin/bash
set -e
source ~/miniforge3/etc/profile.d/conda.sh
cd ~/work/robot_percept
if ! conda env list | grep -q '^robot_percept '; then
  conda create -n robot_percept python=3.12 -y > /tmp/conda_create.log 2>&1
fi
conda activate robot_percept
python -VV
pip install mujoco==3.17.0 numpy==2.5.3 flask==3.1.3 opencv-python==5.0.0.93 requests urllib3 scipy trimesh open3d rtree pytest -c notes/rp_constraints.txt > /tmp/pip_install.log 2>&1 || { tail -30 /tmp/pip_install.log; exit 1; }
tail -2 /tmp/pip_install.log
if [ ! -d assets/mujoco_menagerie ]; then
  git clone -q https://github.com/google-deepmind/mujoco_menagerie.git assets/mujoco_menagerie
fi
git -C assets/mujoco_menagerie log --oneline -1
python -c "import sysconfig; print('HAVE_SEM_CLOCKWAIT=', sysconfig.get_config_var('HAVE_SEM_CLOCKWAIT')); print('HAVE_PTHREAD_COND_TIMEDWAIT_RELATIVE_NP=', sysconfig.get_config_var('HAVE_PTHREAD_COND_TIMEDWAIT_RELATIVE_NP')); print('HAVE_CLOCK_NANOSLEEP=', sysconfig.get_config_var('HAVE_CLOCK_NANOSLEEP'))"
grep -rn "/home/" --include=*.py --include=*.sh . | grep -v mujoco_menagerie | grep -v "^./assets" | head -30
