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

def _worker(req,res,parent_pid=None):
    start_parent_pid_watch(parent_pid)
    import os
    target_nice = max(0, min(19, int(os.environ.get('RP_PERCEPTION_NICE', '10'))))
    try: os.nice(max(0, target_nice - os.nice(0)))
    except OSError: pass
    import torch
    cpu_threads = int(os.environ.get('RP_PERCEPTION_CPU_THREADS', '0'))
    if cpu_threads > 0:
        torch.set_num_threads(cpu_threads)
        try: torch.set_num_interop_threads(1)
        except RuntimeError: pass
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
                if self.mode != 'fp':
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
