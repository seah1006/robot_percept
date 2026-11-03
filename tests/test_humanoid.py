import numpy as np
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
