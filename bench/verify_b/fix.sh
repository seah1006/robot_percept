#!/bin/bash
# 수정본 검증: 작업 트리 스냅샷 -> repro.sh (monotonic 시간, 10회) 
R=$HOME/work/robot_percept; T=/tmp/rp_g_snap; rm -rf $T; mkdir $T
cd $R; cp -r web $T/; for f in $(ls $R); do [ -e $T/$f ] || ln -s $R/$f $T/$f; done
echo "snapshot web hash: $(cd $T && find web -name '*.py' | sort | xargs sha1sum | sha1sum | cut -c1-12)"
sed -e "s|\$(date +%s.%N)|\$(awk '{print \$1}' /proc/uptime)|g" bench/verify_g/repro.sh > bench/verify_g/repro_mono.sh
# MJPEG 구독자 1개를 붙이는 옵션
sed -i 's|^  sleep 1$|  if [ -n "$MJPEG" ]; then curl -s -m 60 localhost:$PORT/stream -o /dev/null \& sleep 0.5; fi; sleep 1|' bench/verify_g/repro_mono.sh
chmod +x bench/verify_g/repro_mono.sh
grep -c uptime bench/verify_g/repro_mono.sh
SIGS="${SIGS:-TERM INT KILL}" flock -w 900 /tmp/rp_measure.lock bash bench/verify_g/repro_mono.sh $T $R/bench/verify_g/out/${OUTN:-fix} ${N:-10} 2>&1 | grep -v bogus | cut -c1-200
