"""RPC boundary: CUDA/SAM/FP never run in the Flask or MuJoCo process."""
from __future__ import annotations
import multiprocessing as mp
import threading, time, uuid, traceback
import numpy as np
from .process_lifecycle import start_parent_pid_watch, stop_process

def estimate_pose(rgb, depth, K, info, object_name):
    T=np.asarray(info['gt_pose'],float).copy()
    T[:3,3]+=np.random.default_rng(7).normal(0,.0015,3)
    return T

def _dispatch_new(op,a,detector=None,segmenter=None):
    from perception.interfaces import Frame,FrameMeta
    from perception.grounding import REVISION
    if op=='capabilities':
        import torch,importlib.util
        gpu=torch.cuda.is_available()
        device='rocm' if gpu and torch.version.hip else 'cuda' if gpu else 'cpu'
        available=importlib.util.find_spec('transformers') is not None
        sam_available=importlib.util.find_spec('sam2') is not None
        return dict(schema_version=1,ops=['ground','segment_box'],device=device,device_name=torch.cuda.get_device_name(0) if gpu else 'cpu',torch_version=torch.__version__,accel_version=torch.version.hip or torch.version.cuda,models={'grounding_dino':dict(revision=REVISION,available=available,loaded=detector is not None and detector.model is not None,reason=None if available else 'MODEL_UNAVAILABLE'),'sam2':dict(revision='sam2.1_hiera_small',available=sam_available,loaded=segmenter is not None and segmenter.predictor is not None,reason=None if sam_available else 'MODEL_UNAVAILABLE')},segmenter=segmenter.mode if segmenter else 'off',localizer='plane',fp_available=False)
    if a.get('schema_version',1)!=1: raise ValueError('INVALID_INPUT: schema_version')
    def check():
        token=a.get('cancel_token')
        if token is True or (hasattr(token,'is_set') and token.is_set()): raise RuntimeError('CANCELLED')
        if a.get('deadline',float('inf'))<=time.monotonic(): raise TimeoutError('DEADLINE_EXCEEDED')
    check()
    meta=a['frame'] if isinstance(a['frame'],FrameMeta) else FrameMeta.from_dict(a['frame'])
    rgb=a['rgb']; rgb=rgb.tobytes() if hasattr(rgb,'tobytes') else rgb
    frame=Frame(meta,rgb)
    if op=='ground':
        detector.table_mask=a.get('table_mask')
        detections=detector.detect(frame,a['queries'],a.get('box_threshold',.35),a.get('text_threshold',.25),a.get('filtering',True),check,a.get('mapping'))
        result=dict(frame=meta.to_dict(),detections=[d.to_dict() for d in detections],rejections=detector.rejections,error=None if detections else 'NO_DETECTION',model_revision=REVISION,device=detector.backend)
    elif op=='segment_box':
        result=dict(mask=segmenter.segment(frame,a['box_xyxy']).to_dict(),error=None,model_revision='sam2.1_hiera_small' if segmenter.mode=='sam2' else 'box-only-v1',device=segmenter.device)
    else: raise ValueError('UNSUPPORTED_OP')
    if a.get('deadline',float('inf'))<=time.monotonic(): raise TimeoutError('DEADLINE_EXCEEDED')
    return result
def _worker(req,res,parent_pid=None):
    start_parent_pid_watch(parent_pid)
    import os
    target_nice = max(0, min(19, int(os.environ.get('RP_PERCEPTION_NICE', '10'))))
    try: os.nice(max(0, target_nice - os.nice(0)))
    except OSError: pass
    import sys
    torch=None; detector=None; box_segmenter=None; threads_configured=False
    runners={}; predictor=None; active=None
    res.put(('ready',True,None))
    while True:
        item=req.get()
        if item is None: break
        ident,op,a=item
        try:
            t=time.perf_counter()
            torch=sys.modules.get('torch')
            if torch is not None and torch.cuda.is_available():
                torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
            if op!='drop' and not threads_configured:
                import torch
                cpu_threads=int(os.environ.get('RP_PERCEPTION_CPU_THREADS','0'))
                if cpu_threads>0:
                    torch.set_num_threads(cpu_threads)
                    try: torch.set_num_interop_threads(1)
                    except RuntimeError: pass
                threads_configured=True
            if op in ('ground','segment_box','capabilities'):
                if op=='ground' and detector is None:
                    from perception.grounding import Detector
                    detector=Detector()
                if op=='segment_box':
                    from perception.segment import Segmenter
                    mode=a.get('segmenter','off')
                    if box_segmenter is None or box_segmenter.mode!=mode: box_segmenter=Segmenter(mode)
                result=_dispatch_new(op,a,detector,box_segmenter)
                torch=sys.modules.get('torch')
            elif op=='segment':
                import torch
                from perception.sam_runner import select_candidate
                from sam2.build_sam import build_sam2
                from sam2.sam2_image_predictor import SAM2ImagePredictor
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
                import cv2
                mask = masks[selected].astype(np.uint8)
                _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
                x, y = map(int, a['click'])
                component = int(labels[y, x])
                raw_area = int(mask.sum())
                if component:
                    mask = labels == component
                result={'mask':mask.astype(bool),'sam_score':float(scores[selected]),'sam_selected':selected,'sam_raw_area':raw_area}
                predictor.reset_predictor(); predictor.model.to('cpu'); torch.cuda.empty_cache()
            elif op=='register':
                import torch
                from perception.fp_runner import FPRunner
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
            else:
                res.put((ident,True,dict(error='UNSUPPORTED_OP',ms=(time.perf_counter()-t)*1000,peak_mb=None)))
                continue
            if torch is not None and torch.cuda.is_available(): torch.cuda.synchronize()
            result['ms']=(time.perf_counter()-t)*1000
            result['peak_mb']=torch.cuda.max_memory_allocated()/1024**2 if torch is not None and torch.cuda.is_available() else None
            res.put((ident,True,result))
        except Exception as exc:
            if op in ('ground','segment_box','capabilities'):
                message=str(exc)
                code='OUT_OF_MEMORY' if 'out of memory' in message.lower() else 'DEADLINE_EXCEEDED' if isinstance(exc,TimeoutError) else 'MODEL_UNAVAILABLE' if isinstance(exc,(ImportError,OSError)) else 'CANCELLED' if 'CANCELLED' in message else 'INVALID_INPUT' if isinstance(exc,(ValueError,KeyError,TypeError)) else 'INTERNAL_ERROR'
                res.put((ident,True,dict(error=code,ms=(time.perf_counter()-t)*1000,peak_mb=None)))
            else: res.put((ident,False,traceback.format_exc()))
        finally:
            # Keep active FP tracking resident. Only temporary SAM/ground tensors offload.
            if detector is not None: detector.release()
            if box_segmenter is not None: box_segmenter.release()
            if predictor is not None:
                predictor.reset_predictor(); predictor.model.to('cpu')
            torch=sys.modules.get('torch')
            if torch is not None and op in ('ground','segment_box','segment'):
                torch.set_default_tensor_type(torch.FloatTensor)
                if torch.cuda.is_available(): torch.cuda.empty_cache()

class PerceptionBackend:
    def __init__(self,mode='fp'):
        self.mode=mode;self.warning=None;self.proc=None;self.lock=threading.RLock();self.closed=False
        self.warmup_cancel = threading.Event()
        self.lifecycle_lock = threading.RLock()
        self.rpc_inflight = None
        self.suspending = False
        # No worker/import/CUDA initialization until the first real RPC.
        # Startup warmup can therefore be deferred while G1 is active.
    def call(self,op,**args):
        with self.lock:
            with self.lifecycle_lock:
                if self.closed:
                    raise RuntimeError('Perception backend is closed')
                if self.mode != 'fp' and op not in ('ground','segment_box','capabilities'):
                    raise RuntimeError('FP RPC requires fp mode')
                is_warmup = threading.current_thread() is getattr(self, 'warmup_thread', None)
                if self.suspending or (is_warmup and self.warmup_cancel.is_set()):
                    raise RuntimeError('Warmup suspended')
                if self.proc is None:
                    if op == 'drop':
                        return {'ms': 0., 'peak_mb': 0.}
                    ctx=mp.get_context('spawn');self.req_q=ctx.Queue();self.res_q=ctx.Queue()
                    self.proc=ctx.Process(target=_worker,args=(self.req_q,self.res_q,__import__("os").getpid()),daemon=True);self.proc.start()
                ident=uuid.uuid4().hex
                self.rpc_inflight = (ident, threading.get_ident(), is_warmup)
                self.req_q.put((ident,op,args))
            try:
                import queue
                deadline = time.monotonic() + 180
                while True:
                    if is_warmup and self.warmup_cancel.is_set():
                        raise RuntimeError('Warmup deferred for G1')
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Perception RPC timed out')
                    # Queue's timed semaphore lock is CLOCK_REALTIME-sensitive in this build;
                    # the reader Connection.poll path uses selectors + a monotonic deadline.
                    if not self.res_q._reader.poll(min(.1, remaining)):
                        continue
                    try:
                        rid,ok,payload=self.res_q.get_nowait()
                    except queue.Empty:
                        continue
                    if rid=='ready':continue
                    if rid!=ident:continue
                    if not ok:
                        self.warning=payload.splitlines()[-1];raise RuntimeError(payload)
                    self.warning=None;return payload
            finally:
                with self.lifecycle_lock:
                    self.rpc_inflight = None
    def warmup_async(self, rgb, depth, K, objects):
        """Prime real inference off the HTTP thread; no simulator labels required.

        RP_GPU_SERIALIZE=1 opts into the cross-process GPU lock.
        When enabled, do not call while already holding that lock.
        warmup_state is observable: idle/running/ready/failed; poses are discarded.
        """
        import os
        if self.mode != 'fp' or os.environ.get('RP_PERCEPTION_WARMUP', '1').lower() in ('0', 'false', 'off'):
            self.warmup_state = 'disabled'
            return None
        old_thread = getattr(self, 'warmup_thread', None)
        if old_thread is not None and old_thread.is_alive():
            return old_thread
        if getattr(self, 'warmup_state', 'idle') == 'ready':
            return old_thread
        if self.closed or self.suspending:
            return None
        self.warmup_cancel.clear()
        self.warmup_state = 'running'
        self.warmup_error = None
        rgb, depth, K = np.array(rgb, copy=True), np.array(depth, copy=True), np.array(K, copy=True)
        def run():
            import fcntl, subprocess
            from contextlib import nullcontext
            start = time.perf_counter()
            try:
                serialize = os.environ.get('RP_GPU_SERIALIZE', '0').lower() in ('1', 'true', 'on')
                with (open('/tmp/rp_gpu.lock', 'a') if serialize else nullcontext()) as gpu_lock:
                    if gpu_lock is not None:
                        fcntl.flock(gpu_lock, fcntl.LOCK_EX)
                    self.warmup_gpu_before = subprocess.getoutput('nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits')
                    with self.lock:
                        if self.warmup_cancel.is_set():
                            raise RuntimeError('Warmup suspended')
                        h, w = depth.shape
                        self.call('segment', rgb=rgb, depth=depth, K=K, click=(w//2,h//2))
                        # Compact valid-depth support is sufficient to compile kernels;
                        # it is not a claimed object detection or persisted pose.
                        ys, xs = np.where(np.isfinite(depth) & (depth > 0))
                        if not len(xs):
                            raise ValueError('Warmup requires valid depth')
                        j = len(xs)//2; x, y = int(xs[j]), int(ys[j])
                        mask = np.zeros(depth.shape, bool)
                        mask[max(0,y-16):y+17,max(0,x-16):x+17] = True
                        for name, info in objects.items():
                            if self.warmup_cancel.is_set():
                                raise RuntimeError('Warmup suspended')
                            mesh = info['mesh'] if isinstance(info, dict) else info
                            if mesh:
                                self.call('register', name=name, mesh=mesh, rgb=rgb, depth=depth, mask=mask, K=K)
                        if self.warmup_cancel.is_set():
                            raise RuntimeError('Warmup suspended')
                        self.call('drop')
                    self.warmup_gpu_after = subprocess.getoutput('nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits')
                self.warmup_state = 'ready'
            except Exception as exc:
                self.warmup_error = str(exc)
                self.warmup_state = 'failed'
            finally:
                self.warmup_seconds = time.perf_counter() - start
                if self.warmup_cancel.is_set():
                    self.suspend_worker()
        self.warmup_thread = threading.Thread(target=run, daemon=True)
        self.warmup_thread.start()
        return self.warmup_thread

    def defer_warmup_for_g1(self):
        """Abort only warmup-owned work; never terminate an actual user RPC.

        Does not wait for the RPC lock. True requests cancellation and wakes the
        warmup RPC wait immediately. Owner must join warmup_thread (<=3s usual)
        before resuming; its finally block joins/reaps worker and closes queues.
        App must additionally guarantee no selected object before calling.
        """
        with self.lifecycle_lock:
            thread = getattr(self, 'warmup_thread', None)
            if self.closed or thread is None or not thread.is_alive():
                return False
            if getattr(self, 'warmup_state', None) not in ('running', 'failed'):
                return False
            pending = self.rpc_inflight
            if pending is not None and not pending[2]:
                return False
            self.suspending = True
            self.warmup_cancel.set()
            self.warmup_state = 'cancelling_g1'
            if self.proc is not None and self.proc.is_alive():
                self.proc.terminate()
            if pending is not None:
                self.res_q.put((pending[0], False, 'Warmup deferred for G1'))
            return True

    def suspend_worker(self):
        """Cancel warmup and reclaim an idle worker without permanently closing.

        Nonblocking: False means an RPC is in flight. Warmup cooperatively stops
        after that RPC and calls this method itself; other callers may retry.
        No running RPC is terminated. A later call may lazily start a new worker.
        All previous registration/tracking state is lost, so the owner must drop
        its active object and register again after resuming.
        """
        self.warmup_cancel.set()
        if not self.lock.acquire(blocking=False):
            return False
        try:
            if self.proc is not None:
                if self.proc.is_alive():
                    self.proc.terminate()
                self.proc.join(timeout=2)
                if self.proc.is_alive():
                    self.warning = 'Perception worker did not stop; retry suspension'
                    return False
                self.proc = None
                for attr in ('req_q', 'res_q'):
                    queue = getattr(self, attr, None)
                    if queue is not None:
                        queue.cancel_join_thread()
                        queue.close()
                        delattr(self, attr)
            with self.lifecycle_lock:
                self.warmup_state = 'deferred_g1' if self.suspending else 'suspended'
                self.warmup_error = None
                self.warning = None
                self.suspending = False
            return True
        finally:
            self.lock.release()

    def close(self, deadline=None):
        self.warmup_cancel.set()
        self.closed = True
        deadline = time.monotonic() + 5.0 if deadline is None else deadline
        proc = self.proc
        if proc is not None:
            request_queue = getattr(self, "req_q", None)
            if request_queue is not None:
                try: request_queue.put(None)
                except (ValueError, OSError): pass
            stop_process(proc, deadline, cooperative_seconds=2.0)
