import json,time,numpy as np
from sim.env import SimEnv
from perception.fp_runner import FPRunner
from perception.sam_runner import select_candidate
r=json.load(open('bench/ip/diagnosis/rows.json')); row=next(v for v in r if v['object']=='mustard' and v['seed']==2 and v['point_type']=='center')
a=np.load(row['artifact']); click=row['click'];start=time.perf_counter()
for _ in range(100):i=select_candidate(a['masks'],a['scores'],click,a['depth'])
print('policy_ms',1000*(time.perf_counter()-start)/100,flush=True)
with SimEnv(objects=('mustard',),seed=2) as env:
 gt=env.T_cam_obj('mustard'); K=env.camera_K();mesh=env.object_mesh_path('mustard')
 for label,index in [('score',row['selected']),('depth_area',i)]:
  t=time.perf_counter();fp=FPRunner(mesh);pose=np.asarray(fp.register(a['rgb'],a['depth'],a['masks'][index],K));print(label,'register_s',time.perf_counter()-t,'error_mm',np.linalg.norm(pose[:3,3]-gt[:3,3])*1000,flush=True);del fp
