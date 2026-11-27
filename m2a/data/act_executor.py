"""Execute ACT grasp_lift and compare against the EE-delta IK expert on paired dev seeds."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import numpy as np
from .auto_demo import MAX_TICKS, clipped, command, expert, l0_case, prepare, rise_meter
from .recorder import MASK, STATE, WRIST, mirror_action, observation, policy_observation

_RGB_SIZE = 256*256*3
_MASK_SIZE = 256*256


def _read(stream,n):
    out = bytearray()
    while len(out)<n:
        b = stream.read(n-len(out))
        if not b:
            raise EOFError(f'Policy pipe stopped after {len(out)} of {n} bytes')
        out.extend(b)
    return out


class PolicyBridge:
    """Fixed-shape binary bridge between the sim environment and m2a_lerobot."""
    def __init__(self, python, policy, device, kind="act"):
        self.proc = subprocess.Popen([python,'-m','m2a.data.act_executor','worker',str(policy),'--device',device,'--kind',kind],
                                     stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                     env={**os.environ,'PYTHONUNBUFFERED':'1'})
        self.chunk = None
        self.kind = kind

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        finally:
            self.proc.stdout.close()

    def __call__(self,obs):
        self.proc.stdin.write(obs[WRIST].tobytes()+obs[MASK].tobytes()+obs[STATE].astype('<f4').tobytes())
        if self.kind == 'smolvla':
            text = obs['task'].encode('utf-8')
            if not 0 < len(text) <= 4096: raise ValueError('invalid task length')
            self.proc.stdin.write(len(text).to_bytes(2,'little')+text)
        self.proc.stdin.flush()
        if self.chunk is None:
            self.chunk = int.from_bytes(_read(self.proc.stdout,4),'little')
            if not 1<=self.chunk<=256:
                raise ValueError('Invalid ACT chunk size')
        return np.frombuffer(_read(self.proc.stdout,28*self.chunk),dtype='<f4').reshape(self.chunk,7)


def worker(policy_path,device,kind="act"):
    import contextlib
    wire = sys.stdout.buffer
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from m2a.learn.rocm_compat import torchvision_import
        with torchvision_import():
            from lerobot.configs.policies import PreTrainedConfig
        from .train_act import act_api,smol_api,tensors
        torch.set_num_threads(2)
        _,_,_,Policy,processors = smol_api() if kind == 'smolvla' else act_api()
        cfg = PreTrainedConfig.from_pretrained(policy_path)
        cfg.device = device
        model = Policy.from_pretrained(policy_path,config=cfg,strict=True).eval()
        stats = torch.load(policy_path/'m2a_stats.pt',map_location='cpu',weights_only=True)
        pre,post = processors(cfg,stats)
        wire.write(cfg.chunk_size.to_bytes(4,'little')); wire.flush()
        entry = sys.stdin.buffer
        while True:
            data = entry.read(_RGB_SIZE+_MASK_SIZE+60)
            if not data:
                break
            if len(data)!=_RGB_SIZE+_MASK_SIZE+60:
                raise EOFError('Truncated observation')
            rgb = np.frombuffer(data,np.uint8,count=_RGB_SIZE).reshape(256,256,3).copy()
            mask = np.frombuffer(data,np.uint8,count=_MASK_SIZE,offset=_RGB_SIZE).reshape(256,256,1).copy()
            state = np.frombuffer(data,'<f4',offset=_RGB_SIZE+_MASK_SIZE).copy()
            ob=tensors(torch.from_numpy(rgb).permute(2,0,1)/255.,torch.from_numpy(mask),torch.from_numpy(state))
            if kind == 'smolvla':
                size = int.from_bytes(_read(entry,2),'little')
                ob['task'] = _read(entry,size).decode('utf-8')
            with torch.inference_mode():
                action = post(model.predict_action_chunk(pre(ob)))[0]
            wire.write(action.cpu().numpy().astype('<f4').tobytes()); wire.flush()


def run_grasp_lift(env,arm,oid,policy,*,execute_steps=5,max_ticks=MAX_TICKS):
    """Run only grasp_lift; accepts an initialized env and returns the skill dict."""
    start = perf_counter()
    env.set_grasp_target(arm,oid)
    sample,measure = rise_meter(env,arm,oid)
    grip = 0.; lost=chunks=ik_errors=0; attached=False; closed=False; ticks=0
    reason='TIMEOUT'
    while ticks<max_ticks:
        obs,mask_lost=observation(env,arm,oid,grip)
        lost+=mask_lost; chunks+=1
        chunk=np.asarray(policy(policy_observation(obs,arm)))
        if chunk.ndim!=2 or not len(chunk) or chunk.shape[1]!=7 or not np.isfinite(chunk).all():
            reason='INVALID_ACTION'; break
        for a in chunk[:min(execute_steps,max_ticks-ticks)]:
            if arm=='left':
                a=mirror_action(a)
            grip=float(np.clip(a[6],0,1))
            closed |= grip>=.85
            status=command(env,arm,np.array([*clipped(a[:3],.048),*clipped(a[3:6],.22),grip]))
            ticks += 1
            ik_errors += not status['ok']
            attached |= status['held_oid']==oid
            if sample(status):
                reason=None; break
        if reason is None:
            break
    if reason=='TIMEOUT':
        reason=('MASK_LOST' if lost==chunks else 'IK_FAIL' if ik_errors>ticks/2
                else 'GRASP_SLIP' if closed and not attached else 'LIFT_SHORT' if attached else 'TIMEOUT')
    ok = reason is None
    return dict(ok=ok,reason_code=reason,internal_done=ok,t_ms=int((perf_counter()-start)*1000),
                mask_lost_chunks=lost,chunks=chunks,ik_errors=ik_errors, ticks=ticks,
                attached=attached,closed=closed,**measure())


def wilson(success,total):
    z=1.959963984540054; p=success/total; base=1+z*z/total
    mid=(p+z*z/(2*total))/base
    margin=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/base
    return max(0,mid-margin),min(1,mid+margin)


def summarize(results, boots=10000):
    """Wilson CIs per method + paired difference (ACT-IK), percentile bootstrap over scenes (seed 41, arbitrary)."""
    summary={}
    for mode in ('IK','ACT'):
        rows=results[mode]; win=sum(row['ok'] for row in rows)
        summary[mode]=dict(success=win,n=len(rows),wilson95=wilson(win,len(rows)),
                           failures=Counter(r['reason_code'] for r in rows if not r['ok']))
    assert [r['seed'] for r in results['IK']]==[r['seed'] for r in results['ACT']]
    ik=np.array([r['ok'] for r in results['IK']],float); act=np.array([r['ok'] for r in results['ACT']],float)
    d=act-ik; n=len(d); rng=np.random.default_rng(41)
    lo,hi=np.percentile(d[rng.integers(n,size=(boots,n))].mean(1),[2.5,97.5])
    both=int((ik*act).sum()); only_ik=int((ik*(1-act)).sum()); only_act=int((act*(1-ik)).sum())
    summary['paired']=dict(diff_act_minus_ik=float(d.mean()),bootstrap95=[float(lo),float(hi)],
        both_ok=both,only_ik=only_ik,only_act=only_act,neither=n-both-only_ik-only_act,
        conclusion='difference not demonstrated (CI contains 0)' if lo<=0<=hi else 'difference demonstrated')
    return summary


def evaluate(a):
    from m2a.sim.g1_manip_env import G1ManipEnv
    if not 10000<=a.start<=a.end<=10199 or min(a.count,a.execute_steps)<=0:
        raise ValueError('dev range 10000..10199 and positive execute_steps required')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    results={'IK':[],'ACT':[]}
    env=G1ManipEnv()
    try:
        with PolicyBridge(a.python,a.policy,a.device) as policy, a.output.open('x',buffering=1) as log:
            for seed in range(a.start,a.end+1):
                spec,oid,arm,digest=l0_case(seed,'dev')
                if a.part and next(o['part_id'] for o in spec['objects'] if o['oid']==oid)!=a.part:
                    continue
                if len(results['IK']) >= a.count:
                    break
                rng=prepare(env,spec,arm)
                env.set_gate_mode(a.grasp_mode)
                env.set_grasp_target(arm,oid)
                for mode in ('IK','ACT'):
                    if mode=='IK':
                        _,r=expert(env,arm,oid,rng)
                    else:
                        prepare(env,spec,arm)
                        r=run_grasp_lift(env,arm,oid,policy,execute_steps=a.execute_steps)
                    row=dict(r,method=mode,seed=seed,arm=arm,oid=oid,scene_digest=digest,
                             part=env.object_parts[oid], grasp_mode=a.grasp_mode, action_encoding='ee_delta_table_v1')
                    results[mode].append(row)
                    print(json.dumps(row),file=log)
    finally:
        env.close()
    if not results['IK']:
        raise ValueError('No matching dev seeds')
    summary=summarize(results)
    a.output.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='mode',required=True)
    w=sub.add_parser('worker'); e=sub.add_parser('eval')
    for parser in (w,e):
        parser.add_argument('policy',type=Path)
        parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    w.add_argument('--kind',choices=['act','smolvla'],default='act')
    e.add_argument('output',type=Path)
    e.add_argument('--grasp-mode',choices=('P-gate','P-gate-strict'),required=True)
    e.add_argument('--python',required=True)
    e.add_argument('--start',type=int,default=10000); e.add_argument('--end',type=int,default=10029)
    e.add_argument('--part'); e.add_argument('--count',type=int,default=30)
    e.add_argument('--execute-steps',type=int,default=5)
    a=p.parse_args()
    worker(a.policy,a.device,a.kind) if a.mode=='worker' else evaluate(a)


if __name__=='__main__':
    main()
