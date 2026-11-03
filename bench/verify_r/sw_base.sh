cd /home/user/work/robot_percept/bench/verify_r/base_src
for x in assets cad_uploads sim_test; do rm -rf $x; ln -s /home/user/work/robot_percept/$x $x; done
pid=$(ss -ltnp | grep ':5092 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p'); echo kill $pid; kill $pid; sleep 3
ss -ltnp | grep ':5092 ' || echo freed