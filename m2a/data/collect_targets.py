"""Recollect successful demonstrations with the exact evaluation servo."""
import argparse
from collections import Counter
import json
from pathlib import Path
from time import sleep
import numpy as np
from .auto_demo import prepare
from .ee_target import ACTION_ENCODING, GATE_MODES, apply_target
from .recorder import observation, write_npz
from .round3 import TASKS, case_for, scripted
from .replay_f3 import load_episode


def candidates(base):
    """Nominal plan, then fixed retiming and grasp offsets (arbitrary)."""
    yield 'nominal',base
    i=np.flatnonzero(base[:,6]>=.85)
    if not len(i): return
    close=int(i[0]); last=int(i[-1]); final=base[last].copy()
    lift=np.flatnonzero(base[close:last+1,2] > base[close,2]+.009)
    if not len(lift): return
    j=close+int(lift[0]); grip=base[close].copy();grip[6]=1.
    for dz,hold in [(0.,5),(-.004,5),(.004,5),(-.008,6),(.008,6)]:
        pre=base[:close].copy(); end=base[j:last+1].copy(); g=grip.copy()
        g[2]+=dz
        pre[-min(7,len(pre)):,2]+=dz*np.linspace(0,1,min(7,len(pre)))
        end[:,2]+=dz*np.linspace(1,0,len(end)); end[:,6]=1.
        yield f'dz={dz},hold={hold}',np.vstack([pre,np.repeat(g[None,:],hold,0),end,np.repeat(final[None,:],12,0)])


def execute(env,case,actions,mode,record=False):
    spec,oid,arm,_,_=case
    prepare(env,spec,arm); env.set_gate_mode(mode); env.set_grasp_target(arm,None)
    z0=env.get_gt_objects()[oid]['xyz'][2]
    rows=[]; hold=0; grip=0.; lost=0; max_rise=0.; last_held=None
    for tick,a in enumerate(actions,1):
        if record:
            obs,missing=observation(env,arm,oid,grip);lost+=missing
            rows.append(dict(obs,action=np.array(a,dtype=np.float32)))
        grip=float(a[6]); st=apply_target(env,arm,a); last_held=st['held_oid']
        rise=env.to_table(env.data.xpos[env.object_bodies[oid]])[2]-z0
        max_rise=max(max_rise,rise)
        hold=hold+1 if last_held==oid and rise>=.055 else 0
        if hold>=20:
            return rows,dict(ok=True,reason_code=None,ticks=tick,max_rise_m=max_rise,mask_lost_frames=lost if record else None)
    return [],dict(ok=False,reason_code='LIFT_SHORT' if last_held==oid else 'GRASP_SLIP',ticks=len(actions),max_rise_m=max_rise)


def main():
    from m2a.sim.g1_manip_env import G1ManipEnv
    from .ee_target import recover_targets
    from .recorder import STATE
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('dest',type=Path)
    p.add_argument('--part',required=True,choices=TASKS);p.add_argument('--grasp-mode',required=True,choices=GATE_MODES)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--count',type=int,default=100);p.add_argument('--commit',required=True)
    a=p.parse_args(); a.dest.mkdir(parents=True,exist_ok=True); env=G1ManipEnv(); counts=Counter()
    done=set()
    log_path=a.dest/f'attempts_{a.part}_targets.jsonl'
    if a.resume:
        for path in a.dest.glob('*.npz'):
            meta,_=load_episode(path)
            if meta.get('grasp_mode')!=a.grasp_mode or meta.get('task')!=TASKS[a.part]:
                raise ValueError(f'incompatible resume episode: {path}')
            done.add(meta['scene_seed'])
        counts[None]=len(done)
        # If the interruption left a partial log line, preserve it as a separate line.
        if log_path.exists():
            raw=log_path.read_bytes()
            with log_path.open('ab') as f:
                if raw and not raw.endswith(b'\n'): f.write(b'\n')
            for line in raw.splitlines():
                try: row=json.loads(line)
                except json.JSONDecodeError: continue
                if not row['ok']: done.add(row['seed'])
    try:
        if counts[None]>=a.count: return
        with log_path.open('a' if a.resume else 'x',buffering=1) as log:
            old={r['seed']:r for f in sorted(a.source.glob(f'attempts_{a.part}_*.jsonl'))
                 for l in f.read_text().splitlines() if l.endswith('}') and (r:=json.loads(l))['ok']}
            def plans():
                for seed in sorted(old):
                    if seed in done: continue
                    path=a.source/f'{seed:05}.npz'; m,base=load_episode(path)
                    case=case_for(seed,'train',m['arm'])
                    if case[3]!=m['scene_digest']: raise ValueError('scene digest mismatch')
                    yield case,base
                for seed in range(5000):
                    if seed in old or seed in done: continue
                    try: case=case_for(seed,'train')
                    except ValueError: continue
                    if not case or case[4]!=a.part: continue
                    rows,result=scripted(env,case,record=True,grasp_mode=a.grasp_mode,render_images=False)
                    if not result['ok'] or not rows: continue
                    yield case,recover_targets(np.stack([r[STATE] for r in rows]),np.stack([r['action'] for r in rows]))
            for case,base in plans():
                spec,oid,arm,digest,part=case; seed=spec['seed']
                for variant,action in candidates(base):
                    _,result=execute(env,case,action,a.grasp_mode)
                    if result['ok']:
                        rows,result=execute(env,case,action,a.grasp_mode,record=True)
                        if result['ok']:
                            write_npz(a.dest/f'{seed:05}.npz',rows,seed=seed,part=part,mode=a.grasp_mode,
                                arm=arm,task=TASKS[part],provenance=dict(action_encoding=ACTION_ENCODING,
                                grasp_mode_name=a.grasp_mode,commit=a.commit, scene_digest=digest,
                                distractors=len(spec['objects'])-1,expert_variant=variant,source_servo='10hz_absolute'))
                            break
                counts[result['reason_code']]+=1
                print(json.dumps(dict(result,seed=seed,part=part,grasp_mode=a.grasp_mode,
                    action_encoding=ACTION_ENCODING,distractors=len(spec['objects'])-1,variant=variant)),file=log)
                if counts[None]>=a.count: break
    finally: env.close()
    print(a.part,counts,flush=True)


if __name__=='__main__': main()
