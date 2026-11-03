source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
export PYTHONPATH=$PWD
python bench/ip/depth_diag.py