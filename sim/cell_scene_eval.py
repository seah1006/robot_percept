"""Evaluation-only GT. Must not be imported by perception or selection."""
import numpy as np
import trimesh
from .cell_scene import _World, ROOT, VERSION, scene_plan, digest
from .grasp import world_aabb
class EvaluationScene:
    def __init__(self,seed,width=320,height=240): self._world=_World(seed,width,height)
    def rgb(self): return self._world.rgb()
    def close(self): self._world.close()
    def ground_truth(self):
        w=self._world; rows=[]
        for item,spec in zip(w.plan['objects'],w.specs):
            bid=w.model.body(spec.name).id; T=np.eye(4); T[:3,:3]=w.data.xmat[bid].reshape(3,3); T[:3,3]=w.data.xpos[bid]
            lo,hi,_=world_aabb(T,spec.bounds)
            vertices=np.asarray(trimesh.load(spec.visual_obj,force="mesh",process=False).vertices)@T[:3,:3].T+T[:3,3]; lo=vertices.min(0); hi=vertices.max(0)
            rows.append({**item,'T_world_obj':T.tolist(),'aabb_m':[lo.tolist(),hi.tolist()],'bottom_gap_m':float(lo[2]-.30)})
        return rows
    def diagnostics(self):
        w=self._world; pairs=[]
        linear=[]; angular=[]
        for spec in w.specs:
            a=w.model.joint(spec.name+"_free").dofadr[0]
            linear.append(float(np.max(np.abs(w.data.qvel[a:a+3]))))
            angular.append(float(np.max(np.abs(w.data.qvel[a+3:a+6]))))
        for c in w.data.contact:
            names=[w.model.body(w.model.geom_bodyid[g]).name for g in (c.geom1,c.geom2)]
            if all(n.startswith('cell_instance_') for n in names): pairs.append(c.dist)
        return {'max_linear_speed_m_s':max(linear),'max_angular_speed_rad_s':max(angular),'settle_steps':getattr(w,'settle_steps',500),'settle_converged':getattr(w,'settle_converged',False),'interobject_contacts':len(pairs),'interobject_penetrations':sum(d<0 for d in pairs),'max_bottom_gap_m':max(abs(r['bottom_gap_m']) for r in self.ground_truth()),'max_speed':float(np.max(np.abs(w.data.qvel)))}
def open_evaluation_scene(seed,width=320,height=240): return EvaluationScene(seed,width,height)
def generate_manifest():
    sets={}
    for name,start,n in [('tuning',1000,20),('evaluation',100000,100)]:
        sets[name]=[{k:v for k,v in scene_plan(seed).items() if k!='objects'} for seed in range(start,start+n)]
    return {'generator_version':VERSION,'seed_split_hash':digest({k:[x['seed'] for x in v] for k,v in sets.items()}),'config_hashes':{p:digest((ROOT/p).read_text()) for p in ['config/objects.yaml','config/vocab_ko_en.yaml']},'sets':sets}
