#!/bin/bash
# A/B 트리 동일성 확인: run_g.sh 가 실제로 TREE 를 쓰는지
R=$HOME/work/robot_percept; G=$R/bench/verify_g
for T in /tmp/rp_base_g /tmp/rp_g_snap; do
  ( cd $T; source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
    PYTHONPATH=$T python -c "import web.app,os;print('$T ->',web.app.__file__, hasattr(web.app,'run_server'))" 2>&1 | grep -v bogus )
done
grep -n "^cd\|PYTHONPATH" $G/run_g.sh | cut -c1-160
for L in AB_A1 AB_B1; do grep -c "" $G/out/ab/$L.server.log; head -3 $G/out/ab/$L.server.log | cut -c1-100; done
# 두 번째 단서: A 트리에서 SIGTERM 후 잔존이 run_g 방식(3초 대기)에서도 나오는지 -> repro_mono 가 이미 10초 기준으로 측정
