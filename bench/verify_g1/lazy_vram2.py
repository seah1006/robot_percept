"""V-G1: 워커 lazy import + 예외 주입 후 VRAM 원복 (워커 함수를 스레드로 직접 구동)"""
import sys, os, json, time, threading, queue, subprocess
sys.path.insert(0, '/home/user/work/robot_percept')
import numpy as np
from web import perception_stub as ps
from perception.interfaces import FrameMeta
def used(): return int(subprocess.getoutput('nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits'))
req, res = queue.Queue(), queue.Queue()
th = threading.Thread(target=ps._worker, args=(req, res, None), daemon=True); th.start()
print('ready', res.get(timeout=20))
heavy = ['torch', 'transformers', 'sam2', 'perception.fp_runner', 'perception.grounding', 'perception.sam_runner', 'cv2']
print('modules after ready:', {m: m in sys.modules for m in heavy})
def rpc(op, **a):
    i = op + str(time.time()); req.put((i, op, a)); r = res.get(timeout=120); return r[1], r[2]
meta = FrameMeta(frame_id='x', generation=0, source='sim_perception', capture_at=None, received_at=time.monotonic(), mirrored=False, calibration_id=None, width=640, height=480, overlay_present=False).to_dict()
rgb = np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8).tobytes()
q = [dict(query_id='a', canonical_class='box', phrase='blue box')]
ok, r = rpc('capabilities'); print('caps', ok, {k: r.get(k) for k in ('device', 'ops', 'fp_available', 'segmenter')}, 'peak_mb', r.get('peak_mb'))
print('modules after capabilities:', {m: m in sys.modules for m in heavy})
base = used(); print('GPU base', base)
ok, r = rpc('ground', schema_version=1, frame=meta, rgb=rgb, queries=q); warm = used()
print('ground ok', ok, 'err', r.get('error'), 'ndet', len(r.get('detections', [])), 'ms', round(r['ms']), 'peak_mb', r.get('peak_mb'), 'after', warm)
print('modules after ground:', {m: m in sys.modules for m in heavy})
# 예외 주입: OOM, 예외, 취소, deadline, 잘못된 입력
import perception.grounding as g
orig = g.Detector.detect
cases = {}
def inject(exc):
    def f(self, *a, **k):
        import torch
        self.ensure_detector(); x = torch.empty(64 * 2**20, device='cuda'); raise exc
    return f
for name, exc in [('oom', RuntimeError('CUDA out of memory')), ('internal', RuntimeError('boom'))]:
    g.Detector.detect = inject(exc)
    ok, r = rpc('ground', schema_version=1, frame=meta, rgb=rgb, queries=q)
    cases[name] = (ok, r.get('error') if isinstance(r, dict) else str(r)[-80:], used())
g.Detector.detect = orig
ok, r = rpc('ground', schema_version=1, frame=meta, rgb=rgb, queries=[]); cases['bad_queries'] = (ok, r.get('error') if isinstance(r, dict) else 'tb', used())
ok, r = rpc('ground', schema_version=1, frame=meta, rgb=rgb, queries=q, deadline=time.monotonic() - 1); cases['deadline'] = (ok, r.get('error'), used())
ok, r = rpc('ground', schema_version=1, frame=meta, rgb=rgb, queries=q, cancel_token=True); cases['cancel'] = (ok, r.get('error'), used())
ok, r = rpc('ground', schema_version=1, frame=meta, rgb=rgb, queries=q, schema_version_x=1); cases['ok_after'] = (ok, r.get('error'), used())
ok, r = rpc('nope'); cases['unsupported'] = (ok, r if isinstance(r, str) and False else (r.get('error') if isinstance(r, dict) else 'traceback:' + r.splitlines()[-1]), used())
ok, r = rpc('segment_box', schema_version=1, frame=meta, rgb=rgb, box_xyxy=[10, 10, 50, 60], segmenter='sam2'); cases['sam2_box'] = (ok, r.get('error') if isinstance(r, dict) else r.splitlines()[-1], used())
print(json.dumps(cases, ensure_ascii=False))
print('baseline', base, 'warm', warm, 'final', used())
import gc,torch
print("before gc",used(),"torch alloc MiB",torch.cuda.memory_allocated()/2**20)
gc.collect();torch.cuda.empty_cache()
print("after gc+empty_cache",used(),"torch alloc MiB",torch.cuda.memory_allocated()/2**20)
req.put(None)
