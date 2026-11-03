#!/usr/bin/env python3
"""Export MuJoCo RGB-D sequences in FoundationPose demo-data format."""
from __future__ import annotations
import argparse, json, math, shutil, tempfile, time
from pathlib import Path
import cv2
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MESH = ROOT / "downloads/demo_data/mustard0/mesh/textured_simple.obj"


def _mesh_vertices(path):
    verts = []
    with Path(path).open("r", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                p = line.split(); verts.append([float(p[1]), float(p[2]), float(p[3])])
    if not verts: raise ValueError(f"No vertices in {path}")
    return np.asarray(verts, np.float64)


def _look_at_quat(position, target):
    z_back = position-target; z_back /= np.linalg.norm(z_back)
    x_right = np.cross([0.,0.,1.], z_back)
    if np.linalg.norm(x_right)<1e-8: x_right=np.array([1.,0.,0.])
    x_right /= np.linalg.norm(x_right); y_up=np.cross(z_back,x_right)
    q=np.empty(4); mujoco.mju_mat2Quat(q,np.column_stack((x_right,y_up,z_back)).ravel()); return q


class FallbackEnv:
    """Self-contained real-mesh adapter used until sim.env.SimEnv is available."""
    def __init__(self, objects=("mustard",), width=640, height=480, cam="rgbd", shadows=False, reflections=False, seed=0):
        if tuple(objects)!=("mustard",): raise ValueError("Fallback supports only mustard")
        self.width,self.height,self.cam=width,height,cam; self.mesh_path=DEFAULT_MESH.resolve()
        vv=_mesh_vertices(self.mesh_path); start_z=0.3005-float(vv[:,2].min())
        panda=(ROOT/"sim_test/panda_mod.xml").resolve(); tex=(self.mesh_path.parent/"texture_map.png").resolve()
        xml=f'''<mujoco model="fp mustard fallback">
<include file="{panda}"/><statistic center="0.5 0 0.45" extent="1.2"/><option timestep="0.002"/>
<visual><headlight diffuse="0.7 0.7 0.7" ambient="0.35 0.35 0.35" specular="0 0 0"/><map znear="0.01" zfar="4"/><global offwidth="640" offheight="480"/></visual>
<asset><texture name="mustard_tex" type="2d" file="{tex}"/><material name="mustard_mat" texture="mustard_tex"/><mesh name="mustard_mesh" file="{self.mesh_path}"/><material name="table" rgba="0.55 0.4 0.25 1"/></asset>
<worldbody><light pos="0 0 1.6" dir="0 0 -1" directional="true"/><geom name="floor" size="0 0 0.05" type="plane" rgba="0.2 0.25 0.3 1"/><body name="table" pos="0.55 0 0.15"><geom name="table_top" type="box" size="0.30 0.42 0.15" material="table"/></body>
<body name="mustard" pos="0.55 0.05 {start_z:.9f}"><freejoint name="mustard_free"/><geom name="mustard_geom" type="mesh" mesh="mustard_mesh" material="mustard_mat" mass="0.15" group="1"/></body>
<camera name="rgbd" mode="fixed" pos="1.35 0 0.95" xyaxes="0 1 0 -0.630593 0 0.776114" fovy="58"/></worldbody>
<keyframe><key name="home" qpos="0 0 0 -1.57079 0 1.57079 -0.7853 0.04 0.04 0.55 0.05 {start_z:.9f} 1 0 0 0" ctrl="0 0 0 -1.57079 0 1.57079 -0.7853 255"/></keyframe></mujoco>'''
        self._tmp=tempfile.TemporaryDirectory(prefix="fp_mj_"); xp=Path(self._tmp.name)/"scene.xml"; xp.write_text(xml)
        self.model=mujoco.MjModel.from_xml_path(str(xp)); self.data=mujoco.MjData(self.model); self.renderer=mujoco.Renderer(self.model,height,width)
        if not shadows: self.renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW]=False
        if not reflections: self.renderer.scene.flags[mujoco.mjtRndFlag.mjRND_REFLECTION]=False
        self.reset(seed,False)
    def reset(self,seed=None,randomize=True):
        mujoco.mj_resetDataKeyframe(self.model,self.data,self.model.key("home").id)
        if randomize:
            rng=np.random.default_rng(seed); adr=self.model.jnt_qposadr[self.model.joint("mustard_free").id]
            self.data.qpos[adr:adr+2]+=rng.uniform(-.025,.025,2); yaw=rng.uniform(-.25,.25); self.data.qpos[adr+3:adr+7]=[math.cos(yaw/2),0,0,math.sin(yaw/2)]
        for _ in range(250): mujoco.mj_step(self.model,self.data)
        mujoco.mj_forward(self.model,self.data)
    def step(self,n=1):
        for _ in range(n):
            self.data.qfrc_applied[:min(7,self.model.nv)]=self.data.qfrc_bias[:min(7,self.model.nv)]; mujoco.mj_step(self.model,self.data)
    def render_rgbd(self,cam=None):
        cam=cam or self.cam; r=self.renderer; r.disable_depth_rendering(); r.disable_segmentation_rendering(); r.update_scene(self.data,camera=cam); rgb=r.render().copy()
        r.enable_depth_rendering(); r.update_scene(self.data,camera=cam); depth=r.render().copy().astype(np.float32); r.disable_depth_rendering()
        r.enable_segmentation_rendering(); r.update_scene(self.data,camera=cam); raw=r.render().copy(); r.disable_segmentation_rendering()
        seg=np.full(raw.shape[:2],-1,np.int32); ok=raw[...,1]==int(mujoco.mjtObj.mjOBJ_GEOM); seg[ok]=raw[...,0][ok]
        far=self.model.vis.map.zfar*self.model.stat.extent; depth[(~np.isfinite(depth))|(depth>=.99*far)]=0
        return {"rgb":rgb,"depth":depth,"seg":seg}
    def object_mask(self,name,cam=None): return self.render_rgbd(cam)["seg"]==self.model.geom("mustard_geom").id
    def camera_K(self,cam=None):
        cid=self.model.camera(cam or self.cam).id; f=.5*self.height/np.tan(np.deg2rad(self.model.cam_fovy[cid])/2)
        return np.array([[f,0,(self.width-1)/2],[0,f,(self.height-1)/2],[0,0,1]],float)
    def T_world_cam(self,cam=None):
        cid=self.model.camera(cam or self.cam).id; T=np.eye(4); T[:3,:3]=self.data.cam_xmat[cid].reshape(3,3)@np.diag([1.,-1.,-1.]); T[:3,3]=self.data.cam_xpos[cid]; return T
    def T_world_obj(self,name):
        bid=self.model.body("mustard").id; T=np.eye(4); T[:3,:3]=self.data.xmat[bid].reshape(3,3); T[:3,3]=self.data.xpos[bid]; return T
    def T_cam_obj(self,name,cam=None): return np.linalg.inv(self.T_world_cam(cam))@self.T_world_obj(name)
    def object_mesh_path(self,name): return str(self.mesh_path)
    def set_arm_target(self,q7): self.data.ctrl[:7]=q7


def _create_env(objects,width,height,seed):
    try:
        from sim.env import SimEnv
        env=SimEnv(objects=tuple(objects),width=width,height=height,seed=seed,shadows=False,reflections=False); env.reset(seed=seed,randomize=False)
        return env,"SimEnv"
    except (ImportError,ModuleNotFoundError) as exc:
        print(f"sim.env unavailable ({exc}); using fallback adapter")
        return FallbackEnv(tuple(objects),width,height,seed=seed),"fallback"


def _body_id(env,name="mustard"):
    for candidate in (name,"obj",f"object_{name}"):
        try: return env.model.body(candidate).id
        except KeyError: pass
    raise KeyError(f"Cannot locate body for {name}")


def _object_geom_ids(env,name="mustard"):
    bid=_body_id(env,name); ids=[]
    for gid,gbid in enumerate(env.model.geom_bodyid):
        b=int(gbid)
        while b>0 and b!=bid: b=int(env.model.body_parentid[b])
        if b==bid: ids.append(gid)
    return ids


def _apply_motion(env,motion,frame,frames,initial_cam):
    phase=frame/max(frames-1,1)
    if motion=="push_object":
        bid=_body_id(env); env.data.xfrc_applied[bid]=0
        if .12<=phase<=.16: env.data.xfrc_applied[bid,:3]=[0.,-1.4,0.]
        env.step(8)
    elif motion=="robot_move":
        q=np.array([0,0,0,-1.57079,0,1.57079,-.7853],float)+np.array([.18*math.sin(2*math.pi*phase),-.12*math.sin(math.pi*phase),.12*math.sin(2*math.pi*phase),-.18*math.sin(math.pi*phase),.1*math.sin(2*math.pi*phase),.12*math.sin(math.pi*phase),.2*math.sin(2*math.pi*phase)])
        env.set_arm_target(q); env.step(8)
    elif motion=="orbit_camera":
        if initial_cam is None: raise RuntimeError("orbit_camera requires model camera")
        cam=getattr(env,"cam","front"); cid=env.model.camera(cam).id; center,base=initial_cam; angle=math.radians(-25+50*phase); radius=np.linalg.norm(base[:2]-center[:2]); pos=np.array([center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle),base[2]])
        env.model.cam_pos[cid]=pos; env.model.cam_quat[cid]=_look_at_quat(pos,center); mujoco.mj_forward(env.model,env.data)
    else: env.step(1)


def _copy_mesh_bundle(mesh_path,out):
    dst=out/"mesh"; dst.mkdir(parents=True,exist_ok=True)
    for p in mesh_path.parent.iterdir():
        if p.is_file() and p.suffix.lower() in {".obj",".mtl",".png",".jpg",".jpeg"}: shutil.copy2(p,dst/p.name)


def _mesh_only_depth(env,name,cam,h,w):
    all_gids=_object_geom_ids(env,name); old=env.model.geom_group.copy(); gids=[g for g in all_gids if old[g]!=3]; env.model.geom_group[gids]=5
    r=mujoco.Renderer(env.model,h,w); opt=mujoco.MjvOption(); opt.geomgroup[:]=0; opt.geomgroup[5]=1
    r.enable_depth_rendering(); r.update_scene(env.data,camera=cam,scene_option=opt); z=r.render().copy(); r.close(); env.model.geom_group[:]=old
    far=env.model.vis.map.zfar*env.model.stat.extent; z[(~np.isfinite(z))|(z>=.99*far)]=0; return z


def _overlay(rgb,vertices,T,K):
    p=(T[:3,:3]@vertices.T).T+T[:3,3]; p=p[p[:,2]>1e-4]; uv=(K@p.T).T; uv=uv[:,:2]/uv[:,2:3]; out=rgb.copy()
    for u,v in uv[::max(1,len(uv)//2500)]:
        x,y=int(round(u)),int(round(v))
        if 0<=x<out.shape[1] and 0<=y<out.shape[0]: cv2.circle(out,(x,y),1,(0,255,0),-1)
    return out


def export(args):
    objects=[x.strip() for x in args.objects.split(",") if x.strip()]
    if objects!=["mustard"]: raise ValueError("Phase-1 supports --objects mustard")
    out=Path(args.out).expanduser().resolve()
    if out.exists(): shutil.rmtree(out)
    for sub in ("rgb","depth","masks","ob_in_cam"): (out/sub).mkdir(parents=True,exist_ok=True)
    env,backend=_create_env(objects,args.width,args.height,args.seed); cam=getattr(env,"cam",None); K=np.asarray(env.camera_K(cam),float); np.savetxt(out/"cam_K.txt",K,fmt="%.10g")
    mesh_path=Path(env.object_mesh_path("mustard")); _copy_mesh_bundle(mesh_path,out); vertices=_mesh_vertices(mesh_path)
    center=np.asarray(env.T_world_obj("mustard")[:3,3],float)
    try:
        cid=env.model.camera(cam).id; initial_cam=(center.copy(),env.model.cam_pos[cid].copy())
    except Exception: initial_cam=None
    poses_wc=[]; depth_check=None; t0=time.perf_counter()
    for i in range(args.frames):
        _apply_motion(env,args.motion,i,args.frames,initial_cam); frame=env.render_rgbd(cam); rgb=np.asarray(frame["rgb"],np.uint8)[...,:3]; depth=np.asarray(frame["depth"],np.float32)
        mm=np.zeros(depth.shape,np.uint16); valid=np.isfinite(depth)&(depth>0)&(depth<65.535); mm[valid]=np.clip(np.rint(depth[valid]*1000),1,65535).astype(np.uint16); stem=f"{i:06d}"
        cv2.imwrite(str(out/"rgb"/f"{stem}.png"),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)); cv2.imwrite(str(out/"depth"/f"{stem}.png"),mm)
        T=np.asarray(env.T_cam_obj("mustard",cam),float); np.savetxt(out/"ob_in_cam"/f"{stem}.txt",T,fmt="%.10g"); poses_wc.append(np.asarray(env.T_world_cam(cam),float).tolist())
        if i==0:
            seg=frame.get("seg")
            try:
                if seg is None: mask=env.object_mask("mustard",cam)
                elif hasattr(env,"object_ids"): mask=seg==env.object_ids["mustard"]
                else: mask=np.isin(seg,_object_geom_ids(env))
            except Exception: mask=env.object_mask("mustard",cam)
            mask=np.asarray(mask,bool); cv2.imwrite(str(out/"masks"/"000000.png"),mask.astype(np.uint8)*255)
            cv2.imwrite(str(out/"overlay.png"),cv2.cvtColor(_overlay(rgb,vertices,T,K),cv2.COLOR_RGB2BGR))
            try:
                mesh_z=_mesh_only_depth(env,"mustard",cam,args.height,args.width); inner=cv2.erode(mask.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool); comp=inner&(depth>0)&(mesh_z>0); errs=np.abs(depth[comp]-mesh_z[comp])*1000
                depth_check={"pixels":int(comp.sum()),"median_abs_diff_mm":float(np.median(errs)),"p95_abs_diff_mm":float(np.percentile(errs,95))}
            except Exception as exc: depth_check={"error":f"{type(exc).__name__}: {exc}"}
    elapsed=time.perf_counter()-t0
    meta={"fps":args.fps,"resolution":[args.width,args.height],"object_names":objects,"motion":args.motion,"seed":args.seed,"frames":args.frames,"backend":backend,"depth_units":"uint16 millimeters; 0 invalid","pose_convention":"T_cam_obj OpenCV","T_world_cam":poses_wc,"export_fps":args.frames/elapsed,"depth_mesh_check":depth_check}
    (out/"meta.json").write_text(json.dumps(meta,indent=2))
    if hasattr(env,"close"): env.close()
    print(json.dumps({"out":str(out),"backend":backend,"frames":args.frames,"export_fps":args.frames/elapsed,"depth_mesh_check":depth_check},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--objects",default="mustard"); p.add_argument("--frames",type=int,default=30); p.add_argument("--motion",choices=("static","orbit_camera","push_object","robot_move"),default="static"); p.add_argument("--seed",type=int,default=0); p.add_argument("--out",default="data/sim_scenes/mustard_static"); p.add_argument("--width",type=int,default=640); p.add_argument("--height",type=int,default=480); p.add_argument("--fps",type=float,default=30.)
    args=p.parse_args()
    if args.frames<1: p.error("--frames must be >= 1")
    export(args)
if __name__=="__main__": main()
