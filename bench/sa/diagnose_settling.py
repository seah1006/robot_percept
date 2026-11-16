"""[simGT] per-body settling root-cause diagnostic, no perception assistance."""
import json
import numpy as np
from sim.cell_scene_eval import open_evaluation_scene
import importlib.util
from sim.cell_scene import ROOT
import sim.cell_scene_eval as ce
module_spec=importlib.util.spec_from_file_location("sim._cell_before",ROOT/"bench/sa/cell_scene_before.py")
before=importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(before); ce._World=before._World
rows=[]
for seed in (100000,100009,100016,100017,100042,100048,100001,100002):
    e=open_evaluation_scene(seed); w=e._world
    objects=[]
    for item,spec in zip(w.plan['objects'],w.specs):
        j=w.model.joint(spec.name+'_free'); a=j.dofadr[0]; q=j.qposadr[0]
        objects.append({'class':item['class_id'],'id':spec.name,'v_m_s':w.data.qvel[a:a+3].tolist(),'omega_rad_s':w.data.qvel[a+3:a+6].tolist(),'quat':w.data.qpos[q+3:q+7].tolist()})
    rows.append({'seed':seed,'diagnostics':e.diagnostics(),'objects':objects}); e.close()
print(json.dumps(rows,indent=2))
