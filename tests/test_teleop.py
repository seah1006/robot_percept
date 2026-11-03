from types import SimpleNamespace
from flask import Flask
from web.teleop import create_blueprint

def client():
 app=Flask(__name__); state={};app.register_blueprint(create_blueprint(SimpleNamespace(status=state)));return app.test_client(),state

def test_validation_and_mode():
 c,s=client()
 assert c.post('/teleop/update',json={'detected':True,'x':float('nan')}).status_code==400
 assert c.post('/teleop/update',json={'detected':True,'x':.5,'y':.5,'scale':.15,'pinch':.6}).status_code==200
 assert c.post('/teleop/mode',json={'enabled':True}).status_code==200
 assert c.post('/teleop/calibrate').status_code==200
 assert c.get('/teleop/status').json['detected']
 s['active_command']='pick'
 assert c.post('/teleop/mode',json={'enabled':True}).status_code==409
 assert c.post('/teleop/mode',json={'enabled':False}).status_code==200
 assert c.post('/teleop/preview',data=b'bad').status_code==400
 assert c.post('/teleop/update',json={'detected':False}).status_code==200
 assert not c.get('/teleop/status').json['detected']
def test_servo_square_circle_no_crash():
 import os,time,math
 os.environ.setdefault('MUJOCO_GL','egl')
 import numpy as np
 from sim.env import SimEnv
 from sim.teleop import TeleopServo
 env=SimEnv(objects=('mustard',),width=160,height=120,seed=3)
 st={'teleop_enabled':True}; servo=TeleopServo(env,st); peak=0.
 try:
  for i in range(4000):
   t=i*env.model.opt.timestep
   if t<1:x,y=.5,.5
   elif t<4:
    corners=[(.6,.5),(.6,.4),(.4,.4),(.4,.5)];x,y=corners[int((t-1)/.75)%4]
   else:x,y=.5+.1*math.sin((t-4)*2),.5+.1*math.cos((t-4)*2)
   st['teleop_sample']={'detected':True,'x':x,'y':y,'scale':.15,'pinch':.6,'received_at':time.time()}
   servo.tick();env.step(1)
   peak=max(peak,float(np.max(np.abs(env.data.qvel[servo.dofs]))))
  assert peak<=.65, peak
  # A measured out-of-range position must never crash the hold/off path.
  st['teleop_enabled']=False;env.data.qpos[servo.qadr[0]]=servo.limits[0,1]+.0001
  env.data.time+=.03;servo.tick()
 finally:env.close()


def test_mjpeg_preview_stream():
 c,s=client()
 jpeg=b"\xff\xd8test-frame\xff\xd9"
 assert c.post('/teleop/preview',data=jpeg,content_type='image/jpeg').status_code==200
 r=c.get('/teleop/preview.mjpg',buffered=False)
 assert 'multipart/x-mixed-replace' in r.content_type
 frame=next(iter(r.response))
 assert frame.startswith(b'--frame\r\n') and jpeg in frame
 r.close()
 assert 'preview_hz' in c.get('/teleop/status').json
