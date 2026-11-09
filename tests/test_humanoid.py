import numpy as np
import threading
from sim.humanoid_retarget import finger_angles, zxy_angles, B_CAM, torso_frame
from web.humanoid import validate_sample

def test_mcp_splay_is_not_flexion():
    h=np.zeros((21,3))
    for chain,x in zip([(1,2,3,4),(5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)],[-.07,-.04,0,.03,.06]):
        for j,i in enumerate(chain):h[i]=[x*(1+j*.25),.05+j*.025,0]
    angles=finger_angles(h)
    assert all(abs(angles[f][0])<1e-6 for f in ['index','middle','ring','pinky'])
    h[6,2]=.04
    assert finger_angles(h)['index'][0]>.2

def test_neutral_torso_and_axis_signs():
    p=np.zeros((33,3));p[11]=[.2,-.3,0];p[12]=[-.2,-.3,0];p[23]=[.15,.2,0];p[24]=[-.15,.2,0]
    r,_=torso_frame(p);assert np.allclose(r,B_CAM)
    for axis in range(3):
        angle=.2;c=np.cos(angle);s=np.sin(angle)
        matrices=[np.array([[c,-s,0],[s,c,0],[0,0,1]]),np.array([[1,0,0],[0,c,-s],[0,s,c]]),np.array([[c,0,s],[0,1,0],[-s,0,c]])]
        assert np.isclose(zxy_angles(matrices[axis])[axis],angle)

def test_input_validation():
    assert validate_sample({'detected':False})[1] is None
    assert validate_sample({'detected':True,'pose':[]})[1]
    p=[[0,0,0,1] for _ in range(33)]
    assert validate_sample({'detected':True,'pose':p})[1] is None
    p[1][0]=float('nan');assert validate_sample({'detected':True,'pose':p})[1]

def test_mirrored_arms_fk_directions():
    """Compare FK bone directions, not coupled shoulder Euler components."""
    import mujoco
    from sim.humanoid_env import HumanoidEnv
    env = HumanoidEnv()
    try:
        for pitch in (-.2, -.9, -1.57, -2.4):
            q = dict(shoulder_pitch=pitch, shoulder_roll=.2, shoulder_yaw=.3,
                     elbow=.8, wrist_roll=.1, wrist_pitch=.1, wrist_yaw=.2)
            for side,sign in [('left',1),('right',-1)]:
                for joint,value in q.items():
                    mirrored = joint in ('shoulder_roll','shoulder_yaw','wrist_roll','wrist_yaw')
                    env.data.qpos[env.qadr[f'{side}_{joint}_joint']] = value*(sign if mirrored else 1)
            mujoco.mj_forward(env.model,env.data)
            directions={}
            for side in ('left','right'):
                shoulder=env.data.xpos[env.model.body(f'{side}_shoulder_roll_link').id]
                elbow=env.data.site_xpos[env.model.site(f'{side}_elbow_site').id]
                wrist=env.data.site_xpos[env.model.site(f'{side}_wrist_site').id]
                directions[side]=[elbow-shoulder,wrist-elbow]
            for left,right in zip(directions['left'],directions['right']):
                assert np.allclose(left,right*np.array([1,-1,1]),atol=3e-3)
    finally:env.close()

def test_offscreen_preview_does_not_reject_world_tracking():
    from tools.teleop_tracker_win import preview_coords
    uv=np.tile([.4,.6],(33,1));uv[30]=[20.,-12.]
    p=[[0.,0.,0.,1.] for _ in range(33)]
    sample,error=validate_sample({'detected':True,'pose':p,'pose2d':preview_coords(uv)})
    assert error is None
    assert sample['pose']==p
    assert sample['pose2d'][0]==[.4,.6]
    assert sample['pose2d'][30]==[2.,-2.]

def test_g1_mode_pauses_only_same_server_panda_render():
    from flask import Flask
    from web.humanoid import create_blueprint
    class HR:
        def start(self):self.enabled=True
        def stop(self):self.enabled=False
        def close(self):pass
    class Panda:
        status={}
        def __init__(self):self.commands=[]
        def send(self,op,**kw):self.commands.append((op,kw))
    h=HR();p=Panda();app=Flask(__name__);app.register_blueprint(create_blueprint(h,p));client=app.test_client()
    assert client.post('/humanoid/mode',json={'enabled':True}).status_code==200
    assert h.enabled and p.commands[-1]==('teleop_render_pause',{'enabled':True})
    assert client.post('/humanoid/mode',json={'enabled':False}).status_code==200
    assert not h.enabled and p.commands[-1]==('teleop_render_pause',{'enabled':False})
    p.status={'held_object':'test'};count=len(p.commands)
    assert client.post('/humanoid/mode',json={'enabled':True}).status_code==409
    assert len(p.commands)==count

def test_humanoid_shm_prefix_and_unlink():
    import pytest
    from multiprocessing import shared_memory
    from web.shm_channel import Blob
    blob=Blob(size=256,create=True);name=blob.name
    try:
        assert name.startswith('rp_humanoid_')
        blob.write(b'payload');assert blob.read()[1]==b'payload'
    finally:blob.close(unlink=True)
    with pytest.raises(FileNotFoundError):shared_memory.SharedMemory(name=name)

def test_tracker_modes_never_send_g1_in_panda_mode():
    from tools.teleop_tracker_win import update_routes
    p={'detected':False};h={'detected':False}
    assert update_routes('panda',p,h)==[('/teleop/update',p)]
    assert update_routes('humanoid',p,h)==[('/humanoid/update',h)]
    assert update_routes('both',p,h)==[('/teleop/update',p),('/humanoid/update',h)]

def test_pipeline_default_is_g1_only_and_can_be_overridden():
    from tools.teleop_tracker_win import pipeline_enabled
    assert not pipeline_enabled('panda')
    assert pipeline_enabled('humanoid') and pipeline_enabled('both')
    assert not pipeline_enabled('humanoid',False)
    assert pipeline_enabled('panda',True)


def test_r2_mixed_pose_rows_and_visibility_rejected():
    p = [[0., 0., 0., 1.] for _ in range(33)]
    p[3] = [0., 0., 0.]
    assert validate_sample({'detected': True, 'pose': p})[1]
    p[3] = [0., 0., 0., 1.1]
    assert validate_sample({'detected': True, 'pose': p})[1]


def test_r2_off_status_enabled_false_and_clean_restart_cache():
    from web.humanoid import HumanoidRuntime
    h = HumanoidRuntime()
    try:
        assert h.status() == {'state': 'off', 'enabled': False}
        h._ensure_blobs()
        h.blobs['status'].write(b'{"state":"ready","enabled":true}')
        assert h.status()['state'] == 'off'
        assert h.status()['enabled'] is False
    finally: h.close()


def test_r2_invalid_payload_http400_without_worker():
    from flask import Flask
    from web.humanoid import HumanoidRuntime, create_blueprint
    h=HumanoidRuntime(); app=Flask(__name__); app.register_blueprint(create_blueprint(h))
    try:
        p=[[0.,0.,0.,1.] for _ in range(33)];p[1]=[0.,0.,0.]
        assert app.test_client().post('/humanoid/update',json={'detected':True,'pose':p}).status_code == 400
        assert not h.running()
    finally:h.close()


def test_r2_optional_quality_compatible_and_finite():
    sample,err=validate_sample({'detected':False,'seq':7,'capture_at':1.0,'quality':{'hands':{'left':{'state':'tracked','confidence':.8,'age_ms':10}},'hips_visible':False}})
    assert err is None and sample['client_seq']==7
    assert validate_sample({'detected':False,'quality':{'hands':{'left':{'confidence':2}}}})[1]

def test_solver_degenerate_frames_are_safe():
    from sim.humanoid_retarget import palm_frame
    r,hips=torso_frame(np.zeros((33,3)))
    assert np.allclose(r.T@r,np.eye(3)) and np.linalg.det(r)>.99 and not hips
    assert palm_frame(np.zeros((21,3)),'left') is None
    h=np.tile(np.arange(21)[:,None],(1,3)).astype(float)
    assert palm_frame(h,'right') is None

def test_solver_missing_arm_and_hand_hold_current_command():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools.humanoid_synth import payload
    env=HumanoidEnv()
    try:
        servo=HumanoidServo(env);p,_=payload(12.)
        servo._retarget(p)
        saved=servo.hand_rotation['left'].copy()
        p['hands']={};p['pose'][13][3]=0
        servo._retarget(p)
        for group in ('left_arm','left_hand','right_hand'):
            ix=[servo.index[n] for n in env.groups[group]]
            assert np.allclose(servo.des[ix],servo.cmd[ix])
        assert np.allclose(servo.hand_rotation['left'],saved)
        assert not servo.tracking['left'] and not servo.tracking['left_hand']
        assert np.isfinite(servo.des).all()
    finally:env.close()

def test_solver_reset_preserves_calibration_frame_and_marker():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    env=HumanoidEnv()
    try:
        servo=HumanoidServo(env);servo.B0=B_CAM@np.array([[0,-1,0],[1,0,0],[0,0,1]])
        frame=servo.B0.copy();servo.calib_seen=123;servo.reset_state()
        assert np.array_equal(servo.B0,frame) and servo.calib_seen==123
    finally:env.close()

def test_solver_upper_body_only_and_degenerate_arm_are_finite():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools.humanoid_synth import payload
    env=HumanoidEnv()
    try:
        servo=HumanoidServo(env);p,_=payload(12.)
        for i in (23,24):p['pose'][i]=[0,0,0,0]
        p['pose'][13][:3]=p['pose'][11][:3]
        servo._retarget(p)
        assert not servo.human['hips_visible'] and not servo.tracking['left']
        assert servo.tracking['right'] and np.isfinite(servo.des).all()
        previous=servo.vel.copy()
        servo._integrate(.02)
        assert np.all(np.abs(servo.vel)<=servo.vmax+1e-9)
        assert np.all(np.abs(servo.vel-previous)<=servo.amax*.02+1e-9)
    finally:env.close()

def test_r2_lifecycle_stop_start_serialized():
    import threading,time
    from web.humanoid import HumanoidRuntime
    h=HumanoidRuntime();events=[]
    class Proc:
        def is_alive(self):return False
        def join(self,timeout):events.append('join');time.sleep(.03);events.append('joined')
    h.proc=Proc()
    def launch():
        with h.lock:events.append('start')
    a=threading.Thread(target=h.stop);a.start();time.sleep(.005)
    b=threading.Thread(target=launch);b.start();a.join();b.join()
    assert events==['join','joined','start']
    h.close()


def test_r2_dead_worker_watch_releases_panda_pause():
    import time
    from web.humanoid import HumanoidRuntime
    h=HumanoidRuntime();released=[]
    class Proc:
        def is_alive(self):return False
        def join(self,timeout):pass
    try:
        h.proc=Proc();h.ctrl['enabled']=True;h.on_failure=lambda:released.append(True)
        deadline=time.monotonic()+1
        while not released and time.monotonic()<deadline:time.sleep(.01)
        assert released==[True] and h.ctrl['enabled'] is False
    finally:h.close()

def test_panda_idle_render_never_throttles_work_or_viewers():
    from web.sim_worker import render_period
    assert render_period({}, 100) == .5
    for key,value in [('video_viewers',1),('video_until',101),('need_depth',True),('teleop_enabled',True),('active_command','pick-id'),('held_object','mustard'),('phase','pick.approach')]:
        assert render_period({key:value},100) == 1/30
    assert render_period({'video_until':99,'video_viewers':0,'phase':'idle'},100)==.5
def test_solver_relative_shoulder_jacobian_matches_finite_difference():
    import mujoco
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_ik import ArmIK
    env=HumanoidEnv()
    try:
        ik=ArmIK(env.model,'left');q=env.q(env.groups['left_arm']);full=env.data.qpos.copy()
        shoulder=env.model.body('left_shoulder_roll_link').id
        d=ik.fk(full,q);jp=np.zeros((3,env.model.nv));js=jp.copy()
        mujoco.mj_jacSite(env.model,d,jp,None,ik.site['wrist_site'])
        mujoco.mj_jacBody(env.model,d,js,None,shoulder)
        analytic=(jp-js)[:,ik.dadr];numeric=np.zeros((3,7))
        for i in range(7):
            eps=np.eye(7)[i]*1e-6
            d=ik.fk(full,q+eps);plus=d.site_xpos[ik.site['wrist_site']].copy()-d.xpos[shoulder]
            d=ik.fk(full,q-eps);minus=d.site_xpos[ik.site['wrist_site']].copy()-d.xpos[shoulder]
            numeric[:,i]=(plus-minus)/2e-6
        assert np.allclose(analytic,numeric,atol=1e-7)
    finally:env.close()

def test_solver_moving_shoulder_targets_restore_fk_accuracy():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools.humanoid_synth import payload
    env=HumanoidEnv()
    try:
        servo=HumanoidServo(env);p,gt=payload(7.5)
        for _ in range(20):servo._retarget(p)
        errors={}
        for side in ('left','right'):
            ik=servo.iks[side];d=ik.fk(env.data.qpos,servo.q_ik[side]);R=d.xmat[servo.torso_body].reshape(3,3)
            S=d.xpos[env.model.body(f'{side}_shoulder_roll_link').id];E=d.site_xpos[ik.site['elbow_site']];W=d.site_xpos[ik.site['wrist_site']]
            errors[side]=[]
            for v,k in ((E-S,'u1'),(W-E,'u2')):
                v=R.T@v;u=np.array(gt[side][k]);angle=np.degrees(np.arccos(np.clip(v@u/np.linalg.norm(v)/np.linalg.norm(u),-1,1)))
                errors[side].append(angle);assert angle<=8
            assert servo.diag[side]['pos_err_mm']<=10
        assert np.max(np.abs(np.array(errors['left'])-errors['right']))<=3
    finally:env.close()
def test_solver_physics_setpoint_acceleration_and_jerk_are_bounded():
    from sim.humanoid_env import JointSetpoint
    f=JointSetpoint([0.],[3.],[25.],scale=.8)
    f.goal[:]=1.
    last_a=f.acceleration.copy()
    for i in range(2500):
        if i==500:f.goal[:]=-1.
        if i==1500:f.goal[:]=0.
        f.advance(.002)
        assert np.isfinite(f.position).all()
        assert np.max(np.abs(f.acceleration))<=20.+1e-9
        assert np.max(np.abs(f.acceleration-last_a))<=.4+1e-9
        last_a=f.acceleration.copy()

def test_solver_collinear_torso_holds_without_poisoning_warm_start():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools.humanoid_synth import payload
    env=HumanoidEnv()
    try:
        s=HumanoidServo(env);p,_=payload(12.);s._retarget(p)
        bad=dict(p,pose=[[i*.01,i*.01,i*.01,.95] for i in range(33)])
        s._retarget(bad)
        assert s.human['invalid_torso'] and np.allclose(s.des,s.cmd)
        for _ in range(12):s._retarget(p)
        assert s.tracking['left'] and np.isfinite(s.des).all()
        assert s.diag['left']['pos_err_mm']<10
    finally:env.close()


def test_fp_warmup_hook_uses_rgbd_and_skips_active_selection(monkeypatch):
    monkeypatch.setenv('RP_PERCEPTION_WARMUP','1')
    import threading, fcntl
    from types import SimpleNamespace
    from web.app import Runtime
    monkeypatch.setattr(fcntl, 'flock', lambda *args: None)
    calls=[]
    backend=SimpleNamespace(mode='fp',warmup_async=lambda *args: (calls.append(args) or SimpleNamespace(join=lambda: calls.append('joined'))))
    runtime=Runtime.__new__(Runtime)
    runtime.perception=backend;runtime.running=True;runtime.selected=None
    runtime.status={'ready':True,'camera_K':np.eye(3).tolist(),'objects':{'mustard':{'mesh':'real.obj'}}}
    runtime.perception_lock=threading.RLock();runtime.state_lock=threading.RLock()
    runtime.frame=lambda: (np.ones((2,2,3),np.uint8),np.ones((2,2),np.float32),None)
    runtime.warmup_loop()
    assert len(calls)==2 and calls[-1]=='joined'
    assert calls[0][0].shape==(2,2,3) and calls[0][1].shape==(2,2)
    assert calls[0][3]==runtime.status['objects']
    calls.clear();runtime.selected='mustard';runtime.warmup_loop();assert calls==[]
    runtime.perception.mode='stub';runtime.selected=None;runtime.warmup_loop();assert calls==[]
    runtime.perception.mode='fp';monkeypatch.setenv('RP_PERCEPTION_WARMUP','0')
    runtime.warmup_loop();assert calls==[] and runtime.perception.warmup_state=='disabled'

def test_solver_setpoint_brakes_before_internal_control_range_clamp():
    from sim.humanoid_env import JointSetpoint
    f=JointSetpoint([0.],[4.],[30.],scale=.6,lower=[-1.],upper=[1.])
    for i in range(5000):
        f.goal[:]=1. if (i//1000)%2==0 else -1.
        before=f.acceleration.copy();f.advance(.002)
        assert np.max(np.abs(f.position))<1.
        assert np.max(np.abs(f.acceleration-before))<=f.jmax[0]*.002+1e-9
        assert np.max(np.abs(f.acceleration))<=18.+1e-9
def test_solver_asymmetric_pose_history_escapes_saturated_branches():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools import humanoid_synth as hs
    from bench.humanoid_s_history import PAIRS,P,angle
    env=HumanoidEnv();s=HumanoidServo(env);original=hs.frame
    _,_,fingers,torso=original(0);matched={}
    try:
        for a,b in PAIRS:
            rows=[]
            for left,right in ((a,b),(b,a)):
                hs.frame=lambda _:(True,{'left':P[left],'right':P[right]},fingers,torso)
                sample,gt=hs.payload(0)
                for _ in range(20):s._retarget(sample)
                row={}
                for side,pose in (('left',left),('right',right)):
                    ik=s.iks[side];d=ik.fk(env.data.qpos,s.q_ik[side])
                    S=d.xpos[env.model.body(f'{side}_shoulder_roll_link').id];E=d.site_xpos[ik.site['elbow_site']];W=d.site_xpos[ik.site['wrist_site']]
                    errs=np.array([angle(E-S,np.array(gt[side]['u1'])),angle(W-E,np.array(gt[side]['u2']))])
                    assert np.max(errs)<=8,(pose,side,errs)
                    assert s.diag[side]['pos_err_mm']<=10
                    row[pose]=errs
                rows.append(row)
            for pose in (a,b):assert np.max(np.abs(rows[0][pose]-rows[1][pose]))<=3
    finally:env.close();hs.frame=original


def test_selected_tracking_uses_atomic_status_copy(monkeypatch):
    import threading
    from web.app import Runtime
    runtime=Runtime.__new__(Runtime)
    runtime.running=True;runtime.selected='mustard';runtime.generation=0
    runtime.state_lock=threading.RLock();runtime.metrics={}
    class Proxy:
        calls=0
        def __iter__(self):raise AssertionError('per-key Manager RPC copy forbidden')
        def copy(self):
            self.calls+=1
            return {'frame_seq':1,'phase':'pick.approach'}
    runtime.status=Proxy()
    monkeypatch.setattr('web.app.time.sleep',lambda _:setattr(runtime,'running',False))
    runtime.track_loop()
    assert runtime.status.calls==1 and runtime.metrics['tracking_state']=='paused'
    runtime.running=True;runtime.selected=None;runtime.status.calls=0
    runtime.track_loop()
    assert runtime.status.calls==0

def test_solver_safety_brake_defaults_on_and_toggle_preserves_physical_state():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo,DEFAULT_OPTIONS
    env=HumanoidEnv()
    try:
        servo=HumanoidServo(env)
        assert DEFAULT_OPTIONS['safety_brake'] and servo.options['safety_brake']
        assert env.safety_brake and env.setpoint_scale==.6
        name='right_shoulder_pitch_joint';j=env.dadr[name];env.data.qvel[j]=.2
        env.set_targets({name:-.3})
        for _ in range(30):env.step()
        for enabled in (False,True,False,True):
            q=env.data.qpos.copy();v=env.data.qvel.copy();ctrl=env.data.ctrl.copy()
            env.set_safety_brake(enabled)
            assert np.array_equal(q,env.data.qpos) and np.array_equal(v,env.data.qvel)
            assert np.array_equal(ctrl,env.data.ctrl)
            if enabled:
                assert np.isclose(env.setpoint.velocity[env.act[name]],env.data.qvel[j])
                assert np.isclose(env.setpoint.position[env.act[name]],env.data.qpos[env.qadr[name]])
            env.step()
            assert np.max(np.abs(env.data.ctrl-ctrl))<.02
            assert np.isfinite(env.data.qpos).all()
        for _ in range(150):env.step()
        assert env.safety_brake and env._brake_transition is None
    finally:env.close()

def test_solver_safety_brake_servo_option_turns_off_without_reset():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    env=HumanoidEnv()
    try:
        servo=HumanoidServo(env)
        servo.tick(None,{'enabled':False,'options':{'safety_brake':False}},100.)
        assert not env.safety_brake and not servo.options['safety_brake']
        for _ in range(110):env.step()
        assert env.setpoint is None
    finally:env.close()


def test_safety_brake_api_boolean_default_and_off_status():
    from flask import Flask
    from web.humanoid import HumanoidRuntime,create_blueprint
    h=HumanoidRuntime();app=Flask(__name__);app.register_blueprint(create_blueprint(h));client=app.test_client()
    try:
        assert client.get('/humanoid/status').json['safety_brake'] is True
        assert client.post('/humanoid/options',json={'safety_brake':False}).status_code==200
        assert h.ctrl['options']['safety_brake'] is False
        assert client.get('/humanoid/status').json['safety_brake'] is False
        assert client.post('/humanoid/options',json={'safety_brake':True}).status_code==200
        assert client.get('/humanoid/status').json['safety_brake'] is True
        for invalid in ('false',0,None):
            assert client.post('/humanoid/options',json={'safety_brake':invalid}).status_code==400
    finally:h.close()

def test_solver_symmetric_full_history_including_hum80_to_up120():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools import humanoid_synth as hs
    from bench.humanoid_s_static import POSES
    from bench.humanoid_s_history import angle
    env=HumanoidEnv();s=HumanoidServo(env);original=hs.frame
    _,_,fingers,torso=original(0)
    try:
        for name,fl,ab,el,hu in POSES:
            hs.frame=lambda _:(True,{z:(fl,ab,el,hu,0) for z in ('left','right')},fingers,torso)
            p,gt=hs.payload(0)
            for _ in range(100):s._retarget(p)
            for z in ('left','right'):
                ik=s.iks[z];d=ik.fk(env.data.qpos,s.q_ik[z]);S=d.xpos[env.model.body(z+'_shoulder_roll_link').id];E=d.site_xpos[ik.site['elbow_site']];W=d.site_xpos[ik.site['wrist_site']]
                errs=[angle(E-S,np.array(gt[z]['u1'])),angle(W-E,np.array(gt[z]['u2']))]
                assert max(errs)<=8,(name,z,errs,s.diag[z])
    finally:env.close();hs.frame=original


def test_fp_warmup_defers_until_g1_off(monkeypatch):
    import threading
    from types import SimpleNamespace
    from web.app import Runtime
    runtime=Runtime.__new__(Runtime);runtime.running=True;runtime.selected=None
    runtime.humanoid_runtime=SimpleNamespace(ctrl={'enabled':True})
    runtime.status={'ready':True,'camera_K':np.eye(3).tolist(),'objects':{'mustard':{'mesh':'real.obj'}}}
    runtime.perception_lock=threading.RLock();runtime.state_lock=threading.RLock();calls=[]
    runtime.perception=SimpleNamespace(mode='fp',warmup_async=lambda *args:(calls.append(args) or None))
    runtime.frame=lambda:(np.ones((2,2,3),np.uint8),np.ones((2,2),np.float32),None)
    def release_g1(_):
        assert runtime.perception.warmup_state=='deferred_g1' and calls==[]
        runtime.humanoid_runtime.ctrl['enabled']=False
    monkeypatch.setattr('web.app.time.sleep',release_g1)
    monkeypatch.setenv('RP_PERCEPTION_WARMUP','1')
    runtime.warmup_loop();assert len(calls)==1


def test_g1_priority_changes_only_own_active_fp_child(monkeypatch):
    from types import SimpleNamespace
    from web.app import Runtime
    runtime=Runtime.__new__(Runtime);changed=[]
    runtime.perception=SimpleNamespace(warmup_state='running',proc=SimpleNamespace(pid=12345,is_alive=lambda:True))
    monkeypatch.setattr('web.app.os.getpriority',lambda *args:10)
    monkeypatch.setattr('web.app.os.setpriority',lambda policy,pid,nice:changed.append((pid,nice)))
    runtime.prioritize_humanoid();assert changed==[(12345,19)]
    assert runtime.perception.warmup_g1_nice_applied==19
    runtime.perception.warmup_state='ready';runtime.prioritize_humanoid();assert len(changed)==1



def test_warmup_harness_drops_overdue_input_deadlines():
    from bench.humanoid_w_warmup import next_input_deadline
    deadline,reset=next_input_deadline(0.,5.)
    assert reset and np.isclose(deadline,5.+1/30)
    deadline,reset=next_input_deadline(0.,.01)
    assert not reset and np.isclose(deadline,1/30)



def test_fp_idle_backend_deferral_creates_no_process_or_cuda_import(monkeypatch):
    import sys,pytest
    from web.perception_stub import PerceptionBackend
    had_torch='torch' in sys.modules
    monkeypatch.setenv('RP_PERCEPTION_WARMUP','0')
    backend=PerceptionBackend('fp')
    try:
        assert backend.proc is None and not hasattr(backend,'req_q')
        assert backend.call('drop')=={'ms':0.,'peak_mb':0.}
        assert backend.warmup_async(np.zeros((1,1,3)),np.ones((1,1)),np.eye(3),{}) is None
        assert backend.proc is None and backend.warmup_state=='disabled'
        if not had_torch:assert 'torch' not in sys.modules
    finally:backend.close()
    with pytest.raises(RuntimeError,match='closed'):backend.call('drop')

def test_solver_off_catchup_preserves_reference_state_and_is_not_fixed_time_blend():
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv()
    try:
        env.set_targets({'right_shoulder_pitch_joint':-2.})
        for _ in range(20):env.step()
        p=env.setpoint.position.copy();v=env.setpoint.velocity.copy();a=env.setpoint.acceleration.copy();ctrl=env.data.ctrl.copy()
        env.set_safety_brake(False)
        assert np.array_equal(env.data.ctrl,ctrl)
        assert np.array_equal(env.setpoint.position,p)
        assert np.array_equal(env.setpoint.velocity,v)
        assert np.array_equal(env.setpoint.acceleration,a)
        for _ in range(110):env.step()
        assert env.setpoint is not None and env._brake_transition is not None
        assert np.max(np.abs(env.data.ctrl-env._fast_goal))>5e-5
    finally:env.close()

def test_solver_on_reference_offset_is_constant_and_transforms_goal_and_limits():
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv(setpoint_scale=None)
    try:
        name='right_shoulder_pitch_joint';aid=env.act[name]
        env.data.ctrl[aid]+=.02;env._fast_goal[aid]=env.data.ctrl[aid]
        env.set_safety_brake(True);offset=env._reference_offset.copy()
        assert np.allclose(env.setpoint.position+offset,env.data.ctrl)
        assert np.allclose(env.setpoint.goal+offset,env._fast_goal)
        assert np.allclose(env.setpoint.lower+offset,env.model.actuator_ctrlrange[:,0])
        for _ in range(120):env.step()
        assert np.array_equal(env._reference_offset,offset)
        assert env._brake_transition is None
    finally:env.close()


def test_g1_reservation_prevents_fp_respawn_during_cancel():
    from types import SimpleNamespace
    from web.app import Runtime
    runtime=Runtime.__new__(Runtime);runtime.state_lock=threading.RLock();runtime.selected=None
    runtime.humanoid_runtime=SimpleNamespace(ctrl={'enabled':False})
    events=[]
    def cancel():
        assert runtime._g1_requested() and runtime.state_lock._is_owned()
        events.append('cancel');return True
    runtime.perception=SimpleNamespace(warmup_state='running',proc=None,defer_warmup_for_g1=cancel,warmup_thread=SimpleNamespace(join=lambda timeout:events.append('joined'),is_alive=lambda:False))
    runtime._warmup_manager_thread=SimpleNamespace(is_alive=lambda:True)
    runtime.prioritize_humanoid()
    assert events==['cancel','joined'] and runtime._g1_requested()
    assert not runtime.perception.warmup_g1_cancel_pending
    runtime.release_humanoid_start();assert not runtime._g1_requested()


def test_selected_object_keeps_fp_worker_and_uses_nice_fallback(monkeypatch):
    from types import SimpleNamespace
    from web.app import Runtime
    runtime=Runtime.__new__(Runtime);runtime.state_lock=threading.RLock();runtime.selected='mustard';events=[]
    runtime.perception=SimpleNamespace(warmup_state='running',defer_warmup_for_g1=lambda:events.append('cancel'),proc=SimpleNamespace(pid=12345,is_alive=lambda:True))
    monkeypatch.setattr('web.app.os.getpriority',lambda *args:10)
    monkeypatch.setattr('web.app.os.setpriority',lambda policy,pid,nice:events.append(('nice',nice)))
    runtime.prioritize_humanoid()
    assert events==[('nice',19)]
    runtime.release_humanoid_start()


def test_failed_g1_start_releases_warmup_reservation():
    from flask import Flask
    from web.humanoid import create_blueprint
    class HR:
        def start(self):raise RuntimeError('startup failed')
        def close(self):pass
    class Panda:
        status={};reserved=False
        def prioritize_humanoid(self):self.reserved=True
        def release_humanoid_start(self):self.reserved=False
        def send(self,*args,**kwargs):pass
    p=Panda();app=Flask(__name__);app.register_blueprint(create_blueprint(HR(),p))
    assert app.test_client().post('/humanoid/mode',json={'enabled':True}).status_code==503
    assert not p.reserved

def test_solver_collision_feature_defaults_off_and_is_opt_in():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo,DEFAULT_OPTIONS
    env=HumanoidEnv()
    try:
        s=HumanoidServo(env)
        assert not DEFAULT_OPTIONS['collision_avoidance']
        assert not env.collision_avoidance and env.collision_model is None
        env.set_collision_avoidance(True)
        assert env.collision_avoidance and env.collision_model is not None
        env.set_collision_avoidance(False)
        assert not env.collision_avoidance
    finally:env.close()


def test_g1_running_process_blocks_warmup_after_start_reservation_released():
    from types import SimpleNamespace
    from web.app import Runtime
    runtime=Runtime.__new__(Runtime)
    runtime.humanoid_runtime=SimpleNamespace(ctrl={'enabled':False},running=lambda:True)
    runtime.release_humanoid_start();assert runtime._g1_requested()
    runtime.humanoid_runtime.running=lambda:False
    assert not runtime._g1_requested()
    runtime.humanoid_runtime.ctrl['enabled']=True;assert runtime._g1_requested()


def test_successful_g1_start_releases_warmup_reservation():
    from flask import Flask
    from web.humanoid import create_blueprint
    class HR:
        def start(self):pass
        def close(self):pass
    class Panda:
        status={};reserved=False;releases=0
        def prioritize_humanoid(self):self.reserved=True
        def release_humanoid_start(self):self.reserved=False;self.releases+=1
        def send(self,*args,**kwargs):pass
    p=Panda();app=Flask(__name__);app.register_blueprint(create_blueprint(HR(),p))
    assert app.test_client().post('/humanoid/mode',json={'enabled':True}).status_code==200
    assert not p.reserved and p.releases==1


def test_experimental_collision_option_is_boolean_only():
    from flask import Flask
    from web.humanoid import HumanoidRuntime,create_blueprint
    runtime=HumanoidRuntime();app=Flask(__name__);app.register_blueprint(create_blueprint(runtime));client=app.test_client()
    try:
        assert 'collision_avoidance' not in runtime.ctrl['options']
        for enabled in (False,True):
            assert client.post('/humanoid/options',json={'collision_avoidance':enabled}).status_code==200
        assert client.post('/humanoid/options',json={'collision_avoidance':'true'}).status_code==400
    finally:runtime.close()

def test_solver_collision_brake_latches_goal_without_state_jump():
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv()
    try:
        env.set_collision_avoidance(True)
        state=[env.data.qpos.copy(),env.data.qvel.copy(),env.setpoint.position.copy(),env.setpoint.velocity.copy(),env.setpoint.acceleration.copy()]
        env.request_collision_brake('test')
        assert env.collision_braking
        for old,new in zip(state,[env.data.qpos,env.data.qvel,env.setpoint.position,env.setpoint.velocity,env.setpoint.acceleration]):assert np.array_equal(old,new)
        goal=env.setpoint.goal.copy();env.set_targets({'right_elbow_joint':1.5})
        assert np.array_equal(env.setpoint.goal,goal)
    finally:env.close()
def test_solver_collision_latch_skips_inverse_kinematics_and_projection():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools.humanoid_synth import payload
    env=HumanoidEnv();s=HumanoidServo(env)
    try:
        env.set_collision_avoidance(True);env.request_collision_brake('test')
        env.data.qvel[env.dadr['right_elbow_joint']]=.1
        before=[ik.fk_calls for ik in s.iks.values()];p,_=payload(6);p['received_at']=100.
        s.tick(p,{'enabled':True,'options':{'collision_avoidance':True}},100.)
        assert before==[ik.fk_calls for ik in s.iks.values()]
        assert not s.solved and s.profile['projection_ms']==0
        assert env.collision_status['collision_state']=='holding'
    finally:env.close()


def test_worker_collision_diagnostics_refresh_without_new_input():
    import json
    from types import SimpleNamespace
    from web.humanoid_worker import runtime_diagnostics
    env=SimpleNamespace(collision_avoidance=True,collision_braking=True,collision_status={'collision_state':'holding','brake':{'reason':{'pair':['left_arm','torso'],'distance':.01}}})
    servo=SimpleNamespace(profile={'total_ms':1.2,'projection_ms':np.float64(.3),'ik_fk_calls':np.int64(4),'bad_ms':float('nan')})
    first=runtime_diagnostics(env,servo)
    assert first['collision_state']=='holding' and first['collision_status']['reason']['pair']==['left_arm','torso']
    assert first['profile_ms']=={'total_ms':1.2,'projection_ms':.3} and first['profile_counts']=={'ik_fk_calls':4}
    json.dumps(first,allow_nan=False)
    env.collision_status['collision_state']='avoiding';env.collision_status['brake']['reason']['distance']=.02
    servo.profile['total_ms']=.8
    second=runtime_diagnostics(env,servo)
    assert second['collision_state']=='avoiding' and second['profile_ms']['total_ms']==.8
    assert first['collision_status']['reason']['distance']==.01
    env.collision_status={'collision_state':'clear'};env.collision_braking=False
    assert runtime_diagnostics(env,servo)['collision_state']=='clear'
    env.collision_status={'goal_projection':{'accepted':False,'modified':True}}
    assert runtime_diagnostics(env,servo)['collision_state']=='holding'
    env.collision_status['goal_projection']['accepted']=True
    assert runtime_diagnostics(env,servo)['collision_state']=='avoiding'
    env.collision_status['collision_state']='clear'
    assert runtime_diagnostics(env,servo)['collision_state']=='clear'


def test_collision_status_api_default_off_and_worker_passthrough():
    from flask import Flask
    from web.humanoid import HumanoidRuntime,create_blueprint
    runtime=HumanoidRuntime();app=Flask(__name__);app.register_blueprint(create_blueprint(runtime));client=app.test_client()
    try:
        initial=client.get('/humanoid/status').json
        assert initial['collision_avoidance'] is False and initial['collision_state']=='clear'
        assert initial['collision_status']['enabled'] is False and initial['profile_ms']=={}
        runtime.status=lambda:{'state':'ready','enabled':True,'options':{'collision_avoidance':True},'collision_state':'holding','collision_status':{'enabled':True,'collision_state':'holding','reason':'guard latch'},'profile_ms':{'total_ms':1.1},'profile_counts':{'ik_fk_calls':3}}
        runtime.running=lambda:True
        current=client.get('/humanoid/status').json
        assert current['collision_avoidance'] and current['collision_state']=='holding'
        assert current['collision_status']['reason']=='guard latch' and current['profile_ms']['total_ms']==1.1
        runtime.running=lambda:False
        off=client.get('/humanoid/status').json
        assert off['collision_state']=='clear' and off['collision_status']['runtime_off']
    finally:runtime.close()

def test_solver_unreachable_collision_goal_makes_positive_safe_progress():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools import humanoid_synth as hs
    env=HumanoidEnv();s=HumanoidServo(env);original=hs.frame
    try:
        _,_,f,t=hs.frame(0);hs.frame=lambda _:(True,{z:(1.4,-.6,1.4,0,0) for z in ('left','right')},f,t)
        p,_=hs.payload(0)
        for _ in range(30):s._retarget(p)
        target=env.data.qpos.copy()
        for z in ('left','right'):target[s.iks[z].qadr]=s.q_ik[z]
        env.set_collision_avoidance(True);g=env.collision_model
        result,diag=g.approach_safe(env.data.qpos.copy(),target,margin=.01)
        assert diag['accepted'] and 0<diag['progress_fraction']<1
        assert g.minimum(result)['distance']>=.01
    finally:env.close();hs.frame=original

def test_solver_collision_reset_explicitly_clears_latch_and_monitor_history():
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv()
    try:
        env.set_collision_avoidance(True);env.request_collision_brake('test');env.step()
        env.reset()
        assert env.collision_avoidance and not env.collision_braking
        assert env.collision_status['collision_state']=='clear'
        assert env.collision_monitor.exact_checks==0
    finally:env.close()
def test_solver_directional_brake_rest_clearance_does_not_latch():
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv()
    try:
        env.set_collision_avoidance(True);env.update_collision_brake()
        assert not env.collision_braking
        env.request_collision_brake('test');env.update_collision_brake()
        assert env.collision_braking  # settled alone is not permission to resume
        assert env.collision_status['collision_state']=='holding'
    finally:env.close()
def test_collision_planner_uses_safe_waypoint_for_cross_chest_path():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools import humanoid_synth as hs
    env=HumanoidEnv();servo=HumanoidServo(env);original=hs.frame
    try:
        _,_,f,t=hs.frame(0);hs.frame=lambda _:(True,{z:(1.,-.35,1.2,0,0) for z in ("left","right")},f,t)
        p,_=hs.payload(0);servo._retarget(p);env.set_collision_avoidance(True);g=env.collision_model
        target=env.data.qpos.copy()
        for n in g.names:target[env.qadr[n]]=servo.des[servo.index[n]]
        waypoint,diag=g.plan_safe_waypoint(env.data.qpos.copy(),target,margin=.003)
        assert diag["accepted"] and diag["route"]=="projected_waypoint"
        assert diag["path_min"]>=.003 and g.sampled_path(env.data.qpos,waypoint,24)>=.003
    finally:env.close();hs.frame=original

def test_collision_option_false_is_byte_identical_to_default_off_path():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools.humanoid_synth import payload
    envs=[HumanoidEnv(),HumanoidEnv()];servos=[HumanoidServo(e) for e in envs]
    try:
        for i in range(1200):
            t=i*.002;p,_=payload(t%21);p["received_at"]=100+t
            servos[0].tick(p,{"enabled":True,"options":{}},100+t)
            servos[1].tick(p,{"enabled":True,"options":{"collision_avoidance":False}},100+t)
            envs[0].step();envs[1].step()
        for attr in ("qpos","qvel","ctrl"):
            assert np.array_equal(getattr(envs[0].data,attr),getattr(envs[1].data,attr))
        assert np.array_equal(servos[0].cmd,servos[1].cmd)
    finally:
        for e in envs:e.close()


def test_collision_planner_minimum_fast_path_matches_full_distance():
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv()
    try:
        env.set_collision_avoidance(True);g=env.collision_model;q=env.data.qpos.copy()
        rng=np.random.default_rng(7)
        for _ in range(24):
            q[g.qadr]=np.clip(q[g.qadr]+rng.normal(0,.08,len(g.qadr)),g.lo+1e-4,g.hi-1e-4)
            expected=g.minimum(q)['distance'];actual=g.minimum_distance(q)
            assert abs(actual-expected)<=1e-12
    finally:env.close()


def test_collision_planner_minimum_fast_path_keeps_degenerate_normal():
    from sim.humanoid_collision import CapsuleModel,PAIRS
    g=CapsuleModel.__new__(CapsuleModel);g.forward=lambda q:None
    g._cap_a=np.zeros((7,3));g._cap_b=np.zeros((7,3));g._cap_r=np.zeros(7)
    g._pair_left=np.zeros(len(PAIRS),dtype=int);g._pair_right=np.ones(len(PAIRS),dtype=int)
    remembered={pair:np.array([.2,.3,.4]) for pair in PAIRS};g.previous_normals={k:v.copy() for k,v in remembered.items()}
    assert g.minimum_distance(np.zeros(1))==0.
    for pair in PAIRS:assert np.array_equal(g.previous_normals[pair],remembered[pair])


def test_async_collision_planner_isolated_geometry_latest_only_and_closes():
    import time
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv()
    try:
        env.set_collision_avoidance(True)
        planner=env.collision_planner
        q=env.data.qpos.copy()
        for _ in range(8):planner.submit(q,q)
        until=time.monotonic()+3
        while not planner._started and time.monotonic()<until:time.sleep(.005)
        assert planner._process.poll() is None
        until=time.monotonic()+2
        while planner.latest() is None and time.monotonic()<until:time.sleep(.005)
        result=planner.latest()
        assert result is not None and result[3]['sequence']<=8
        diag=planner.diagnostics()
        assert diag['planner_ready'] and diag['planner_prepare_ms']>0
        assert diag['planner_child_warmup_ms']>0
        assert planner.submitted==8
        env.set_collision_avoidance(False)
        assert planner._process.poll() is not None and env.collision_planner is None
    finally:env.close()


def test_async_collision_planner_immediate_off_does_not_leave_process():
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv()
    try:
        for _ in range(3):
            env.set_collision_avoidance(True)
            planner=env.collision_planner
            env.set_collision_avoidance(False)
            assert planner._closed and not planner._starter.is_alive()
            assert planner._process is None or planner._process.poll() is not None
    finally:env.close()


def test_collision_resources_prepared_before_enable_and_reused_on_reset():
    from sim.humanoid_env import HumanoidEnv
    env=HumanoidEnv()
    try:
        assert env.collision_model is None and not env.collision_avoidance
        prepared=env._collision_resources
        env.set_collision_avoidance(True)
        assert env.collision_model is prepared[0]
        assert env.collision_monitor is prepared[1]
        assert env.collision_status['planner_ready'] is False
        env.reset()
        assert env.collision_model is prepared[0]
        assert env.collision_monitor.exact_checks==0
        assert not env.collision_braking
    finally:env.close()


def test_collision_monitor_refreshes_before_accumulated_bound_crossing():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_collision import CollisionPathMonitor,MESH_RADII
    env=HumanoidEnv()
    try:
        monitor=CollisionPathMonitor(env.model,radii=MESH_RADII)
        q=env.data.qpos.copy()
        for angle in np.linspace(0,.2,101):
            q[env.qadr['waist_yaw_joint']]=angle
            monitor.inspect(q)
        assert monitor.uncertified==0 and monitor.penetrating==0
        q[env.qadr['waist_yaw_joint']]+=1.
        result=monitor.inspect(q)
        assert monitor.uncertified==1  # An actually unbounded step is never hidden.
        assert not result['continuous_interval_certified']
    finally:env.close()

def test_collision_pending_plan_does_not_invent_negative_clearance():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from tools.humanoid_synth import payload
    env=HumanoidEnv();servo=HumanoidServo(env)
    try:
        env.set_collision_avoidance(True)
        planner=env.collision_planner;planner.ready=True
        planner.submit=lambda *args:None
        planner.latest=lambda:None
        p,_=payload(0);p['received_at']=100.
        servo.tick(p,{'enabled':True,'options':{'collision_avoidance':True}},100.)
        assert not env.collision_plan['accepted']
        assert env.collision_plan['path_min']>.008
        env.collision_model.forward(env.data.qpos)
        row=min(env.collision_model.distances(True,.12),key=lambda r:r['distance'])
        env.data.qvel[env.collision_model.dofs]=-row['gradient']*.01
        env.update_collision_brake()
        assert not env.collision_braking
    finally:env.close()

def test_collision_escape_accepts_small_margin_recovery_without_lowering_goal_margin():
    from sim.humanoid_env import HumanoidEnv
    from sim.humanoid_teleop import HumanoidServo
    from sim.humanoid_collision import CapsuleModel,MESH_RADII
    from tools import humanoid_synth as hs
    e=HumanoidEnv();s=HumanoidServo(e);g=CapsuleModel(e.model,MESH_RADII)
    try:
        p,_=hs.payload(0);s._retarget(p)
        goal=e.data.qpos.copy()
        for name in g.names:goal[e.qadr[name]]=s.des[s.index[name]]
        # Real jump-rest raw IK endpoint is 7.598mm; start at 8.6mm.
        start,_=g.project(goal,margin=.0086,iterations=30,enabled=True)
        start_gap=g.minimum_distance(start)
        assert .0085<start_gap<.009
        waypoint,diag=g.plan_safe_waypoint(start,goal,margin=.010)
        assert diag['accepted'] and diag['route']=='escape_direct'
        assert diag['distance']>=.010-1e-8
        assert diag['path_min']>=start_gap-1e-6
    finally:e.close()