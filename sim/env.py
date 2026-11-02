"""Panda RGB-D environment. Original mesh origins and OpenCV camera frames."""
import numpy as np
import mujoco
import cv2
from .objects import default_registry,mesh_spec
from .scene_builder import build_scene,HOME,TABLE_TOP
class SimEnv:
    def __init__(self,objects=('mustard',),width=640,height=480,cam='front',shadows=False,reflections=False,seed=0):
        self.width,self.height,self.cam=int(width),int(height),cam
        self.shadows,self.reflections=shadows,reflections
        self.rng=np.random.default_rng(seed)
        self.registry=default_registry()
        self.object_names=list(objects)
        if len(set(self.object_names))!=len(self.object_names): raise ValueError('Duplicate object names')
        self.object_ids={n:i for i,n in enumerate(self.object_names)}
        self._renderer=None; self._dirty=True
        self.reset(seed)
    def _compile(self):
        self.close()
        self.model=mujoco.MjModel.from_xml_string(build_scene([self.registry[n] for n in self.object_names],self.width,self.height))
        self.data=mujoco.MjData(self.model)
        self._qadr=np.array([self.model.joint(f'joint{i}').qposadr[0] for i in range(1,8)])
        self._dadr=np.array([self.model.joint(f'joint{i}').dofadr[0] for i in range(1,8)])
        self._act=np.array([self.model.actuator(f'actuator{i}').id for i in range(1,8)])
        self._geom_objects=np.full(self.model.ngeom,-1,np.int32)
        for name,oid in self.object_ids.items(): self._geom_objects[self.model.geom_bodyid==self.model.body(name).id]=oid
        self._dirty=False
    def reset(self,seed=None,randomize=True):
        if seed is not None: self.rng=np.random.default_rng(seed)
        if self._dirty: self._compile()
        mujoco.mj_resetData(self.model,self.data)
        self.data.qpos[self._qadr]=HOME
        self.set_arm_target(HOME); self.set_gripper(.08)
        for n in ('finger_joint1','finger_joint2'): self.data.qpos[self.model.joint(n).qposadr[0]]=.04
        placed=[]
        for i,name in enumerate(self.object_names):
            s=self.registry[name]
            radius=np.linalg.norm(s.bounds[1,:2]-s.bounds[0,:2])*.5
            center=s.bounds[:,:2].mean(0)
            yaw=self.rng.uniform(-np.pi,np.pi) if randomize else 0.
            R=np.array([[np.cos(yaw),-np.sin(yaw)],[np.sin(yaw),np.cos(yaw)]])
            for _ in range(300):
                xy=self.rng.uniform([.45,-.23],[.66,.23]) if randomize else np.array([.55,(i-(len(self.object_names)-1)/2)*.15])
                if all(np.linalg.norm(xy-p)>radius+r+.025 for p,r in placed): break
            else: raise ValueError('Too many/large objects for non-overlapping workspace')
            placed.append((xy,radius))
            adr=self.model.joint(name+'_free').qposadr[0]
            self.data.qpos[adr:adr+3]=[*(xy-R@center),TABLE_TOP-s.bounds[0,2]+.006]
            self.data.qpos[adr+3:adr+7]=[np.cos(yaw/2),0,0,np.sin(yaw/2)]
        mujoco.mj_forward(self.model,self.data)
        self.settle_steps=0
        for k in range(1500):
            self.step(); self.settle_steps=k+1
            if k>=250 and np.max(np.abs(self.data.qvel),initial=0)<1e-3: break
        mujoco.mj_forward(self.model,self.data)
    def step(self,n=1):
        for _ in range(n):
            self.data.qfrc_applied[self._dadr]=self.data.qfrc_bias[self._dadr]
            mujoco.mj_step(self.model,self.data)
        mujoco.mj_forward(self.model,self.data)
    def render_rgbd(self,cam=None,*,depth=True,segmentation=True):
        """Default RGB-D + segmentation contract is unchanged; optional passes save readbacks."""
        cam=self.cam if cam is None else cam
        if self._renderer is None:
            self._renderer=mujoco.Renderer(self.model,height=self.height,width=self.width)
            self._renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW]=self.shadows
            self._renderer.scene.flags[mujoco.mjtRndFlag.mjRND_REFLECTION]=self.reflections
        r=self._renderer
        opt=mujoco.MjvOption(); opt.geomgroup[3]=0
        r.disable_depth_rendering(); r.disable_segmentation_rendering()
        r.update_scene(self.data,camera=cam,scene_option=opt); rgb=r.render().copy()
        out={'rgb':rgb}
        if depth:
            r.enable_depth_rendering(); r.update_scene(self.data,camera=cam,scene_option=opt)
            d=r.render().astype(np.float32,copy=True)
            r.disable_depth_rendering()
            far=self.model.vis.map.zfar*self.model.stat.extent
            d[(~np.isfinite(d)) | (d<=0) | (d>=.99*far)]=0
            out['depth']=d
        if segmentation:
            r.enable_segmentation_rendering(); r.update_scene(self.data,camera=cam,scene_option=opt); raw=r.render().copy()
            r.disable_segmentation_rendering()
            seg=np.full((self.height,self.width),-1,np.int32)
            valid=(raw[...,1]==int(mujoco.mjtObj.mjOBJ_GEOM)) & (raw[...,0]>=0)
            seg[valid]=self._geom_objects[raw[...,0][valid]]
            out['seg']=seg
        if depth:
            kernel=np.ones((3,3),np.uint8)
            edge=(cv2.dilate(d,kernel)-cv2.erode(d,kernel))>.02
            if segmentation:
                for oid in self.object_ids.values():
                    edge |= cv2.morphologyEx((seg==oid).astype(np.uint8),cv2.MORPH_GRADIENT,kernel).astype(bool)
            d[edge]=0
        return out
    def object_mask(self,name,cam=None): return self.render_rgbd(cam)['seg']==self.object_ids[name]
    def camera_K(self,cam=None):
        cid=self.model.camera(self.cam if cam is None else cam).id
        f=.5*self.height/np.tan(np.deg2rad(self.model.cam_fovy[cid])*.5)
        return np.array([[f,0,(self.width-1)/2],[0,f,(self.height-1)/2],[0,0,1]],np.float64)
    def T_world_cam(self,cam=None):
        cid=self.model.camera(self.cam if cam is None else cam).id
        T=np.eye(4); T[:3,:3]=self.data.cam_xmat[cid].reshape(3,3)@np.diag([1.,-1.,-1.]); T[:3,3]=self.data.cam_xpos[cid]
        return T
    def T_world_obj(self,name):
        bid=self.model.body(name).id
        T=np.eye(4); T[:3,:3]=self.data.xmat[bid].reshape(3,3); T[:3,3]=self.data.xpos[bid]
        return T
    def T_cam_obj(self,name,cam=None): return np.linalg.inv(self.T_world_cam(cam))@self.T_world_obj(name)
    def object_mesh_path(self,name): return self.registry[name].visual_obj
    def arm_qpos(self): return self.data.qpos[self._qadr].copy()
    def set_arm_target(self,q7):
        q=np.asarray(q7,float)
        if q.shape!=(7,) or not np.isfinite(q).all(): raise ValueError('Expected seven finite positions')
        limits=self.model.actuator_ctrlrange[self._act]
        if np.any(q<limits[:,0]) or np.any(q>limits[:,1]): raise ValueError('Arm target outside joint limits')
        self.data.ctrl[self._act]=q
    def set_gripper(self,width_m):
        if not np.isfinite(width_m) or not 0<=width_m<=.08: raise ValueError('Width must be in [0,.08] metres')
        self.data.ctrl[self.model.actuator('actuator8').id]=width_m/.08*255
    def ee_pose(self):
        sid=self.model.site('tcp').id
        T=np.eye(4); T[:3,:3]=self.data.site_xmat[sid].reshape(3,3); T[:3,3]=self.data.site_xpos[sid]
        return T
    def add_object_from_mesh(self,name,visual_obj,collision_objs,mass=.1,rgba=None):
        self.registry[name]=mesh_spec(name,visual_obj,collision_objs,mass,rgba)
        if name not in self.object_names: self.object_names.append(name)
        self.object_ids={n:i for i,n in enumerate(self.object_names)}
        self._dirty=True
    def close(self):
        if self._renderer is not None: self._renderer.close(); self._renderer=None
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
