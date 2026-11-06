#!/bin/bash
set -e
mkdir -p ~/work
cd ~/work
if [ ! -d robot_percept ]; then git clone https://github.com/seah1006/robot_percept.git; fi
cd robot_percept
git fetch origin
git checkout wip/r2
git log --oneline -5
ls
ls notes
cat sim_test/gl_env.sh
cat notes/rp_constraints.txt | head -60
if [ ! -d ~/miniforge3 ]; then
  curl -sSL -o /tmp/mf.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
  bash /tmp/mf.sh -b -p ~/miniforge3 > /tmp/mf_install.log 2>&1
fi
~/miniforge3/bin/conda --version
dpkg -l | grep -E "libegl|mesa|libgl1" | cut -c1-90 | head -20
