import sys, json, time, argparse
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument('--root'); ap.add_argument('--seeds',type=int,default=30); ap.add_argument('--out'); ap.add_argument('--objs',default='mustard,box,cup')
a=ap.parse_args()
sys.path.insert(0,a.root)
import numpy as np
from sim.env import SimEnv
from sim.grasp import choose_grasp
CAD=Path('/home/user/work/robot_percept/cad_uploads/converted')
NAMES={'mustard':'mustard','box':'box_fillet_50x30x20mm','cup':'cup_d70_h60mm'}
def make_env(k,seed):
    n=NAMES[k]
    env=SimEnv(objects=(n,),seed=seed)
    return env,n
if __name__=='__main__':
    res={}
    for k in a.objs.split(','):
        ts=[];ok=0;modes=[]
        for s in range(a.seeds):
            env,name=make_env(k,s)
            t=time.perf_counter()
            try:
                p=choose_grasp(env.model,env.data,env.T_world_obj(name),env.registry[name].bounds); ok+=1; modes.append(p['mode'])
            except Exception as e: modes.append('FAIL')
            ts.append(time.perf_counter()-t)
        q=lambda x:round(float(np.quantile(ts,x)),3)
        res[k]=dict(p50=q(.5),p95=q(.95),max=round(max(ts),3),ok=ok,n=a.seeds,modes={m:modes.count(m) for m in set(modes)})
        print(k,res[k],flush=True)
    json.dump(res,open(a.out,'w'),indent=1)