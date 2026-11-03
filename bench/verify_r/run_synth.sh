source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; export PYTHONPATH=$PWD
python tools/humanoid_synth.py --url http://127.0.0.1:5092 --loop
