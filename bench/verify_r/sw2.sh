cd /home/user/work/robot_percept/bench/verify_r/base_src
for x in downloads FoundationPose .venvs; do [ -e /home/user/work/robot_percept/$x ] && { rm -rf $x; ln -s /home/user/work/robot_percept/$x $x; }; done
pid=$(ss -ltnp | grep ':5092 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p'); kill $pid; sleep 3; echo killed $pid