import sys, numpy as np, inspect
sys.path.insert(0, '/home/user/work/robot_percept')
from perception.interfaces import FrameMeta
from perception.segment import Segmenter
print(inspect.signature(FrameMeta))
import time
m = FrameMeta(frame_id='f', generation=1, source='sim', capture_at=None, received_at=time.time(), mirrored=False,
              calibration_id=None, width=8, height=6, overlay_present=False)
class F: pass
f = F(); f.meta = m; f.rgb = bytes(8*6*3)
r = Segmenter('off').segment(f, (1, 2, 4, 5))
exp = np.zeros((6, 8), bool); exp[2:5, 1:4] = True
def dec(counts, order):
    v = False; out = []
    for c in counts:
        out += [v]*c; v = not v
    return np.array(out).reshape((6, 8), order=order)
print('counts', r.counts)
print('row-major decode ok', np.array_equal(dec(r.counts, 'C'), exp))
print('col-major decode ok', np.array_equal(dec(r.counts, 'F').reshape(6, 8) if False else np.array(dec(r.counts,'C')).ravel().reshape(8, 6).T if False else dec(r.counts, 'F'), exp))
