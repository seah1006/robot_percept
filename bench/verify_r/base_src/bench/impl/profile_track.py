"""FP stage profiler on saved sim frames; seeds GT only to isolate tracking, not registration."""
import time,json,logging,sys,statistics,collections,pickle
import numpy as np
from perception.fp_runner import FPRunner
import torch
from datareader import YcbineoatReader
import estimater
import learning.training.predict_pose_refine as refmod
logging.disable(logging.INFO)
ds='data/sim_scenes/mustard_static';rd=YcbineoatReader(ds)
r=FPRunner(ds+'/mesh/textured_simple.obj');r.registered=True
stats=collections.defaultdict(list)
def wrap(obj,name):
 old=getattr(obj,name)
 def timed(*a,**kw):
  torch.cuda.synchronize();t=time.perf_counter();v=old(*a,**kw);torch.cuda.synchronize();stats[name].append((time.perf_counter()-t)*1000);return v
 setattr(obj,name,timed)
wrap(refmod,'make_crop_data_batch');wrap(r.est.refiner.model,'forward');wrap(estimater,'erode_depth');wrap(estimater,'bilateral_filter_depth');wrap(estimater,'depth2xyzmap_batch')
origempty=torch.cuda.empty_cache;out={}
frames=[(rd.get_color(i),rd.get_depth(i),np.loadtxt(ds+'/ob_in_cam/'+rd.id_strs[i]+'.txt')) for i in range(min(25,len(rd)))]
for it,cache in [(2,True),(2,False),(1,False)]:
 r.track_refine_iter=it;torch.cuda.empty_cache=origempty if cache else lambda:None
 r.est.pose_last=torch.as_tensor(frames[0][2],device='cuda',dtype=torch.float)@torch.linalg.inv(r.est.get_tf_to_centered_mesh())
 totals=[];errs=[];rots=[];stats.clear()
 for i,(rgb,dep,gt) in enumerate(frames):
  torch.cuda.synchronize();t=time.perf_counter();p=r.track(rgb,dep,rd.K);torch.cuda.synchronize();dt=time.perf_counter()-t
  if i>=3:
   totals.append(dt);errs.append(float(np.linalg.norm(p[:3,3]-gt[:3,3])*1000));rots.append(float(np.degrees(np.arccos(np.clip((np.trace(p[:3,:3]@gt[:3,:3].T)-1)/2,-1,1)))))
 key=f'iter{it}_emptycache{cache}'
 out[key]={'fps':len(totals)/sum(totals),'error_mm':statistics.mean(errs),'error_deg':statistics.mean(rots),'stage_mean_ms':{k:statistics.mean(v[3*it:] if len(v)>25 else v[3:]) for k,v in stats.items()}}
 print(key,out[key],flush=True)
torch.cuda.empty_cache=origempty
out['pickle_rgbd_ms']=0
a=time.perf_counter()
for _ in range(100):pickle.dumps((frames[0][0],frames[0][1]),protocol=pickle.HIGHEST_PROTOCOL)
out['pickle_rgbd_ms']=(time.perf_counter()-a)*10
open('bench/impl/track_profile.json','w').write(json.dumps(out,indent=2))
