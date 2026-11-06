#!/bin/bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate robot_percept
cd ~/work/robot_percept
git -C assets/mujoco_menagerie checkout -q f3b6013 && git -C assets/mujoco_menagerie log --oneline -1
git status --short | head
sed -i 's/MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA/MESA_D3D12_DEFAULT_ADAPTER_NAME=AMD/; s/RTX 2080 SUPER/AMD Radeon RX 7600 (home)/' sim_test/gl_env.sh
cat sim_test/gl_env.sh
source sim_test/gl_env.sh
export HOST=0.0.0.0 PYTHONPATH=$PWD
python - <<'EOF'
import mujoco, time
m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><light pos="0 0 3"/><geom type="sphere" size=".1"/></worldbody></mujoco>')
d = mujoco.MjData(m)
r = mujoco.Renderer(m, 480, 640)
mujoco.mj_forward(m, d)
r.update_scene(d); r.render()
from OpenGL import GL
print('GL_RENDERER', GL.glGetString(GL.GL_RENDERER))
t=time.perf_counter()
for _ in range(50): r.update_scene(d); r.render()
print('render ms', (time.perf_counter()-t)/50*1000)
EOF
nproc; uptime
time python -m pytest -q 2>&1 | tail -15
