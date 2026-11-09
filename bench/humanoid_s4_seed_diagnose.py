"""준비 전용: 부모 재개 공지 후 measure락 안에서 실행. 제품코드 무수정 A/B.
seq/cross→hum80→up120, 4초와8초 snapshot, reset 시드 및 raw-IK 시드 대조.
"""
import os,json,time,subprocess
from pathlib import Path
import numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from sim.humanoid_collision import CapsuleModel,MESH_RADII
from bench.humanoid_s4_function import execute
from bench.humanoid_s2_static_split import POSES as ALL_POSES
OUT=Path('bench/humanoid_s4_out/c6_seed_diagnose')
POSES=(('cross_chest',1.,-.35,1.2,0),('hum80',.17,1.4,1.1,1.4),('up120',2.1,.1,.3,0))
class DiagnosticServo(HumanoidServo):
    def __init__(self,env,raw_seed=False):
        self.raw_seed=raw_seed;self.last_raw=None;self.last_seed_shift=None
        super().__init__(env)
    def _retarget(self,sample):
        enabled=self.options['collision_avoidance'];captured=[]
        if enabled:
            planner=self.env.collision_planner;original=planner.submit
            def record(start,target):
                captured.append(np.array(target,copy=True));return original(start,target)
            planner.submit=record
        try:super()._retarget(sample)
        finally:
            if enabled:planner.submit=original
        if captured:
            self.last_raw=captured[-1]
            self.last_seed_shift={side:float(np.max(np.abs(self.q_ik[side]-self.last_raw[self.iks[side].qadr]))) for side in ('left','right')}
            if self.raw_seed:
                for side in ('left','right'):self.q_ik[side]=self.last_raw[self.iks[side].qadr].copy()

def run(case,enabled,reset_each,raw_seed):
    e=HumanoidEnv();s=DiagnosticServo(e,raw_seed);g=CapsuleModel(e.model,MESH_RADII);rows=[]
    try:
        prefix=[]
        if not reset_each:
            # Exact preceding nine poses, each four seconds, not a rest-only shortcut.
            for name,fl,ab,el,hu in ALL_POSES[:9]:
                item=execute(e,s,(fl,ab,el,hu,0),4.,enabled);item['pose']=name;prefix.append(item)
        for name,fl,ab,el,hu in POSES:
            if reset_each:e.reset();s.reset_state()
            for window in (4,8):
                wall_before=time.monotonic();sim_before=float(e.data.time)
                row=execute(e,s,(fl,ab,el,hu,0),4.,enabled)
                row['actual_wall_s']=time.monotonic()-wall_before;row['sim_advance_s']=float(e.data.time)-sim_before
                row.update(pose=name,elapsed_at_pose_s=window,raw_ik_diag=dict(s.diag),seed_shift_rad=s.last_seed_shift)
                if s.last_raw is not None:row['raw_target_clearance_mm']=1000*g.minimum_distance(s.last_raw)
                rows.append(row);print(case,name,window,max(row['final_errors_deg']),row.get('raw_target_clearance_mm'),flush=True)
        return dict(case=case,enabled=enabled,reset_each=reset_each,raw_seed=raw_seed,prefix=prefix,rows=rows)
    finally:e.close()

def main():
    if os.environ.get('RP_MEASUREMENT_RESUMED')!='1':
        raise SystemExit('부모 재개 공지 확인 후 RP_MEASUREMENT_RESUMED=1 및 measure락 안에서만 실행')
    OUT.mkdir(exist_ok=True)
    result=dict(note='GT auxiliary. Bench-only seed intervention, NOT production acceptance/performance proof.',load=Path('/proc/loadavg').read_text(),gpu=subprocess.getoutput('nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'),cases=[])
    for case,enabled,reset_each,raw_seed in (('on_seq_projected',True,False,False),('on_reset_projected',True,True,False),('on_seq_raw_seed',True,False,True)):
        result['cases'].append(run(case,enabled,reset_each,raw_seed))
        (OUT/'result.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()