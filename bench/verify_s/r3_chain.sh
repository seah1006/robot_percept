#!/bin/bash
# usage: r3_chain.sh TREE TAG   -- sequence of server holds (each <=295s under measure lock), results bench/verify_s/out_<TAG>_*.json
T=$1; G=$2; D=/home/user/work/robot_percept/bench/verify_s
bash $D/r3_srv_job.sh $T ${G}_stON "STATOPT=1" static,release > /dev/null 2>&1
for p in sweep chest jump twist; do bash $D/r3_srv_job.sh $T ${G}_pat_$p "COLLPAT=$p" coll1 > /dev/null 2>&1; done
bash $D/r3_srv_job.sh $T ${G}_asymON "STATOPT=1" asym > /dev/null 2>&1
bash $D/r3_srv_job.sh $T ${G}_off "STATOPT=0" static,asym > /dev/null 2>&1
bash $D/r3_srv_job.sh $T ${G}_p1b "STATOPT=0" dynv,degen > /dev/null 2>&1
echo ALLDONE > $D/chain_$G.done
