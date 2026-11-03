"""Reproducible CPU/render stage microbenchmark. Run with sim_test/gl_env.sh."""
import time,json,statistics
import numpy as np, cv2
from sim.env import SimEnv

def measure(fn,n=30):
    a=[]
    for _ in range(n):
        t=time.perf_counter();fn();a.append((time.perf_counter()-t)*1000)
    return {'mean_ms':statistics.mean(a),'p95_ms':float(np.percentile(a,95))}
e=SimEnv(objects=('mustard',),width=640,height=480,shadows=False,reflections=False,seed=7)
p=e.render_rgbd(); results={}
results['physics_step']=measure(lambda:e.step())
results['render_rgbd_seg']=measure(lambda:e.render_rgbd())
results['shm_copy_equivalent']=measure(lambda:tuple(x.copy() for x in p.values()))
results['color_jpeg80']=measure(lambda:cv2.imencode('.jpg',cv2.cvtColor(p['rgb'],cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,80]))
try:
    results['render_rgb_only']=measure(lambda:e.render_rgbd(depth=False,segmentation=False))
    results['render_rgb_depth']=measure(lambda:e.render_rgbd(segmentation=False))
except TypeError:pass
print(json.dumps(results,indent=2)); e.close()
