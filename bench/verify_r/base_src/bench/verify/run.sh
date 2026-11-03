source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd ${ROOT:-/home/user/work/robot_percept}; source sim_test/gl_env.sh; export HOST=127.0.0.1
LABEL=${1:-baseline}; RUNS=${2:-2}; SRC=${3:-live}
mkdir -p bench/verify/out
for i in $(seq 1 $RUNS); do
  PORT=5082 PERCEPTION=fp FP_INPLANE_STEP=120 python -m web.app > bench/verify/out/server_${LABEL}_$i.log 2>&1 &
  PID=$!
  for k in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:5082/status | grep -q ready && break; sleep 2; done
  python bench/verify/bench.py http://127.0.0.1:5082 ${LABEL}_$i bench/verify/out/${LABEL}_$i.json 2>&1 | tail -20
  kill $PID; sleep 5; kill -9 $PID 2>/dev/null
  grep -ciE "traceback|error" bench/verify/out/server_${LABEL}_$i.log
done