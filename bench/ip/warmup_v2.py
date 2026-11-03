import sys,time,json,numpy as np,fcntl,subprocess,os
from contextlib import nullcontext
sys.path.insert(0,'/home/user/work/robot_percept')
from web.perception_stub import PerceptionBackend
R='/home/user/work/robot_percept'
def main():
 z=np.load(R+'/bench/verify_p/frames/s00.npz'); names=['mustard','cup_d70_h60mm','box_fillet_50x30x20mm']; meshes=[R+'/downloads/demo_data/mustard0/mesh/textured_simple.obj']+[f'{R}/cad_uploads/converted/{n}/{n}.obj' for n in names[1:]]; objects=dict(zip(names,meshes))
 b=PerceptionBackend('fp'); t=b.warmup_async(z['rgb'],z['depth'],z['K'],objects);t.join(180)
 row={k:v for k,v in vars(b).items() if k.startswith('warmup_') and k!='warmup_thread'}
 if row.get('warmup_state')=='ready':
  with (nullcontext() if os.getenv('RP_BENCH_GPU_LOCK_HELD')=='1' else open('/tmp/rp_gpu.lock','a')) as f:
   if f is not None: fcntl.flock(f,fcntl.LOCK_EX)
   start=time.perf_counter(); s=b.call('segment',rgb=z['rgb'],depth=z['depth'],K=z['K'],click=(318,187));q=b.call('register',name=names[0],mesh=meshes[0],rgb=z['rgb'],depth=z['depth'],mask=s['mask'],K=z['K'])
   row.update(first_click_seconds=time.perf_counter()-start,terr_mm=float(np.linalg.norm(np.array(q['pose'])[:3,3]-z['T_mustard'][:3,3])*1000),peak_mb=q['peak_mb'],sam_ms=s['ms'],reg_ms=q['ms'])
 print(json.dumps(row,indent=2),flush=True);json.dump(row,open(R+'/bench/ip/warmup_v2.json','w'),indent=2);b.close();subprocess.run(['nvidia-smi'])
if __name__=='__main__':main()