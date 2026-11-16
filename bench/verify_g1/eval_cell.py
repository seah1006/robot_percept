"""V-G1 독립 셀 eval: 시뮬 장면 -> Grounding DINO(GT 보조 없음) -> GT 가시 박스 IoU>=0.5 같은 클래스 greedy.
GT는 검출 후 평가에서만 사용. 출력 bench/verify_g1/eval_out_tune_nomsaa.json"""
import sys, os, json, time, subprocess, threading, yaml
import numpy as np
sys.path.insert(0, '/home/user/work/robot_percept')
import mujoco
from sim.cell_scene_eval import open_evaluation_scene
from perception.grounding import Detector
from perception.interfaces import Frame, FrameMeta
import torch

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
START = int(os.environ.get("VG1_START", "1000"))
vocab = json.loads(open('/home/user/work/robot_percept/config/vocab_ko_en.yaml').read())['phrases']
queries = [dict(query_id=c, canonical_class=c, phrase=p) for c, p in vocab.items()]

def vis_boxes(es):
    w = es._world; w.model.vis.quality.offsamples = 0; r = mujoco.Renderer(w.model, w.height, w.width)
    opt = mujoco.MjvOption(); opt.geomgroup[3] = 0
    r.enable_segmentation_rendering()
    r.update_scene(w.data, camera='front', scene_option=opt); seg = r.render().copy()
    r.disable_segmentation_rendering(); r.close()
    gid = seg[..., 0]; typ = seg[..., 1]
    out = {}
    for item in w.plan['objects']:
        bid = w.model.body(item['instance_id']).id
        geoms = [g for g in range(w.model.ngeom) if w.model.geom_bodyid[g] == bid]
        m = np.isin(gid, geoms) & (typ == int(mujoco.mjtObj.mjOBJ_GEOM))
        if m.any():
            ys, xs = np.where(m)
            out[item['instance_id']] = (item['class_id'], [xs.min(), ys.min(), xs.max() + 1, ys.max() + 1], int(m.sum()))
    return out

def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy; u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i
    return i / u if u else 0

def score(dets, gt):
    used = set(); tp = 0
    for d in sorted(dets, key=lambda d: -d.score):
        best = None; bi = 0
        for k, (cls, box, area) in gt.items():
            if k in used or cls != d.canonical_class: continue
            v = iou(d.box_xyxy, box)
            if v >= .5 and v > bi: best, bi = k, v
        if best: used.add(best); tp += 1
    return tp, len(dets) - tp

peak = [0]; stop = threading.Event()
def sampler():
    while not stop.is_set():
        try: peak[0] = max(peak[0], int(subprocess.getoutput('nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits')))
        except Exception: pass
        time.sleep(.1)
threading.Thread(target=sampler, daemon=True).start()
load0 = os.getloadavg()
res = dict(source='[시뮬인식]', gt_assist=False, identity_assist=False, queries='9 vocab phrases (GT 장면 구성 무관, 고정 사전)', scenes=[], load_start=load0)
det = Detector()
agg = {True: [0, 0, 0], False: [0, 0, 0]}  # gt, tp, fp
lat = []
t_start = time.time()
for s in range(START, START + N):
    es = open_evaluation_scene(s, 640, 480)
    rgb = es.rgb(); gt = vis_boxes(es); es.close()
    meta = FrameMeta(frame_id=str(s), generation=0, source='sim_perception', capture_at=None, received_at=time.monotonic(), mirrored=False, calibration_id=None, width=640, height=480, overlay_present=False)
    fr = Frame(meta, rgb.tobytes())
    row = dict(seed=s, gt={k: v[0] for k, v in gt.items()}, gt_area_px={k: v[2] for k, v in gt.items()})
    for filt in (True, False):
        t = time.perf_counter(); d = det.detect(fr, queries, .35, .25, filt); ms = (time.perf_counter() - t) * 1000
        tp, fp = score(d, gt)
        agg[filt][0] += len(gt); agg[filt][1] += tp; agg[filt][2] += fp
        row['filter_%s' % filt] = dict(ms=ms, tp=tp, fp=fp, ndet=len(d), rej=[x['reason'] for x in det.rejections])
        if filt: lat.append(ms)
    res['scenes'].append(row)
    if time.time() - t_start > 200: break
stop.set()
for f in (True, False):
    g, tp, fp = agg[f]
    res['filter_%s' % f] = dict(gt=g, tp=tp, fp=fp, recall=tp / g if g else None, precision=tp / (tp + fp) if tp + fp else None)
res['latency_ms_filtered'] = dict(all=lat, warm_p50=float(np.percentile(lat[1:], 50)) if len(lat) > 1 else None, first=lat[0])
res['n_scenes'] = len(res['scenes']); res['device_used_peak_sampled_mib'] = peak[0]
res['load_end'] = os.getloadavg(); res['proc_max_alloc_mib'] = torch.cuda.max_memory_allocated() / 2**20
# blue case (G0 image): single-box prompts
from PIL import Image
img = Image.open('/home/user/work/robot_percept/sim_test/results/egl_d3d12/rgb.png').convert('RGB')
m2 = FrameMeta(frame_id='g0', generation=0, source='sim_perception', capture_at=None, received_at=time.monotonic(), mirrored=False, calibration_id=None, width=img.width, height=img.height, overlay_present=False)
f2 = Frame(m2, img.tobytes())
blue = {}
for name, qs in {'red+blue': [dict(query_id='r', canonical_class='red', phrase='a red cube'), dict(query_id='b', canonical_class='blue', phrase='a blue cube')],
                 'blue_only': [dict(query_id='b', canonical_class='blue', phrase='a blue cube')]}.items():
    for filt in (True, False):
        d = det.detect(f2, qs, .35, .25, filt)
        blue['%s/filter=%s' % (name, filt)] = dict(size=img.size, dets=[(x.canonical_class, round(x.score, 3), [round(v, 1) for v in x.box_xyxy], round((x.box_xyxy[2]-x.box_xyxy[0])*(x.box_xyxy[3]-x.box_xyxy[1])/(img.width*img.height), 3)) for x in d], rej=det.rejections)
res['blue_case'] = blue
json.dump(res, open('/home/user/work/robot_percept/bench/verify_g1/eval_out_tune_nomsaa.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k != 'scenes'}, ensure_ascii=False, default=str)[:4000])
