import numpy as np, sys
from PIL import Image
from sim import cell_scene as cs
out = []
for s in (100000, 100003, 1000, 100010, 100020, 100031):
    imgs = []
    for _ in range(3):
        c = cs.open_cell(s, 640, 480); imgs.append(c.capture()['rgb'].astype(int)); c.close()
    d = max(np.abs(imgs[0] - imgs[i]).max() for i in (1, 2)); n = max((np.abs(imgs[0] - imgs[i]).sum(2) > 0).sum() for i in (1, 2))
    out.append((s, int(d), int(n), cs.scene_plan(s)['scene_hash'][:8]))
    Image.fromarray(imgs[0].astype(np.uint8)).save(f'/home/user/work/robot_percept/bench/verify_sa/render_{s}.png')
for o in out: print('RGBDIFF seed=%d maxabs=%d diffpix=%d plan=%s' % o)
