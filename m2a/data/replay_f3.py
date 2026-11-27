"""Migrate old actions without altering source data; validate fixed samples open-loop."""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
from .auto_demo import prepare
from .ee_target import ACTION_ENCODING, GATE_MODES, apply_target, recover_targets
from .recorder import STATE
from .round3 import TASKS, case_for


def load_episode(path):
    with np.load(path,allow_pickle=False) as z:
        meta=json.loads(z['metadata'].item())
        action=z['action']
        if meta.get('action_encoding') != ACTION_ENCODING:
            if meta.get('action_encoding') not in (None,'ee_delta_table_v1'):
                raise ValueError(f'Unknown action representation: {meta}')
            action=recover_targets(z[STATE],action)
    return meta,action


def migrate(source,dest):
    dest.mkdir(parents=True,exist_ok=True)
    for p in sorted(source.glob('*.npz')):
        out=dest/p.name
        if out.exists(): continue
        meta,action=load_episode(p)
        with np.load(p,allow_pickle=False) as ep:
            cols={k:ep[k] for k in ep.files if k not in ('metadata','action')}
        # Historical old files from F3 record string grasp_mode_name in provenance.
        mode=meta.get('grasp_mode_name',meta.get('grasp_mode'))
        if mode not in GATE_MODES: raise ValueError(f'unknown original grasp_mode in {p}')
        meta.update(action_encoding=ACTION_ENCODING,grasp_mode=mode)
        tmp=out.with_suffix('.tmp')
        with tmp.open('wb') as f:
            np.savez_compressed(f,**cols,action=action,metadata=json.dumps(meta))
        tmp.replace(out)


def replay(env,case,action,mode):
    spec,oid,arm,_,_=case
    prepare(env,spec,arm)
    env.set_gate_mode(mode)
    env.set_grasp_target(arm,None)
    z0=env.get_gt_objects()[oid]['xyz'][2]
    hold=max_hold=ik_errors=0; seen=[]; max_rise=0.
    for a in action:
        st=apply_target(env,arm,a)
        held=st['held_oid']
        if held is not None and held not in seen: seen.append(held)
        rise=env.to_table(env.data.xpos[env.object_bodies[oid]])[2]-z0
        hold=hold+1 if held==oid and rise>=.055 else 0
        max_hold=max(hold,max_hold); max_rise=max(max_rise,rise)
        ik_errors+=not st['ik_ok']
    return dict(ok=max_hold>=20, max_rise_m=max_rise, hold_ticks=max_hold, held_oids=seen, ik_errors=ik_errors)


def gate(source,output,parts,count,mode):
    from m2a.sim.g1_manip_env import G1ManipEnv
    from .recorder import PART_IDS
    valid=Counter(); wins=Counter(); env=G1ManipEnv()
    try:
        with output.open('x',buffering=1) as log:
            for path in sorted(source.glob('*.npz')):
                m,a=load_episode(path)
                part=next(k for k,v in PART_IDS.items() if v==m['target_part'])
                if part not in parts or valid[part]>=count: continue
                if m.get('grasp_mode_name',m.get('grasp_mode'))!=mode: raise ValueError('mode mismatch')
                seed=m['scene_seed']; case=case_for(seed,'train',m['arm'])
                if case[3]!=m['scene_digest']: raise ValueError(f'scene digest mismatch for {seed}')
                row=replay(env,case,a,mode)
                valid[part]+=1; wins[part]+=row['ok']
                print(json.dumps(dict(row,seed=seed,part=part,file=path.name,grasp_mode=mode,
                                       action_encoding=ACTION_ENCODING)),file=log)
                if all(valid[p]>=count for p in parts): break
    finally: env.close()
    result={p:dict(success=wins[p],total=valid[p],rate=wins[p]/max(1,valid[p]),
                 passed=valid[p]>=count and wins[p]*5>=valid[p]*4) for p in parts}
    passed=all(v['passed'] for v in result.values())
    summary=dict(passed=passed,parts=result,grasp_mode=mode,action_encoding=ACTION_ENCODING)
    output.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)
    return passed


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    for k in ('migrate','gate'):
        q=sub.add_parser(k);q.add_argument('source',type=Path);q.add_argument('dest',type=Path)
        if k=='gate':
            q.add_argument('--part',choices=TASKS,action='append');q.add_argument('--count',type=int,default=10)
            q.add_argument('--grasp-mode',choices=GATE_MODES,required=True)
    a=p.parse_args()
    if a.cmd=='migrate': migrate(a.source,a.dest)
    elif a.count<10: p.error('at least 10 expert successes per part')
    elif not gate(a.source,a.dest,a.part or list(TASKS),a.count,a.grasp_mode): raise SystemExit(2)


if __name__=='__main__': main()
