import multiprocessing as mp
import time
import traceback
import numpy as np


def worker(requests, responses):
    # No simulator or web imports in this CUDA process.
    import torch
    from perception.fp_runner import FPRunner
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    import os
    predictor = None
    runners = {}
    active = None
    while True:
        a = requests.get()
        if a is None:
            return
        try:
            t = time.perf_counter()
            if a['op'] == 'register':
                torch.set_default_tensor_type(torch.FloatTensor)
                if predictor is None:
                    predictor = SAM2ImagePredictor(build_sam2('configs/sam2.1/sam2.1_hiera_s.yaml', os.getenv('SAM2_CHECKPOINT','/home/user/ai_class/sam/checkpoints/sam2.1_hiera_small.pt'), device='cuda'))
                predictor.model.to('cuda')
                torch.cuda.reset_peak_memory_stats()
                with torch.inference_mode(), torch.autocast('cuda',dtype=torch.float16):
                    predictor.set_image(a['rgb'])
                    masks, scores, _ = predictor.predict(point_coords=np.asarray([a['click']]),point_labels=np.array([1]),multimask_output=True)
                selected = int(np.argmax(scores))
                mask = masks[selected].astype(bool)
                torch.cuda.synchronize()
                sam_s = time.perf_counter()-t
                sam_peak = torch.cuda.max_memory_allocated()
                predictor.reset_predictor()
                predictor.model.to('cpu')
                torch.cuda.empty_cache()
                name = a['name']
                if name not in runners:
                    ref = next(iter(runners.values()),None)
                    runners[name] = FPRunner(a['mesh'], scorer=ref.est.scorer if ref else None, refiner=ref.est.refiner if ref else None)
                active = runners[name]
                start = time.perf_counter()
                pose = active.register(a['rgb'],a['depth'],mask,a['K'])
                extra = dict(mask=mask,scores=scores.tolist(),selected_index=selected,sam_s=sam_s,sam_peak_bytes=sam_peak)
            else:
                start = time.perf_counter()
                pose = active.track(a['rgb'],a['depth'],a['K'])
                extra = {}
            torch.cuda.synchronize()
            responses.put(dict(ok=True,pose=np.asarray(pose),latency_s=time.perf_counter()-start,peak_bytes=torch.cuda.max_memory_allocated(),**extra))
        except Exception:
            responses.put(dict(ok=False,error=traceback.format_exc()))


class Client:
    def __init__(self, timeout=180):
        ctx=mp.get_context('spawn')
        self.q,self.r=ctx.Queue(),ctx.Queue()
        self.p=ctx.Process(target=worker,args=(self.q,self.r),daemon=True)
        self.p.start()
        self.timeout=timeout
    def call(self, **kw):
        self.q.put(kw)
        try:
            result=self.r.get(timeout=self.timeout)
        except Exception:
            # Never allow a timed-out reply to be misassociated with a later trial.
            self.p.terminate(); self.p.join(3)
            self.__init__(self.timeout)
            raise
        if not result['ok']:
            raise RuntimeError(result['error'])
        return result
    def close(self):
        self.q.put(None)
        self.p.join(3)
        if self.p.is_alive():
            self.p.terminate()
            self.p.join(3)
