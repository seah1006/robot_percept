#!/bin/bash
# usage: run_tick.sh TREE PREFIX REPS
TREE=$1; P=$2; N=${3:-2}
for r in $(seq 1 $N); do for pat in sweep chest jump twist; do
  ./job.sh $TREE ${P}_r${r}_$pat "COLLPAT=$pat" coll0,coll1 > /dev/null 2>&1
done; done
echo ALLDONE > /home/my/rp_s3/vs3_$P.done
