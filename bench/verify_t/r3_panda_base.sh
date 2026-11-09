#!/bin/bash
# Panda screen fps with tracker OFF (teleop mode off and on, no tracker). 3 x 30s count-based on /video MJPEG. Run under measure lock.
L=$1; R=$HOME/work/robot_percept; B=$R/bench/verify_t; O=$B/out_r3; PORT=5092
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd $R; source sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$PWD PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
if ss -ltn | grep -q ":$PORT "; then echo "5092 occupied"; exit 1; fi
bash $R/bench/verify_f/env_snap.sh before_$L > $O/$L.env
python -m web.app > $O/$L.server.log 2>&1 & SP=$!
for i in $(seq 80); do curl -s localhost:$PORT/status >/dev/null && break; sleep 0.5; done
sleep 5
python - <<'PY' > $O/$L.json
import http.client, json, time, threading
def post(p, b):
    c = http.client.HTTPConnection("127.0.0.1", 5092, timeout=60); c.request("POST", p, json.dumps(b), {"Content-Type": "application/json"}); c.getresponse().read(); c.close()
def window(sec):
    ts = []; stop = [False]
    def run():
        c = http.client.HTTPConnection("127.0.0.1", 5092, timeout=10); c.request("GET", "/video"); r = c.getresponse(); buf = b""
        while not stop[0]:
            ch = r.read1(65536)
            if not ch: break
            buf += ch
            while True:
                i = buf.find(b"\xff\xd8"); j = buf.find(b"\xff\xd9", i + 2) if i >= 0 else -1
                if i < 0 or j < 0: break
                ts.append(time.monotonic()); buf = buf[j + 2:]
    t = threading.Thread(target=run, daemon=True); t.start(); time.sleep(sec); stop[0] = True
    t0 = time.monotonic() - sec
    ts = [x for x in ts]
    return (len(ts) - 1) / (ts[-1] - ts[0]) if len(ts) > 2 else None
res = {}
post("/humanoid/mode", {"enabled": False})
post("/teleop/mode", {"enabled": False}); res["teleop_off"] = [window(30) for _ in range(2)]
post("/teleop/mode", {"enabled": True}); time.sleep(2); res["teleop_on_no_tracker"] = [window(30) for _ in range(2)]
post("/teleop/mode", {"enabled": False})
print(json.dumps(res))
PY
bash $R/bench/verify_f/env_snap.sh after_$L >> $O/$L.env
kill $SP 2>/dev/null; sleep 4; [ -d /proc/$SP ] && kill -9 $SP
echo "post_listener=$(ss -ltn | grep -c ":$PORT ") leftover=$(ps -eo args | grep -E 'web\.app|multiprocessing' | grep -v grep | wc -l)" >> $O/$L.env
cat $O/$L.env $O/$L.json
