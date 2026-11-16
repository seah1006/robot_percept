import os, sys, json
os.environ.setdefault('HSA_ENABLE_DXG_DETECTION','1')
lib=os.environ.get('CONDA_PREFIX',sys.prefix)+'/lib'
if lib not in os.environ.get('LD_LIBRARY_PATH','').split(':'):
 os.environ['LD_LIBRARY_PATH']=lib+':'+os.environ.get('LD_LIBRARY_PATH','')
 os.execv(sys.executable,[sys.executable]+sys.argv)
import torch
r=dict(torch=torch.__version__,hip=torch.version.hip,HSA_ENABLE_DXG_DETECTION=os.getenv('HSA_ENABLE_DXG_DETECTION'),available=torch.cuda.is_available())
print(json.dumps(r),flush=True)
if not r['available']: raise SystemExit(2)
r['name']=torch.cuda.get_device_name(0)
a=torch.ones((32,32),device='cuda'); b=a@a; torch.cuda.synchronize()
r['matmul_sum']=b.sum().item()
free,total=torch.cuda.mem_get_info()
r.update(device_used_bytes=total-free,process_allocated_bytes=torch.cuda.memory_allocated(),process_reserved_bytes=torch.cuda.memory_reserved())
print(json.dumps(r),flush=True)
