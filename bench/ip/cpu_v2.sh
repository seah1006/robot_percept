source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
export PYTHONPATH=$PWD
python -m py_compile web/perception_stub.py perception/fp_runner.py perception/depth_refine.py
python -m pytest -q tests/test_smoke.py