source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
python - <<'PY'
import numpy as np,cv2,mujoco,textwrap,json
from pathlib import Path
from sim.env import SimEnv
s=Path('data/backup_fps/sim/env.py').read_text();a=s.index('    def render_rgbd(');b=s.index('    def object_mask',a)
d={'np':np,'cv2':cv2,'mujoco':mujoco};exec(textwrap.dedent(s[a:b]),d)
e=SimEnv(objects=('mustard',),seed=7,shadows=False,reflections=False)
p=d['render_rgbd'](e);q=e.render_rgbd()
r={k:{'max_abs_diff':float(np.abs(p[k].astype(float)-q[k].astype(float)).max()),'unequal':int(np.count_nonzero(p[k]!=q[k]))} for k in p}
print(json.dumps(r,indent=2));Path('bench/impl/render_equivalence.json').write_text(json.dumps(r,indent=2));e.close()
PY