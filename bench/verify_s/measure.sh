#!/bin/bash
# usage: measure.sh TAG [parts]  -- runs base_s.py against 5094 under the global measure lock
TAG=$1; PARTS=${2:-static,dyn,drop,occ,degen,coll}
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd /home/user/work/robot_percept; export PYTHONPATH=$PWD
echo "load before: $(cat /proc/loadavg)"; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
flock -w 900 /tmp/rp_measure.lock timeout 295 python bench/verify_s/base_s.py http://127.0.0.1:5094 $TAG $PARTS
echo "load after: $(cat /proc/loadavg)"; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
