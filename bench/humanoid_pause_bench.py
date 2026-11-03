"""Same-server Panda pause/resume and GT-assisted stub pick/place regression."""
import json,time,urllib.request
URL='http://127.0.0.1:5091'
def get(path='/status'):return json.load(urllib.request.urlopen(URL+path,timeout=10))
def post(path,data):return json.load(urllib.request.urlopen(urllib.request.Request(URL+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'}),timeout=30))
def until(fn,timeout=90):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  s=get()
  if fn(s):return s
  time.sleep(.1)
 raise RuntimeError('timeout:'+str(s))
until(lambda s:s.get('ready') and not s.get('active_command'))
post('/humanoid/mode',{'enabled':True});until(lambda s:s.get('humanoid_render_paused') and not s.get('active_command'))
time.sleep(.2);a=get()['frame_seq'];time.sleep(1);b=get()['frame_seq'];assert a==b,(a,b)
post('/humanoid/mode',{'enabled':False});r=until(lambda s:not s.get('humanoid_render_paused') and s.get('frame_seq',0)>b,10);resume=r['frame_seq']
point=r['objects']['mustard']['center_px'];post('/click',dict(x=point[0],y=point[1]))
pick=post('/robot/pick',{'gt_assist':True});s=until(lambda s:s.get('last_command',{}).get('id')==pick['command_id']);assert s['last_command']['ok'],s['last_command'];assert s.get('held_object'),s
place=post('/robot/place',{'gt_assist':True});s=until(lambda s:s.get('last_command',{}).get('id')==place['command_id']);assert s['last_command']['ok'],s['last_command'];assert not s.get('held_object'),s
print(json.dumps({'pause_seq':[a,b],'resume_seq':resume,'pick':True,'place':True,'GT_assisted':True}),flush=True)
