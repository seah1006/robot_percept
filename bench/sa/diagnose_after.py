"""[simGT] per-body settling root-cause diagnostic, no perception assistance."""
import json
import numpy as np
from sim.cell_scene_eval import open_evaluation_scene
rows=[]
for seed in (100003,100007,100042):
    e=open_evaluation_scene(seed); w=e._world
    objects=[]
    for item,spec in zip(w.plan['objects'],w.specs):
        j=w.model.joint(spec.name+'_free'); a=j.dofadr[0]; q=j.qposadr[0]
        objects.append({'class':item['class_id'],'id':spec.name,'v_m_s':w.data.qvel[a:a+3].tolist(),'omega_rad_s':w.data.qvel[a+3:a+6].tolist(),'quat':w.data.qpos[q+3:q+7].tolist()})
    rows.append({'seed':seed,'diagnostics':e.diagnostics(),'objects':objects}); e.close()
print(json.dumps(rows,indent=2))
