"""Start a dedicated server on 5081 first; never targets production 5080."""
import requests,time,json,traceback
from pathlib import Path
base='http://127.0.0.1:5081';out=Path(__import__('os').getenv('TEST_OUTPUT','/tmp/web-perception-test'));out.mkdir(parents=True,exist_ok=True)
def status():return requests.get(base+'/status').json()
def post(p,d=None):
 r=requests.post(base+p,json=d or {},timeout=180);j=r.json();print(p,r.status_code,json.dumps(j)[:1600],flush=True);return j
def wait(j):
 cid=j.get('command_id');end=time.time()+75
 while time.time()<end:
  s=status();c=s.get('last_command') or {}
  if c.get('id')==cid:return c
  time.sleep(.25)
 return {'ok':False,'error':'timeout'}
for _ in range(150):
 try:
  if status().get('ready'):break
 except:pass
 time.sleep(.5)
results=[]
try:
 for i in range(4):
  wait(post('/reset' if i==0 else '/scene/randomize'))
  s=status();xy=s['objects']['mustard']['center_px'];j=post('/click',dict(zip(['x','y'],xy)));row={'run':i,'registration':j}
  if not j.get('ok'):results.append(row);break
  time.sleep(5);row['tracking']=status().get('pose');(out/f'overlay_{i}.jpg').write_bytes(requests.get(base+'/frame.jpg?gt=1').content)
  row['pick']=wait(post('/robot/pick'));print('pick result',row['pick'],flush=True)
  if row['pick'].get('ok'):
   # Target visible table world coordinate .50,.15,.32 (projected using calibrated camera).
   import numpy as np
   s=status();T=np.asarray(s['T_world_cam']);K=np.asarray(s['camera_K']);p=np.linalg.inv(T)@np.array([.50,.15,.32,1]);uv=K@p[:3];uv=uv[:2]/uv[2]
   j=post('/click',{'x':float(uv[0]),'y':float(uv[1]),'mode':'place'});row['place']=wait(j)
   s=status()
   if 'xyz' in j:row['place_error_mm']=float(np.linalg.norm(np.array(s['objects']['mustard']['T_world_obj'])[:2,3]-np.array(j['xyz'])[:2])*1000)
   print('place',row.get('place'),row.get('place_error_mm'),flush=True)
  row['gpu']=status().get('gpu');results.append(row);(out/'results.json').write_text(json.dumps(results,indent=2))
 # CAD
 with open('cad_uploads/samples/box_fillet_50x30x20mm.step','rb') as f:
  r=requests.post(base+'/cad/upload',files={'file':f},timeout=180);j=r.json();print('CAD',j,flush=True)
 if j.get('ok'):
  s=status();xy=s['objects'][j['name']]['center_px'];reg=post('/click',dict(zip(['x','y'],xy)));cad={'registration':reg}
  if reg.get('ok'):cad['pick']=wait(post('/robot/pick'))
  results.append({'cad':cad});(out/'cad_overlay.jpg').write_bytes(requests.get(base+'/frame.jpg?gt=1').content)
except Exception:traceback.print_exc()
finally:(out/'results.json').write_text(json.dumps(results,indent=2))