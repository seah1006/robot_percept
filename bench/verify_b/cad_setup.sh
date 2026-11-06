#!/bin/bash
set -e
source ~/miniforge3/etc/profile.d/conda.sh
conda activate robot_percept
cd ~/work/robot_percept
grep -nE "argv|argparse|add_argument|__main__" tools/stp_to_mesh.py | head -20
if [ ! -x .venvs/cad/bin/python ]; then
  python -m venv .venvs/cad
fi
.venvs/cad/bin/pip install -q cadquery==2.8.0 cadquery-ocp==7.9.3.1.1 trimesh numpy scipy networkx rtree coacd fast-simplification manifold3d > /tmp/cad_pip.log 2>&1 || { tail -20 /tmp/cad_pip.log; exit 1; }
.venvs/cad/bin/python -c "import cadquery, coacd; print('cadquery', cadquery.__version__)"
