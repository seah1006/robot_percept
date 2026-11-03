source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export HOST=0.0.0.0; export PYTHONPATH=$PWD; export PORT=5092 PERCEPTION=stub
exec python -m web.app > bench/verify_r/server5092.log 2>&1
