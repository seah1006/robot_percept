import sys, json, time, argparse, collections
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument('--root',default='/home/user/work/robot_percept'); ap.add_argument('--n',type=int,default=20)
ap.add_argument('--gt',default='on'); ap.add_argument('--home',type=int,default=1); ap.add_argument('--suite',default='single,multi'); ap.add_argument('--out'); ap.add_argument('--objs',default='mustard,box,cup'); ap.add_argument('--s0',type=int,default=0)
a=ap.parse_args()
sys.path.insert(0,a.root)
import numpy as np, mujoco
from sim.env import SimEnv
from sim.control import Controller
CAD=Path('/home/user/work/robot_percept/cad_uploads/converted')
NAMES={'mustard':'mustard','box':'box_fillet_50x30x20mm','cup':'cup_d70_h60mm'}
def add_cad(env,n):
    d=CAD/n; env.add_object_from_mesh(n,d/(n+'.obj'),sorted(d.glob('*_collision_coacd_*.obj')))
def make_env(keys,seed):
    return SimEnv(objects=tuple(NAMES[k] for k in keys),seed=seed)
gtcalls=collections.Counter()
def arm_obj_contacts(env,name):
    m=env.model;d=env.data;bid=m.body(name).id
    arm={m.body(n).id for n in ('hand','left_finger','right_finger')}|{i for i in range(m.nbody) if m.body(i).name.startswith('link') and m.body(i).name!='link0'}
    return sum(1 for c in d.contact[:d.ncon] if (m.geom_bodyid[c.geom1] in arm and m.geom_bodyid[c.geom2]==bid) or (m.geom_bodyid[c.geom2] in arm and m.geom_bodyid[c.geom1]==bid))
def run_one(env,ctl,key,xy):
    name=NAMES[key]; phase=['pick']
    def obj():
        f=sys._getframe(1)
        gtcalls[(phase[0],f.f_code.co_name)]+=1
        return env.T_world_obj(name)
    def raw(): return env.T_world_obj(name)
    r={}
    t=time.perf_counter()
    try:
        orig=raw()
        res=ctl.pick_object(orig,env.registry[name].bounds,object_pose_fn=obj)
        r['pick']=bool(res['ok']); r['lifted']=res.get('lifted')
        if r['pick']:
            phase[0]='place'
            p=ctl.place_object(xy,obj); r['place']=bool(p['err_mm']<20 and p['upright']>.95); r['err_mm']=p['err_mm']
            if a.home and hasattr(ctl,'return_home'):
                phase[0]='home'
                P0=raw()[:3,3].copy(); maxd=0; contacts=0
                orig_step=ctl._step
                def st():
                    nonlocal maxd,contacts
                    orig_step(); maxd=max(maxd,np.linalg.norm(raw()[:3,3]-P0)); contacts+=arm_obj_contacts(env,name)
                ctl._step=st
                try:
                    h=ctl.return_home(obj); r['home_ok']=True; r['home']=h
                except Exception as e:
                    r['home_ok']=False; r['home_err']=str(e)
                ctl._step=orig_step
                q=env.data.qpos[ctl.qadr]; from sim.ik import HOME
                r['home_joint_err']=float(np.max(np.abs(q-np.asarray(HOME)))); r['obj_move_mm']=float(np.linalg.norm(raw()[:3,3]-P0)*1000); r['obj_maxmove_mm']=float(maxd*1000); r['arm_obj_contacts']=int(contacts)
        else: r['place']=False
    except Exception as e: r.update(pick=r.get('pick',False),place=False,error=str(e)[:120])
    r['elapsed']=round(time.perf_counter()-t,1); return r
out={}
for suite in a.suite.split(','):
    if suite=='single':
        for k in a.objs.split(','):
            rows=[]
            for s in range(a.s0,a.s0+a.n):
                env=make_env([k],s); ctl=Controller(env.model,env.data,env=env)
                if hasattr(ctl,'gt_assist'): ctl.gt_assist=(a.gt=='on')
                pos=env.T_world_obj(NAMES[k])[:2,3]
                r=run_one(env,ctl,k,(.50,-.12 if pos[1]>0 else .12)); rows.append(r)
                if not (r['pick'] and r['place']) or r.get('home_ok') is False: print('FAIL',k,s,r,flush=True)
            out[k]=rows
            print('SUMMARY',k,'gt',a.gt,sum(r['pick'] for r in rows),'pick',sum(r['place'] for r in rows),'place',sum(r.get('home_ok',False) for r in rows),'home /',len(rows),flush=True)
    if suite=='multi':
        rows=[]
        for s in range(a.s0,a.s0+a.n):
            env=make_env(['mustard','box','cup'],s); ctl=Controller(env.model,env.data,env=env)
            if hasattr(ctl,'gt_assist'): ctl.gt_assist=(a.gt=='on')
            tr=[run_one(env,ctl,k,xy) for k,xy in zip(('mustard','box','cup'),((.48,-.29),(.56,-.29),(.50,.29)))]
            rows.append(tr)
            print('MULTI',s,[(r['pick'],r['place'],r.get('home_ok')) for r in tr],flush=True)
        out['multi']=rows
        print('SUMMARY multi all3',sum(all(r['pick'] and r['place'] for r in t) for t in rows),'/',len(rows),flush=True)
out['gtcalls']={f'{k[0]}:{k[1]}':v for k,v in gtcalls.items()}
print('GTCALLS',json.dumps(out['gtcalls']))
if a.out: json.dump(out,open(a.out,'w'),indent=1,default=float)