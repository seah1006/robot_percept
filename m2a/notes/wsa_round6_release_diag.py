"""Run from repo root: python -m m2a.notes.wsa_round6_release_diag baseline|tune.
Use round-5 code for baseline, round-6 candidate for tune.
"""
import json, math, sys
from collections import Counter
from pathlib import Path
import numpy as np
from m2a.sim import skill_bench as b
from m2a.sim.skills import SkillRunner
from m2a.sim.g1_manip_env import G1ManipEnv
root=Path('m2a/notes/wsa_gate_raw')
rows=[json.loads(l) for l in (root/'bench_r5_final.jsonl').open()]
for c in (0,3):
    ff=[r for r in rows if r['clutter']==c and r['stage']=='grasp_lift' and r['reason']=='GRASP_SLIP']
    for f in [lambda r:r['part_id'],lambda r:r['source'],lambda r:r['skills']['grasp_lift']['events']['stage'],lambda r:tuple(r['skills']['grasp_lift']['events']['weld_fingers'] or ()),lambda r:tuple(r['skills']['grasp_lift']['events']['peak_fingers'])]:
        print(c,Counter(map(f,ff)))
    for subset in [ff,[r for r in rows if r['clutter']==c and r.get('skills',{}).get('grasp_lift',{}).get('ok')]]:
        def near(r):
            a,*rest=r['spec']['objects']; d=min([math.dist(a['xyz'][:2],o['xyz'][:2]) for o in rest], default=math.inf)
            return '<8cm' if d<.08 else '8-12cm' if d<.12 else '12+cm' if rest else 'none'
        print(c,Counter(map(near,subset)))
    for pid in ['P04','P06']:
        rr=[r for r in rows if r['part_id']==pid and r['dest']=='put_aside' and 'judge' in r and r['clutter']==c]
        print(c,pid,[(r['seed'],r['reason'],r['skills']['place']['events'].get('place_touched')) for r in rr])
variant=sys.argv[1] if len(sys.argv)>1 else 'baseline'
trace=[]
state={'opening':False,'arm':None}
def snap(sk,label):
    e=sk.env; oid='o0'; d=e.data; pos=e.get_gt_objects()[oid]
    trace.append(dict(phase=label,time=float(d.time),xyz=pos['xyz'],speed=pos['lin_speed'],up=abs(float(d.xmat[e.object_bodies[oid],8])),touch=sk._touching_support(oid),fingers=sorted(e.contact_fingers(state['arm'],oid))))
opening_attr = "_open" if variant == "baseline" else "_staged_release"
origopen=getattr(SkillRunner, opening_attr)
origmove=SkillRunner._move
origstep=G1ManipEnv.step
def opening(sk,arm,p):
    if sk.held:
        state.update(opening=True,arm=arm,sk=sk,steps=0,moving=False); snap(sk,'before_open')
    return origopen(sk,arm,p)
def stepping(env,n=1):
    ans=origstep(env,n)
    if state["opening"] and not state["moving"] and (variant == "baseline" or n>1 or int(round(env.data.time/env.model.opt.timestep))%10==0):
        state['steps']+=1
        snap(state['sk'],f"opening_step_{state['steps']}")
    return ans
def moving(sk,arm,q,sec,*a,**kw):
    if state['opening']:
        state['moving']=True; snap(sk,'retreat_start')
    ans=origmove(sk,arm,q,sec,*a,**kw)
    if state['opening']:
        snap(sk,'retreat_end')
    return ans
setattr(SkillRunner, opening_attr, opening); SkillRunner._move=moving; G1ManipEnv.step=stepping
allowed={r['seed'] for r in rows if r['dest']=='put_aside' and r['part_id'] in ['P04','P06'] and 'judge' in r}
trials=[t for t in b.all_trials(2,parts=['P04','P06'],dests=['put_aside']) if t['seed'] in allowed]
with (root/f'bench_r6_release_diag_{variant}.jsonl').open('w') as f:
    for t in trials:
        trace.clear(); state['opening']=False
        r=b.run_trial(t); r['release_trace']=trace
        f.write(json.dumps(r,default=float)+'\n'); f.flush()
        print(t['seed'],r['reason'],[(p['phase'],round(p['up'],2),round(p['xyz'][2],3),p['touch']) for p in trace])
