"""Paired right-arm L0 eval and command/mask disagreement probes."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import itertools
import json
from pathlib import Path
from time import perf_counter
import numpy as np
from .act_executor import PolicyBridge, wilson
from .auto_demo import prepare
from .ee_target import ACTION_ENCODING,GATE_MODES,apply_target
from .recorder import MASK, observation
from .round3 import TASKS, dev_cases, scripted

METHODS = ('IK', 'ACT', 'SmolVLA')


def paired(rows, boots=10000):
    by_method = {m:{(r['seed'],r['scene_digest']):r for r in rows if r['method']==m} for m in METHODS}
    keys = sorted(set.intersection(*(set(d) for d in by_method.values())))
    if not keys: return dict(n=0)
    n = len(keys)
    indices = np.random.default_rng(41).integers(n,size=(boots,n))
    values = {m:np.asarray([int(d[k]['ok']) for k in keys]) for m,d in by_method.items()}
    out = dict(n=n, methods={}, paired={})
    for m, val in values.items():
        data = [by_method[m][k] for k in keys]
        lat = [v for r in data for v in r.get('latency_ms', [])]
        s = int(val.sum())
        out['methods'][m] = dict(success=s, wilson95=wilson(s,n),
            failure_types=dict(Counter(r['reason_code'] for r in data if not r['ok'])),
            bridge_ms_p50_p95=np.percentile(lat,[50,95]).tolist() if lat else None,
            bridge_samples=len(lat))
    for base, model in itertools.combinations(METHODS,2):
        d = values[model]-values[base]
        lo, hi = np.percentile(d[indices].mean(1),[2.5,97.5])
        out['paired'][f'{model}-{base}'] = dict(diff=float(d.mean()), bootstrap95=[float(lo),float(hi)],
             only_base=int((d==-1).sum()),only_model=int((d==1).sum()),
             conclusion='차이 입증 안 됨' if lo<=0<=hi else '차이 입증')
    return out


def rollout(env, case, policy, task_oid, mask_oid, execution=5, grasp_mode='P-gate'):
    spec, target, arm, _, _ = case
    prepare(env,spec,arm)
    env.set_gate_mode(grasp_mode)
    env.set_grasp_target(arm,None)  # never pass the target to learned control
    grip = 0.; seen = []; lat = []; error = ticks = lost = hold = 0; closed = False
    z0 = env.get_gt_objects()[target]['xyz'][2]
    phase = None; max_rise = 0.
    for _ in range(0,110,execution):
        obs, missing = observation(env,arm,mask_oid or target,grip)
        if mask_oid is None: obs[MASK].fill(0)
        lost += missing
        obs['task'] = TASKS[env.object_parts[task_oid]]
        t0=perf_counter(); actions = policy(obs); dt=(perf_counter()-t0)*1000
        if getattr(policy,'warmed',False): lat.append(dt)
        policy.warmed=True
        if not np.isfinite(actions).all(): phase='INVALID_ACTION'; break
        for cmd in actions[:execution]:
            grip = float(np.clip(cmd[6],0.,1.)); closed |= grip>=.85
            status = apply_target(env,arm,np.r_[cmd[:6],grip]); ticks += 1
            error += not status['ok']
            oid = status['held_oid']
            if oid is not None and oid not in seen: seen.append(oid)
            rise = env.to_table(env.data.xpos[env.object_bodies[target]])[2] - z0
            max_rise = max(max_rise,rise)
            hold = hold+1 if oid==target and rise>=.055 else 0
            if hold >= 20: break
        if hold >= 20: break
    if hold < 20 and phase is None:
        phase = ('WRONG_OBJECT' if seen and target not in seen else 'IK_FAIL' if error>ticks/2 else
                 'LIFT_SHORT' if target in seen else 'GRASP_SLIP' if closed else 'TIMEOUT')
    return dict(ok=phase is None,reason_code=phase,held_oids=seen, first_held=seen[0] if seen else None,
                task_oid=task_oid,mask_oid=mask_oid,latency_ms=lat,ticks=ticks,ik_errors=error,
                mask_lost_chunks=lost,max_rise_m=max_rise)


def summarize(rows):
    out = {'overall':paired(rows)}
    for part in TASKS:
        out[part] = paired([r for r in rows if r['part']==part])
    lang = defaultdict(Counter)
    for r in rows:
        if not r.get('probe'): continue
        held = r['first_held']; t, m = r['task_oid'],r['mask_oid']
        key = ('none' if held is None else 'both' if held==t==m else 'language' if held==t else
               'mask' if held==m else 'other')
        lang[r['method']][key] += 1
    out['target_selection_first_weld'] = {k:dict(v) for k,v in lang.items()}
    return out


def main():
    from m2a.sim.g1_manip_env import G1ManipEnv
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('out',type=Path); p.add_argument('--python',required=True)
    p.add_argument('--act',type=Path,required=True);p.add_argument('--smol',type=Path,required=True)
    p.add_argument('--grasp-mode',choices=GATE_MODES,required=True)
    p.add_argument('--device',default='cuda',choices=['cpu','cuda'])
    p.add_argument('--count',type=int,default=20); p.add_argument('--part',required=True,choices=TASKS)
    p.add_argument('--skip',type=int,default=0); p.add_argument('--probes',type=int,default=4)
    a=p.parse_args()
    for policy in (a.act,a.smol):
        run_info=json.loads((policy/'m2a_run.json').read_text())
        if (run_info['action_encoding'],run_info['grasp_mode'])!=(ACTION_ENCODING,a.grasp_mode):
            p.error(f'{policy}: mismatched action encoding or grasp mode')
    env=G1ManipEnv()
    rows=[]; probes=0; matched=0; evaluated=0
    try:
        with ExitStack() as stack:
            handles={name:stack.enter_context(PolicyBridge(a.python,path,a.device,kind)) for name,path,kind in
                     [('ACT',a.act,'act'),('SmolVLA',a.smol,'smolvla')]}
            log=stack.enter_context(a.out.open('x',buffering=1))
            for case in dev_cases(a.part):
                matched += 1
                if matched <= a.skip: continue
                spec,oid,arm,digest,part=case
                seed = spec['seed']
                _,ik=scripted(env,case,minimum_rise=.055,grasp_mode=a.grasp_mode)
                modes={'IK':dict(ik), **{m:rollout(env,case,pol,oid,oid,grasp_mode=a.grasp_mode) for m,pol in handles.items()}}
                other = next((o['oid'] for o in spec['objects'] if o['oid']!=oid and o['part_id'] in TASKS),None)
                if other and probes<a.probes:
                    probes += 1
                    for mode,task,mask in [('SmolVLA_baseline_probe',oid,oid),('SmolVLA_language_only',oid,None),
                                           ('SmolVLA_conflicting_language',other,oid),('SmolVLA_conflicting_mask',oid,other)]:
                        modes[mode]=dict(modes['SmolVLA'] if mode.endswith('baseline_probe') else
                                            rollout(env,case,handles['SmolVLA'],task,mask,grasp_mode=a.grasp_mode),probe=True)
                for mode,r in modes.items():
                    row=dict(r,method=mode,seed=seed,part=part,arm=arm,oid=oid,scene_digest=digest,
                             distractors=len(spec['objects'])-1,grasp_mode=a.grasp_mode,action_encoding=ACTION_ENCODING)
                    rows.append(row); print(json.dumps(row),file=log)
                evaluated += 1
                if evaluated>=a.count: break
    finally:
        env.close()
    a.out.with_suffix('.summary.json').write_text(json.dumps(summarize(rows),ensure_ascii=False,indent=2))
    print(f'{a.part}: {evaluated} paired scenes, {probes} probes', flush=True)


if __name__=='__main__': main()