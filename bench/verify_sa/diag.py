import sys, hashlib
from sim import cell_scene_eval as ce
s = int(sys.argv[1]); w = ce.open_evaluation_scene(s); W = w._world
qh = hashlib.sha256(W.data.qpos.tobytes()).hexdigest()[:12]
r1 = hashlib.sha256(w.rgb().tobytes()).hexdigest()[:12]
r2 = hashlib.sha256(w.rgb().tobytes()).hexdigest()[:12]
print(s, 'qpos', qh, 'rgb', r1, r2, [o['class_id'] for o in W.plan['objects']])
