"""Cell-only simulator. Perception capability exposes RGB, never GT."""
import json
import hashlib
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
from .objects import ROOT, ObjectSpec
from .scene_builder import build_scene, TABLE_TOP, HOME
VERSION='cell-r5-2'
ZONES={name:{'slots':[[.48,y],[.62,y]],'slot_size_m':[.12,.12], 'capacity':2,'layers':1} for name,y in [('left_box',-.36),('right_box',.36)]}
def catalog():
    return json.loads((ROOT/'config/objects.yaml').read_text())['objects']
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def scene_plan(seed):
    if not isinstance(seed,int) or isinstance(seed,bool) or seed<0: raise ValueError('invalid seed')
    rng=np.random.default_rng(seed); cat=catalog(); count=2+seed%3
    classes=rng.choice(list(cat),count,replace=False).tolist()
    if seed%5==0: classes[1]=classes[0]
    placed=[]; items=[]; rejected=0
    for i,cls in enumerate(classes):
        r=np.linalg.norm(cat[cls]['dimensions_m'][:2])/2
        for _ in range(1000):
            xy=rng.uniform([.40+r,-.24+r],[.72-r,.24-r])
            if all(np.linalg.norm(xy-p)>r+rr+.012 for p,rr in placed): break
            rejected+=1
        else: raise ValueError('placement exhausted; never silently omit')
        placed.append((xy,r)); items.append({'instance_id':f'cell_instance_{i}','class_id':cls,'xy_m':xy.tolist(),'yaw_rad':float(rng.uniform(-np.pi,np.pi))})
    p={'seed':seed,'generator_version':VERSION,'objects':items,'object_count':count,'distractor_count':count-1,'same_class_distractor':len(set(classes))<count,'occlusion':'unmeasured','rejected_placements':rejected,'source':'sim_gt','gt_assist':False,'identity_assist':False}
    p['scene_hash']=digest(p); return p
class CellCamera:
    """API capability boundary, not a hostile-code Python sandbox."""
    __slots__=('__capture','__close')
    def __init__(self,capture,close): self.__capture,self.__close=capture,close
    def capture(self): return {'rgb':self.__capture(),'source':'sim_perception','gt_assist':False,'identity_assist':False}
    def close(self): self.__close()
def open_cell(seed,width=320,height=240):
    w=_World(seed,width,height); return CellCamera(w.rgb,w.close)
class _World:
    """Private simulator backend, only evaluation module inspects GT."""
    def __init__(self,seed,width=320,height=240):
        self.plan=scene_plan(seed); cat=catalog(); self.specs=[]
        for item in self.plan['objects']:
            s=cat[item['class_id']]
            self.specs.append(ObjectSpec(item['instance_id'],str(ROOT/s['visual']),tuple(str(ROOT/p) for p in s['collision']),s['mass_kg'],tuple(s['rgba']),str(ROOT/s['texture']) if s.get('texture') else None,np.array(s['bounds_m'])))
        xml=ET.fromstring(build_scene(self.specs,width,height)); world=xml.find('worldbody')
        # Rubber-like ball: 6D contact includes physical rolling resistance.
        for item in self.plan["objects"]:
            policy=cat[item["class_id"]].get("contact_policy")
            if policy:
                for geom in xml.findall(".//body[@name='"+item["instance_id"]+"']/geom"):
                    if geom.get("group") == "3":
                        geom.set("condim",str(policy["condim"]))
                        geom.set("friction",f"{policy['sliding_friction']} {policy['torsional_friction_m']} {policy['rolling_friction_m']}")
                        geom.set("priority","1")
        xml.find('.//geom[@name="table_top"]').set('size','.30 .46 .15')
        # Matte rubber tabletop provides rolling/torsional resistance for
        # irregular source-mesh bottle bases as well as spherical surrogates.
        table_geom=xml.find(".//geom[@name='table_top']")
        table_geom.set("condim","6"); table_geom.set("friction",".8 .01 .002")
        for name,z in ZONES.items():
            for j,xy in enumerate(z['slots']):
                ET.SubElement(world,'geom',name=f'{name}_slot_{j}',type='box',pos=f'{xy[0]} {xy[1]} .3002',size='.06 .06 .0002',rgba='.25 .25 .25 1' if name=='left_box' else '.8 .8 .8 1',contype='0',conaffinity='0')
        for j,(pos,size) in enumerate([('.40 0 .3002','.001 .24 .0002'),('.72 0 .3002','.001 .24 .0002'),('.56 -.24 .3002','.16 .001 .0002'),('.56 .24 .3002','.16 .001 .0002')]):
            ET.SubElement(world,'geom',name=f'tray_edge_{j}',type='box',pos=pos,size=size,rgba='.9 .8 .1 1',contype='0',conaffinity='0')
        self.model=mujoco.MjModel.from_xml_string(ET.tostring(xml,encoding='unicode')); self.data=mujoco.MjData(self.model)
        for i in range(7):
            self.data.qpos[self.model.joint(f'joint{i+1}').qposadr[0]]=HOME[i]; self.data.ctrl[i]=HOME[i]
        for n in ('finger_joint1','finger_joint2'): self.data.qpos[self.model.joint(n).qposadr[0]]=.04
        self.data.ctrl[7]=255
        for item,spec in zip(self.plan['objects'],self.specs):
            a=self.model.joint(spec.name+'_free').qposadr[0]; yaw=item['yaw_rad']; c,s=np.cos(yaw),np.sin(yaw)
            xy=np.array(item['xy_m'])-np.array([[c,-s],[s,c]])@spec.bounds[:,:2].mean(0)
            self.data.qpos[a:a+3]=[*xy,TABLE_TOP-spec.bounds[0,2]+.002]; self.data.qpos[a+3:a+7]=[np.cos(yaw/2),0,0,np.sin(yaw/2)]
        mujoco.mj_forward(self.model,self.data)
        dofs=[self.model.joint(f'joint{i+1}').dofadr[0] for i in range(7)]
        stable=0; self.settle_steps=0
        # Require a genuine quiet interval, not a single fixed-time snapshot.
        for step in range(2000):
            self.data.qfrc_applied[dofs]=self.data.qfrc_bias[dofs]; mujoco.mj_step(self.model,self.data)
            self.settle_steps=step+1
            stable=stable+1 if np.max(np.abs(self.data.qvel))<.003 else 0
            if step>=499 and stable>=100: break
        self.settle_converged=stable>=100
        mujoco.mj_forward(self.model,self.data); self.width,self.height=width,height; self.renderer=None
    def rgb(self):
        if self.renderer is None: self.renderer=mujoco.Renderer(self.model,height=self.height,width=self.width)
        opt=mujoco.MjvOption(); opt.geomgroup[3]=0
        self.renderer.update_scene(self.data,camera='front',scene_option=opt); rgb=self.renderer.render().copy(); rgb.setflags(write=False); return rgb
    def close(self):
        if self.renderer is not None: self.renderer.close(); self.renderer=None
