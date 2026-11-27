"""Compare head segmentation visibility before/after the perception pose."""
import json
from pathlib import Path
import mujoco as mj
import numpy as np
from m2a.scene.generator import generate
from m2a.sim.g1_manip_env import G1ManipEnv

with Path('m2a/notes/wsa_gate_raw/round2_visibility.jsonl').open('w') as f:
    env=G1ManipEnv()
    for i in range(24):
        seed=10080+i
        level='L1' if i%2==0 else 'L2'
        situation=('standard','missing','pretray','stacked','reach')[(i//2)%5]
        try:
            spec=generate(seed,level,situation,'dev')
        except ValueError as err:
            f.write(json.dumps(dict(seed=seed,level=level,situation=situation,error=str(err)))+'\n');continue
        env.reset(spec)
        env.step(round(.20/env.model.opt.timestep))
        with mj.Renderer(env.model,height=480,width=640) as r:
            r.enable_segmentation_rendering()
            opt=mj.MjvOption(); opt.geomgroup[3:]=0; opt.sitegroup[5]=0
            def vis():
                r.update_scene(env.data,camera='head',scene_option=opt)
                seg=r.render()
                return {oid:int(np.count_nonzero((seg[...,0]==gid)&(seg[...,1]==int(mj.mjtObj.mjOBJ_GEOM)))) for oid,gid in env.object_geoms.items()}
            before=vis(); old=env.get_gt_objects(); token=env.perception_pose(.8); after=vis(); new=env.get_gt_objects()
            env.restore_perception_pose(token,.8)
        row=dict(seed=seed,level=level,situation=situation,before=before,after=after,
                 displacement={o:float(np.linalg.norm(np.array(old[o]['xyz'])-new[o]['xyz'])) for o in old})
        f.write(json.dumps(row)+'\n');f.flush()
