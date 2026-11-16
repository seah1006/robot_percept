#!/bin/bash
# kill -9 후 재기동 시 nonterminal -> aborted/server_restart, 잔존 프로세스 확인
cd /home/user/work/robot_percept
rm -f /tmp/vk_cell.sqlite3*
dump(){ python3 - <<'PY'
import sqlite3,json
for i,s,p in sqlite3.connect('/tmp/vk_cell.sqlite3').execute('select id,state,payload from tasks'):
    print(i[:8],s,json.loads(p).get('reason'))
PY
}
bash bench/verify_k/run.sh killme 2>&1 | grep -E '^\{|exit' | head -c 900; echo
echo "== DB after kill -9 (before restart)"; dump
sleep 3; echo "== residual after kill -9 (3s)"; ps -eo pid,ppid,etimes,cmd | grep -E 'spawn_main|resource_tracker|vk_live|multiprocessing' | grep -v grep || echo none
bash bench/verify_k/run.sh keys >/dev/null 2>&1
echo "== DB after restart"; dump
