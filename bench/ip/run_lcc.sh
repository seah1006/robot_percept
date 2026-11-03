source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
export PYTHONPATH=$PWD
uptime
nvidia-smi
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock -c "nice -n 10 python bench/ip/diagnostic_lcc.py" > bench/ip/diagnostic_lcc.log 2>&1
uptime
nvidia-smi