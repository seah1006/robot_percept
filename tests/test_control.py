"""Standalone validation: PYTHONPATH=. .venvs/mj/bin/python tests/test_control.py"""
import json
import os
from pathlib import Path
import numpy as np
import mujoco
from sim.ik import HOME, arm_indices, solve_ik, tcp_pose
from sim.control import Controller, top_down_grasp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/p1_control_check'
SCENE = ROOT / 'sim_test/scene_panda.xml'


def rotation_error(A, B):
    return float(np.arccos(np.clip((np.trace(A.T @ B)-1)/2, -1, 1)))


def scene():
    m = mujoco.MjModel.from_xml_path(str(SCENE)); d = mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m, d, m.key('home').id)
    mujoco.mj_forward(m, d)
    return m, d


def test_ik():
    m, d = scene(); qadr, _, lim = arm_indices(m)
    rng = np.random.default_rng(42); errors = []; successes = 0
    for _ in range(50):
        d.qpos[qadr] = rng.uniform(lim[:,0]+.25, lim[:,1]-.25)
        mujoco.mj_forward(m,d)
        goal = tcp_pose(m,d)
        q, ok = solve_ik(m,d,goal,HOME)
        check = mujoco.MjData(m); check.qpos[:] = d.qpos; check.qpos[qadr] = q
        mujoco.mj_forward(m,check); got=tcp_pose(m,check)
        errors.append([float(np.linalg.norm(goal[:3,3]-got[:3,3])), rotation_error(goal[:3,:3],got[:3,:3])])
        successes += ok
    e=np.array(errors)
    return {'successes':successes,'trials':50,'max_position_m':float(e[:,0].max()),'max_rotation_deg':float(np.rad2deg(e[:,1].max())), 'median_position_m':float(np.median(e[:,0]))}


def test_cartesian():
    m,d=scene(); c=Controller(m,d)
    start=c.ee_pose(); goal=start.copy(); goal[:3,3] += [.035,.04,-.045]
    errors=[]
    def observe(ctrl):
        # Reference path at instantaneous simulation time (quintic profile).
        fraction=min(1.,d.time/1.2); u=10*fraction**3-15*fraction**4+6*fraction**5
        ref=start[:3,3]*(1-u)+goal[:3,3]*u
        errors.append(float(np.linalg.norm(ctrl.ee_pose()[:3,3]-ref)))
    c.step_hook=observe
    c.move_cartesian(goal,duration=1.2,n_waypoints=12)
    c.step_hook=None
    return {'final_error_m':float(np.linalg.norm(c.ee_pose()[:3,3]-goal[:3,3])), 'max_path_error_m':max(errors), 'p95_path_error_m':float(np.percentile(errors,95))}


def _obj_pose(m,d):
    bid=m.body('obj').id; T=np.eye(4)
    T[:3,:3]=d.xmat[bid].reshape(3,3); T[:3,3]=d.xpos[bid]
    return T


def test_pick_place(record=True):
    import imageio.v2 as imageio
    import cv2
    OUT.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(173); trials=[]; frames=[]
    for i in range(10):
        m,d=scene(); adr=m.joint('obj_free').qposadr[0]
        xy=rng.uniform([.49,-.12],[.60,.12]); yaw=rng.uniform(-.5,.5)
        d.qpos[adr:adr+3]=[*xy,.342]
        d.qpos[adr+3:adr+7]=[np.cos(yaw/2),0,0,np.sin(yaw/2)]
        d.ctrl[7]=255
        for _ in range(200): mujoco.mj_step(m,d)
        mujoco.mj_forward(m,d)
        target=np.clip(xy+rng.uniform([-.07,-.07],[.07,.07]),[.46,-.19],[.65,.19])
        renderer=None
        if record and i==0:
            renderer=mujoco.Renderer(m,width=320,height=240)
            counter=[0]
            def capture(ctrl):
                counter[0]+=1
                if counter[0]%65==0:
                    renderer.update_scene(d,camera='rgbd')
                    frames.append(renderer.render().copy())
        else: capture=None
        c=Controller(m,d,step_hook=capture)
        initial=_obj_pose(m,d)
        G=top_down_grasp(initial,[.05,.06,.08])
        try:
            width=c.pick(G)
            lifted=float(_obj_pose(m,d)[2,3]-initial[2,3])
            # Preserve the observed in-gripper object/TCP transform when placing.
            rel=np.linalg.inv(c.ee_pose())@_obj_pose(m,d)
            desired_obj=_obj_pose(m,d); desired_obj[:2,3]=target; desired_obj[2,3]=initial[2,3]
            desired_tcp=desired_obj@np.linalg.inv(rel)
            desired_tcp[2,3] += .025  # release above table to avoid dragging the box
            c.place(desired_tcp, object_pose_fn=lambda: _obj_pose(m,d), desired_object_pose=desired_obj)
            for _ in range(300): c._step()
            final=_obj_pose(m,d)
            err=float(np.linalg.norm(final[:2,3]-target))
            trials.append({'trial':i,'lift_m':lifted,'place_error_m':err,'success':bool(lifted>.10 and err<.02),'grasp_width_m':width})
        except Exception as exc:
            trials.append({'trial':i,'success':False,'error':str(exc)})
        if renderer: renderer.close()
    if frames:
        imageio.mimsave(OUT/'pick_place.gif',frames[::2],duration=.09,loop=0)
        ids=np.linspace(0,len(frames)-1,min(6,len(frames)),dtype=int)
        strip=np.concatenate([frames[j] for j in ids],axis=1)
        cv2.imwrite(str(OUT/'frame_strip.png'),cv2.cvtColor(strip,cv2.COLOR_RGB2BGR))
        tmp=Path('/mnt/c/Users/USER/.aside/u/0/sessions/2026-10-19_5xmUwlu5vry7k9Rb/tmp/p1/control_frame_strip.png')
        cv2.imwrite(str(tmp),cv2.cvtColor(strip,cv2.COLOR_RGB2BGR))
    return {'successes':sum(t['success'] for t in trials),'trials':trials,'video_frames':len(frames)}


def test_simenv():
    try:
        from sim.env import SimEnv
        with SimEnv(objects=('mustard',),width=320,height=240) as env:
            c=Controller(env)
            T=c.ee_pose(); goal=T.copy(); goal[0,3]+=.02
            c.move_cartesian(goal,duration=.6,n_waypoints=6)
            return {'status':'ok','final_error_m':float(np.linalg.norm(c.ee_pose()[:3,3]-goal[:3,3]))}
    except Exception as exc:
        return {'status':'failed','error':str(exc)}


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    result={'ik':test_ik(),'cartesian':test_cartesian(),'pick_place':test_pick_place(),'simenv':test_simenv()}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
