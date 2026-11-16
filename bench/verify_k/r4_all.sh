#!/bin/bash
cd /home/user/work/robot_percept
echo "== hashes"; git hash-object web/app.py web/sim_worker.py web/cell_db.py web/cell_executor.py tests/test_cell_exec_r5.py | cut -c1-8 | tr '\n' ' '; echo
git diff --stat sim/ik.py web/cell_state.py | tail -1; git diff --stat sim/grasp.py | tail -1
echo "== expiry"; bash bench/verify_k/run.sh expiry | grep -E '^\{' | python3 -c "
import sys,json
d=json.loads(sys.stdin.read())
print('expired',d['expired_deadline']['result']); print('stale',d['stale_epoch']['result']); print('moved',d['moved'],'per_cid',d['per_cid'],'late',d['late_cmd'],'legacy_after_timeout',d['legacy_place_after_timeout'][0])"
echo "== api"; rm -f /tmp/vk_cell.sqlite3*; bash bench/verify_k/run.sh api | grep -E '^\{' | python3 -c "
import sys,json
d=json.loads(sys.stdin.read())
print('bad',{k:v[0] for k,v in d['bad_payloads'].items()}); print('post',d['tasks_post_ok'][0],'second',d['second_task'],'teleop',d['teleop_post_while_owner'][0],'cancel_unknown',d['cancel'][0])"
echo "== reset"; bash bench/verify_k/run.sh reset | grep -E '^\{' | python3 -c "
import sys,json
d=json.loads(sys.stdin.read())
print({k:(v if not isinstance(v,(list,dict)) else (v[0] if isinstance(v,list) else None)) for k,v in d.items() if k in ('place_while_latched','task_while_latched','place_after_reset','reset_again','reset_ok','reset_missing_confirm','reset_wrong_ack','reset_wrong_version')})
print('reset_ok',d['reset_ok'][0],'epoch',d['cell_after_estop'].get('epoch'),'->',d['cell_after_reset'].get('epoch'),'latch',d['cell_after_reset'].get('stop_latched'))"
echo "== stop N40"; N=40 bash bench/verify_k/run.sh stop > /dev/null 2>&1
python3 - <<'PY'
import json,statistics as s
t=json.load(open('bench/verify_k/out/stop.json'))['trials']
p95=lambda a:sorted(a)[min(len(a)-1,int(round(.95*(len(a)-1))))]
for b in sorted({x['boundary'] for x in t if x['boundary']}):
    v=[x['worker_latency_ms'] for x in t if x['boundary']==b]; print(b,len(v),'p50',round(s.median(v),2),'p95',round(p95(v),2),'max',max(v))
print({x['status'] for x in t},{x['held'] for x in t})
PY
echo "== stopik N20"; N=20 bash bench/verify_k/run.sh stopik >/dev/null 2>&1
python3 - <<'PY'
import json
t=json.load(open('bench/verify_k/out/stopik.json'))['trials']
v=[x['worker_latency_ms'] for x in t]; print(len(v),'max',max(v),{x['boundary'] for x in t})
PY
echo "== restart kill-9 + synthetic rows"
bash bench/verify_k/restart_kill.sh 2>&1 | grep -E '^==|aborted|needs|residual|none' 
echo "== residual"; ps -eo pid,cmd | grep -E 'spawn_main|resource_tracker|vk_live' | grep -v grep || echo none
