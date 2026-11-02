"""Run: source sim_test/gl_env.sh; PYTHONPATH=. .venvs/mj/bin/python tests/test_env.py"""
import json
import time
from pathlib import Path
import cv2
import numpy as np
import trimesh
from sim import SimEnv
from sim.objects import ROOT
OUT=ROOT/'data/p1_env_check'

def validate():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    with SimEnv() as env:
        mesh=trimesh.load(env.object_mesh_path('mustard'),force='mesh',process=False)
        for seed in range(3):
            env.reset(seed=seed)
            frame=env.render_rgbd(); rgb,depth,seg=(frame[k] for k in ('rgb','depth','seg'))
            assert rgb.shape==(480,640,3) and rgb.dtype==np.uint8
            assert depth.dtype==np.float32 and seg.dtype==np.int32
            mask=seg==env.object_ids['mustard']
            T=env.T_cam_obj('mustard'); K=env.camera_K()
            uv=K@T[:3,3]; uv=uv[:2]/uv[2]
            u,v=np.rint(uv).astype(int)
            on_mask=bool(0<=u<env.width and 0<=v<env.height and mask[v,u])
            assert on_mask, (seed,uv)
            vv,uu=np.nonzero(mask & (depth>0))
            rng=np.random.default_rng(seed)
            ids=rng.choice(len(vv),min(2000,len(vv)),replace=False)
            vv,uu=vv[ids],uu[ids]; z=depth[vv,uu]
            pc=np.c_[(uu-K[0,2])*z/K[0,0],(vv-K[1,2])*z/K[1,1],z]
            po=(pc-T[:3,3])@T[:3,:3]
            _,dist,_=trimesh.proximity.closest_point(mesh,po)
            med=float(np.median(dist)*1000)
            assert med<2., f'Depth/mesh frame median error {med} mm'
            cv2.imwrite(str(OUT/f'seed{seed}_rgb.png'),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
            dc=cv2.applyColorMap(np.clip((1.5-depth)/1.3*255,0,255).astype(np.uint8),cv2.COLORMAP_TURBO); dc[depth==0]=0
            cv2.imwrite(str(OUT/f'seed{seed}_depth.png'),dc)
            overlay=rgb.copy(); overlay[mask]=(overlay[mask]*.5+np.array([0,255,100])*.5).astype(np.uint8)
            cv2.circle(overlay,(u,v),4,(255,0,0),-1)
            cv2.imwrite(str(OUT/f'seed{seed}_seg.png'),cv2.cvtColor(overlay,cv2.COLOR_RGB2BGR))
            np.save(OUT/f'seed{seed}_depth_m.npy',depth)
            target=np.array([.3,-.3,.2,-2.2,.1,2.,.6]); env.set_arm_target(target)
            env.step(int(3/env.model.opt.timestep))
            err=float(np.max(np.abs(env.arm_qpos()-target)))
            assert err<.002, err
            results.append(dict(seed=seed,origin_pixel=uv.tolist(),origin_on_mask=on_mask,mask_pixels=int(mask.sum()),depth_mesh_median_mm=med,depth_mesh_p95_mm=float(np.percentile(dist,95)*1000),tracking_max_rad=err,settle_steps=env.settle_steps))
        for _ in range(2): env.render_rgbd()
        start=time.perf_counter()
        for _ in range(20): env.render_rgbd()
        fps=20/(time.perf_counter()-start)
        # Deterministic reset and same camera transforms.
        env.reset(seed=7); pose=env.T_world_obj('mustard').copy()
        env.reset(seed=7); assert np.allclose(pose,env.T_world_obj('mustard'))
        assert np.allclose(env.T_world_cam()@env.T_cam_obj('mustard'),env.T_world_obj('mustard'))
        # Registration triggers recompilation on reset, preserves CAD OBJ origin.
        cad=ROOT/'cad_uploads/converted'
        for name in ('box_fillet_50x30x20mm','cup_d70_h60mm'):
            d=cad/name
            env.add_object_from_mesh(name,d/(name+'.obj'),sorted(d.glob('*_collision_coacd_*.obj')),rgba=(.3,.7,.9,1))
        old_model=env.model
        env.reset(seed=2)
        assert env.model is not old_model
        f=env.render_rgbd()
        counts={name:int((f['seg']==oid).sum()) for name,oid in env.object_ids.items()}
        assert all(n>0 for n in counts.values()), counts
        cv2.imwrite(str(OUT/'cad_rgb.png'),cv2.cvtColor(f['rgb'],cv2.COLOR_RGB2BGR))
        env.set_gripper(0); env.step(500)
        closed=[float(env.data.qpos[env.model.joint(n).qposadr[0]]) for n in ('finger_joint1','finger_joint2')]
    result=dict(seeds=results,rgb_depth_seg_fps=fps,cad_mask_pixels=counts,finger_closed_qpos=closed)
    (OUT/'validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    return result

def test_env():
    validate()
if __name__=='__main__': validate()
