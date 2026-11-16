"""Grounding DINO benchmark. Run via measure -> gpu locks; no production imports."""
import argparse,hashlib,json,os,sys,time,threading,subprocess
from pathlib import Path
os.environ.setdefault('HSA_ENABLE_DXG_DETECTION','1')
lib=os.environ.get('CONDA_PREFIX',sys.prefix)+'/lib'
if lib not in os.environ.get('LD_LIBRARY_PATH','').split(':'):
 os.environ['LD_LIBRARY_PATH']=lib+':'+os.environ.get('LD_LIBRARY_PATH','')
 os.execv(sys.executable,[sys.executable]+sys.argv)
import numpy as np
import torch
from PIL import Image
from transformers import AutoProcessor,AutoModelForZeroShotObjectDetection
REV='a2bb814dd30d776dcf7e30523b00659f4f141c71'
p=argparse.ArgumentParser();p.add_argument('--n',type=int,default=20);p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=360);p.add_argument('--output',default='bench/g0/gpu.json');p.add_argument('--coexist',choices=['none','sam2','fp','both'],default='none');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
assert a.n>=20
backend='rocm' if torch.version.hip and torch.cuda.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu'
if a.dry_run:
 print(json.dumps(dict(backend=backend,width=a.width,height=a.height,n=a.n,coexist=a.coexist)));sys.exit(0)
dev='cpu' if backend=='cpu' else 'cuda';torch.set_num_threads(4)
image_path=Path('sim_test/results/egl_d3d12/rgb.png');image=Image.open(image_path).convert('RGB').resize((a.width,a.height))
load_start=os.getloadavg();peaks=[];stop=threading.Event()
def used():
 f,t=torch.cuda.mem_get_info();return (t-f)/2**20
def monitor():
 while not stop.wait(.02):
  peaks.append(used())
def sync():
 if dev=='cuda':torch.cuda.synchronize()
base=used() if dev=='cuda' else None
if dev=='cuda':
 thread=threading.Thread(target=monitor,daemon=True);thread.start();torch.cuda.reset_peak_memory_stats()
co=[];co_errors=[]
try:
 if a.coexist in ('sam2','both'):
  from sam2.build_sam import build_sam2
  co.append(build_sam2('configs/sam2.1/sam2.1_hiera_s.yaml',os.getenv('SAM2_CHECKPOINT','/home/user/ai_class/sam/checkpoints/sam2.1_hiera_small.pt'),device=dev))
 if a.coexist in ('fp','both'):
  from perception.fp_runner import FPRunner
  co.append(FPRunner('downloads/demo_data/mustard0/mesh/textured_simple.obj'))
except Exception as e:co_errors.append(repr(e))
t=time.perf_counter();processor=AutoProcessor.from_pretrained('IDEA-Research/grounding-dino-tiny',revision=REV);model=AutoModelForZeroShotObjectDetection.from_pretrained('IDEA-Research/grounding-dino-tiny',revision=REV).eval().to(dev);sync();load=time.perf_counter()-t
# FP may set global CUDA tensor defaults; explicit CPU processor conversion then device transfer.
def run():
 inputs=processor(images=image,text='a red cube. a blue cube.',return_tensors='pt',do_resize=False).to(dev)
 with torch.inference_mode():out=model(**inputs)
 sync()
 if dev=='cuda':peaks.append(used())
 return inputs,out
t=time.perf_counter();inputs,out=run();first=1000*(time.perf_counter()-t)
for _ in range(2):run()
samples=[]
for _ in range(a.n):
 t=time.perf_counter();run();samples.append(1000*(time.perf_counter()-t))
res=processor.post_process_grounded_object_detection(out,inputs.input_ids,threshold=.35,text_threshold=.25,target_sizes=[(a.height,a.width)])[0]
dets=[dict(label=str(l),score=float(s),box=b.tolist()) for s,l,b in zip(res['scores'],res.get('text_labels',res.get('labels')),res['boxes'])]
stop.set()
if dev=='cuda':thread.join()
r=dict(source='[시뮬인식]',gt_assisted=False,revision=REV,backend=backend,torch=torch.__version__,numpy=np.__version__,device=torch.cuda.get_device_name(0) if dev=='cuda' else 'cpu',width=a.width,height=a.height,n=a.n,warmup=2,load_seconds=load,first_inference_ms=first,samples_ms=samples,p50_ms=float(np.percentile(samples,50)),p95_ms=float(np.percentile(samples,95)),loadavg_start=load_start,loadavg_end=os.getloadavg(),device_used_before_mib=base,device_used_peak_sampled_mib=max(peaks) if peaks else None,process_max_allocated_mib=torch.cuda.max_memory_allocated()/2**20 if dev=='cuda' else None,process_max_reserved_mib=torch.cuda.max_memory_reserved()/2**20 if dev=='cuda' else None,coexist=a.coexist,coexist_errors=co_errors,coexist_scope='model resident only; no SAM2/FP inference warmup',vram_limit_mib=7168,vram_note='7.0GiB device-wide sampled used incl Windows; process allocated reported separately; sample is not true instantaneous peak',image=str(image_path),image_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),detections=dets)
Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False),flush=True)