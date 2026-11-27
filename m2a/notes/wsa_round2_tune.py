"""Try opposed plate profiles without changing the enabled contact gate."""
import json
from pathlib import Path
from m2a.sim.g1_manip_env import G1ManipEnv
from m2a.sim.gate_grasp import run_batch
from m2a.sim.grasp_profiles import PROFILES
from m2a.sim import gate_grasp
from m2a.common import load_parts

def run(name, offset, delay, middle, width):
    env=G1ManipEnv()
    if width is not None:
        import m2a.sim.g1_manip_env as mod
        def narrow(*args, **kwargs):
            data=load_parts(*args,**kwargs)
            for pid in ('P01','P02','P03'):
                data['parts'][pid]['size'][1]=width
            return data
        gate_grasp.load_parts=mod.load_parts=narrow
    if width is None:
        # Approach along the plate's long side: Dex3 thumb/index span its width.
        PROFILES['parts']['P01']={**PROFILES['parts']['P04'], 'name':name,
            'offset_hand_m':offset,'thumb_delay':delay,
            'close':[0,.64,1.32,-1.05,-1.3,*middle], 'approach_yaw_offset':0.}
    elif name == 'width040_default':
        PROFILES['parts'].pop('P01',None)
    else:
        PROFILES['parts']['P01']={**PROFILES['parts']['P04'], 'name':name,
            'offset_hand_m':offset,'thumb_delay':delay,
            'close':[0,.64,1.32,-1.05,-1.3,*middle], 'approach_yaw_offset':0.}
    out=Path('m2a/notes/wsa_gate_raw')/f'gate_round2_tune_{name}.jsonl'
    n=0
    with out.open('w') as f:
        for row in run_batch(env,'P01','P-gate',0,20):
            n += row['ok']; f.write(json.dumps(row)+'\n'); f.flush()
    print(name,n,flush=True)
    return n

if __name__=='__main__':
    results=[run('plateA',[0,0,0],.35,[-.6,-.65],None),
             run('plateB',[-.014,0,-.010],.52,[0,0],None),
             run('plateC',[0,.006,.010],.15,[-1.05,-1.3],None)]
    if max(results)<12:
        run('width040',[-.014,0,-.010],.52,[0,0],.04)
        run('width040_default',[],0,[],.04)
