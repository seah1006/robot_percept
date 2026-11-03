"""RPC boundary: CUDA/SAM/FP never run in the Flask or MuJoCo process."""
from __future__ import annotations
import multiprocessing as mp
import threading, time, uuid, traceback
import numpy as np

def estimate_pose(rgb, depth, K, info, object_name):
    T=np.asarray(info['gt_pose'],float).copy()
    T[:3,3]+=np.random.default_rng(7).normal(0,.0015,3)
    return T

def _worker(req,res):
    import os, torch
    from pathlib import Path
    from perception.fp_runner import FPRunner
    from perception.sam_runner import select_candidate
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    runners={}; predictor=None; active=None
    res.put(('ready',True,None))
    while True:
        item=req.get()
        if item is None: break
        ident,op,a=item
        try:
            t=time.perf_counter()
            if op=='segment':
                # FP changes default tensor type. SAM expects CPU prompt tensors.
                torch.set_default_tensor_type(torch.FloatTensor)
                if predictor is None:
                    model=build_sam2('configs/sam2.1/sam2.1_hiera_s.yaml',os.getenv('SAM2_CHECKPOINT','/home/user/ai_class/sam/checkpoints/sam2.1_hiera_small.pt'),device='cuda')
                    predictor=SAM2ImagePredictor(model)
                predictor.model.to('cuda')
                with torch.inference_mode(),torch.autocast('cuda',dtype=torch.float16):
                    predictor.set_image(a['rgb'])
                    masks,scores,_=predictor.predict(point_coords=np.array([a['click']]),point_labels=np.array([1]),multimask_output=True)
                selected=select_candidate(masks,scores,a['click'],a.get('depth'))
                result={'mask':masks[selected].astype(bool),'sam_score':float(scores[selected]),'sam_selected':selected}
                predictor.reset_predictor(); predictor.model.to('cpu'); torch.cuda.empty_cache()
            elif op=='register':
                name=a['name']; mesh=a['mesh']
                if name not in runners:
                    # Share the heavyweight neural networks between per-mesh estimators.
                    if runners:
                        ref=next(iter(runners.values()))
                        runners[name]=FPRunner(mesh,scorer=ref.est.scorer,refiner=ref.est.refiner)
                    else: runners[name]=FPRunner(mesh)
                active=name
                result={'pose':np.asarray(runners[name].register(a['rgb'],a['depth'],a['mask'],a['K'])).tolist()}
            elif op=='track':
                if active!=a['name']:raise RuntimeError('Tracker is not registered for selected object')
                result={'pose':np.asarray(runners[active].track(a['rgb'],a['depth'],a['K'])).tolist()}
            elif op=='drop': active=None; result={}
            else:raise ValueError(op)
            torch.cuda.synchronize();result['ms']=(time.perf_counter()-t)*1000
            result['peak_mb']=torch.cuda.max_memory_allocated()/1024**2
            res.put((ident,True,result))
        except Exception:res.put((ident,False,traceback.format_exc()))

class PerceptionBackend:
    def __init__(self,mode='fp'):
        self.mode=mode;self.warning=None;self.proc=None;self.lock=threading.RLock()
        if mode=='fp':
            ctx=mp.get_context('spawn');self.req_q=ctx.Queue();self.res_q=ctx.Queue()
            self.proc=ctx.Process(target=_worker,args=(self.req_q,self.res_q),daemon=True);self.proc.start()
            # Initialization is lazy so Flask/video stay responsive.
    def call(self,op,**args):
        with self.lock:
            ident=uuid.uuid4().hex;self.req_q.put((ident,op,args))
            while True:
                rid,ok,payload=self.res_q.get(timeout=180)
                if rid=='ready':continue
                if rid!=ident:continue
                if not ok:
                    self.warning=payload.splitlines()[-1];raise RuntimeError(payload)
                self.warning=None;return payload
    def close(self):
        if self.proc is not None:
            self.req_q.put(None);self.proc.join(timeout=2)
            if self.proc.is_alive():self.proc.terminate();self.proc.join(2)
