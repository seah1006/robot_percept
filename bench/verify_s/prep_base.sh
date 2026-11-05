set -e
cd /home/user/work/robot_percept
rm -rf /tmp/vs_base; mkdir -p /tmp/vs_base
git archive 1da4b93 | tar -x -C /tmp/vs_base
for d in assets; do [ -e /tmp/vs_base/$d ] || echo "missing $d"; done
ls /tmp/vs_base/assets 2>/dev/null | head
ls assets | head
cat sim_test/gl_env.sh
