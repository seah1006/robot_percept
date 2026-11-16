#!/bin/bash
cd /home/user/work/robot_percept
q(){ python3 - <<'PY'
import sqlite3,json
for i,s,p in sqlite3.connect('/tmp/vk_cell.sqlite3').execute('select id,state,payload from tasks'):
    print(i[:8],s,json.loads(p).get('reason'))
PY
}
echo "== DB before restart"; q
bash bench/verify_k/run.sh keys >/dev/null 2>&1
echo "== DB after new boot"; q
ps -eo pid,etimes,cmd | grep -E 'resource_tracker|spawn_main|vk_live' | grep -v grep || echo "no residual"
