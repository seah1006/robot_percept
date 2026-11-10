import argparse,hashlib,json,os,platform,time
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
REV='a2bb814dd30d776dcf7e30523b00659f4f141c71'
p=argparse.ArgumentParser();p.add_argument('--threads',type=int,default=4);p.add_argument('--n',type=int,default=20);p.add_argument('--output',default='bench/g0/cpu.json');a=p.parse_args()
assert a.n>=20
torch.set_num_threads(a.threads);torch.set_num_interop_threads(1)
cache=Path.home()/'.cache/huggingface';cache.mkdir(parents=True,exist_ok=True)
image_path=Path('sim_test/results/egl_d3d12/rgb.png')
image=Image.open(image_path).convert('RGB').resize((640,360))
t=time.perf_counter()
processor=AutoProcessor.from_pretrained('IDEA-Research/grounding-dino-tiny',revision=REV,cache_dir=str(cache))
model=AutoModelForZeroShotObjectDetection.from_pretrained('IDEA-Research/grounding-dino-tiny',revision=REV,cache_dir=str(cache)).eval()
load=time.perf_counter()-t
def run():
 inputs=processor(images=image,text='a red cube. a blue cube.',return_tensors='pt',do_resize=False)
 with torch.inference_mode(): model(**inputs)
 return list(inputs['pixel_values'].shape)
t=time.perf_counter();shape=run();first=time.perf_counter()-t
for _ in range(2):run()
samples=[]
for _ in range(a.n):
 t=time.perf_counter();run();samples.append((time.perf_counter()-t)*1000)
r=dict(source='[시뮬인식]',gt_assisted=False,revision=REV,torch=torch.__version__,numpy=np.__version__,python=platform.python_version(),threads=torch.get_num_threads(),interop_threads=torch.get_num_interop_threads(),load_seconds=load,first_inference_ms=first*1000,warmup=2,n=a.n,samples_ms=samples,p50_ms=float(np.percentile(samples,50)),p95_ms=float(np.percentile(samples,95)),image=str(image_path),image_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),input_shape=shape,loadavg=os.getloadavg(),device='cpu',device_vram=None,process_vram=None)
Path(a.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
