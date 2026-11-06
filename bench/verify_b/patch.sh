#!/bin/bash
cd ~/work/robot_percept/bench/verify_g
kill -9 13313 13314 13287 2>/dev/null; sleep 1
echo after_cleanup workers=$(ps -eo args | grep -E 'multiprocessing|web\.app' | grep -v grep | wc -l) listener=$(ss -ltn | grep -c :5092)
# 비대화형 셸의 & 는 SIGINT를 무시시킴 -> 기본 동작으로 복원하는 런처 사용
sed -i 's|python -m web.app > \$OUT/\$L.log 2>&1 &|python -c "import signal,os;signal.signal(signal.SIGINT,signal.default_int_handler);os.execvp(\\"python\\",[\\"python\\",\\"-m\\",\\"web.app\\"])" > $OUT/$L.log 2>\&1 \&|' repro.sh
sed -i 's|^for SIG in TERM INT KILL; do|for SIG in ${SIGS:-TERM INT KILL}; do|' repro.sh
grep -n "web.app\|for SIG" repro.sh
mkdir -p out/base_part1; cp out/base/summary.txt out/base_part1/
