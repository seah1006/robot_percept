#!/bin/bash
set -e
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
CUR=/home/my/work/robot_percept; BASE=${BASE_OVERRIDE:-/tmp/rp_shutdown_base}; OUT=$CUR/bench/shutdown_probe/out; PORT=5093
rm -rf $BASE; mkdir $BASE; cd $CUR; git archive HEAD | tar -x -C $BASE; cp sim_test/gl_env.sh sim_test/panda_mod.xml $BASE/sim_test/; ln -s $CUR/assets/mujoco_menagerie $BASE/assets/mujoco_menagerie
ss -ltnp | grep -q ":$PORT " && exit 2
desc(){ python - "$1" <<"PY"
import os,sys
r=int(sys.argv[1]);c={}
for d in os.listdir("/proc"):
 if d.isdigit():
  try:c.setdefault(int(open(f"/proc/{d}/stat").read().rsplit(")",1)[1].split()[1]),[]).append(int(d))
  except:pass
o=[];q=[r]
while q:
 p=q.pop(0); k=c.get(p,[]);o+=k;q+=k
print(" ".join(map(str,o)))
PY
}
for SPEC in A:$BASE B:$CUR; do L=${SPEC%%:*}; TREE=${SPEC#*:}; cd $TREE; source $CUR/sim_test/gl_env.sh; export HOST=127.0.0.1 PORT=$PORT PYTHONPATH=$TREE PERCEPTION=stub RP_PERCEPTION_WARMUP=0
 python -m web.app >$OUT/g1_${L}.server.log 2>&1 & SP=$!; for i in $(seq 120); do curl -sf localhost:$PORT/humanoid/status >/dev/null && break; sleep .1; done
 cd $CUR; SERVER_PID=$SP python bench/shutdown_probe/g1_cpu_window.py http://127.0.0.1:$PORT 30 $OUT/g1_${L}.json >$OUT/g1_${L}.out 2>$OUT/g1_${L}.err
 ALL=$(desc $SP); kill $SP 2>/dev/null || true; sleep 2; for p in $ALL; do [ -d /proc/$p ] && kill -9 $p 2>/dev/null || true; done; [ -d /proc/$SP ] && kill -9 $SP 2>/dev/null || true; wait $SP 2>/dev/null || true; sleep .5
done
python - <<"PY"
import json
for x in "AB":
 d=json.load(open(f"/home/my/work/robot_percept/bench/shutdown_probe/out/g1_{x}.json"));print(x,d["cpu_pct"],d["window"]["fps_count"],d["window"]["proxy_post_to_next_frame_ms"]["p95"])
PY
