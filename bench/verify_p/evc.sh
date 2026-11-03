source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export HOST=127.0.0.1
V=/mnt/c/Users/USER/.aside/u/0/sessions/2026-10-19_5xmUwlu5vry7k9Rb/tmp/vp
mkdir -p bench/verify_p/out; git show baseline-1102:web/perception_stub.py > bench/verify_p/baseline_stub.py
flock /tmp/rp_gpu.lock -c "python $V/ev.py current bench/verify_p/out/eval_current.json" 2>&1 | tail -30
