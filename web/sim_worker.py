"""Spawned process that exclusively owns MuJoCo and robot control."""
from __future__ import annotations
import os, queue, time, traceback
from multiprocessing import shared_memory
import numpy as np


class ControlAdapter:
    """Small compatibility boundary around sim.control.Controller."""
    def __init__(self, env, phase_cb):
        from sim.control import Controller
        self.env, self.phase_cb = env, phase_cb
        self.controller = Controller(env, step_hook=self._step_hook)
        self.render_hook, self._steps = None, 0
        self._wall0, self._sim0 = time.monotonic(), float(env.data.time)

    def _step_hook(self, _controller):
        self._steps += 1
        if self.render_hook and self._steps % 35 == 0: self.render_hook()
        delay = self._wall0 + (float(self.env.data.time) - self._sim0) - time.monotonic()
        if delay > 0: time.sleep(delay)

    def pick(self, grasp, approach=.10, lift=.15):
        G = np.asarray(grasp,float); pre=G.copy(); pre[:3,3] += [0,0,approach]
        self.phase_cb("pick.open"); self.controller.open_gripper()
        self.phase_cb("pick.approach"); self.controller.move_cartesian(pre)
        self.phase_cb("pick.descend"); self.controller.move_cartesian(G,duration=1.0)
        self.phase_cb("pick.grasp"); width=self.controller.close_gripper()
        self.phase_cb("pick.lift"); up=G.copy(); up[2,3]+=lift; self.controller.move_cartesian(up)
        return float(width)

    def place(self, target, object_pose_fn=None, desired_object_pose=None):
        self.phase_cb("place.approach")
        out=self.controller.place(target,object_pose_fn=object_pose_fn,desired_object_pose=desired_object_pose)
        self.phase_cb("place.done"); return out


def _jm(x): return np.asarray(x,dtype=float).round(8).tolist()


def render_period(status, now):
    """Only throttle idle rendering; never physics, tracking or robot tasks."""
    active = (status.get('video_viewers', 0) > 0 or now < status.get('video_until', 0)
              or status.get('need_depth') or status.get('teleop_enabled')
              or status.get('active_command') or status.get('held_object')
              or status.get('phase', 'idle') not in ('idle', 'ready'))
    return 1 / 30 if active else .5


def run_worker(cfg, shm_names, lock, command_q, status, parent_pid=None, stop_event=None):
    shms=[]
    try:
        from sim.env import SimEnv
        from sim.control import top_down_grasp
        shape=(cfg["height"],cfg["width"])
        rs=shared_memory.SharedMemory(name=shm_names["rgb"]); shms.append(rs)
        ds=shared_memory.SharedMemory(name=shm_names["depth"]); shms.append(ds)
        ss=shared_memory.SharedMemory(name=shm_names["seg"]); shms.append(ss)
        rgb_out=np.ndarray((*shape,3),np.uint8,buffer=rs.buf)
        depth_out=np.ndarray(shape,np.float32,buffer=ds.buf)
        seg_out=np.ndarray(shape,np.int32,buffer=ss.buf)
        env=SimEnv(objects=tuple(cfg.get("objects",["mustard"])),width=cfg["width"],height=cfg["height"],cam=cfg.get("cam","front"),shadows=False,reflections=False,seed=cfg.get("seed",0))
        seg_poses={}
        current_cam=cfg.get("cam","front"); last_render=0.0; frame_count=0; fps_t0=time.monotonic()

        def set_phase(p):
            status["phase"]=p; status["state"]="busy" if p not in ("idle","ready") else "ready"

        adapter=ControlAdapter(env,set_phase)
        from sim.teleop import TeleopServo
        teleop=TeleopServo(env,status)
        humanoid_render_paused=False  # mode-on only; physics and C commands continue
        demand_check=0.; render_interval=.5

        def publish(force=False):
            nonlocal last_render,frame_count,fps_t0,demand_check,render_interval
            now=time.monotonic()
            if now-demand_check >= .025:
                render_interval=render_period(status,now); demand_check=now
            if not force and now-last_render < render_interval: return
            status["render_idle"]=render_interval > 1/30
            if not force and humanoid_render_paused:
                last_render=now
                return
            need_depth=force or bool(status.get("need_depth",False))
            # Refresh segmentation whenever an object has moved since its mask,
            # including uncommanded falling/bumping while tracking.
            poses={n:env.T_world_obj(n).copy() for n in env.object_names}
            moved=any(n not in seg_poses or not np.allclose(T,seg_poses[n],atol=1e-5,rtol=0) for n,T in poses.items())
            need_seg=force or (need_depth and moved)
            pack=env.render_rgbd(current_cam,depth=need_depth,segmentation=need_seg)
            if need_seg:seg_poses.clear();seg_poses.update(poses)
            # Keep exact object-edge invalidation for tracking without a segmentation readback.
            # Motion-sensitive mask refresh above bounds stale-mask error to 10 micrometres.
            if "depth" in pack and "seg" not in pack:
                import cv2
                kernel=np.ones((3,3),np.uint8)
                for oid in env.object_ids.values():
                    edge=cv2.morphologyEx((seg_out==oid).astype(np.uint8),cv2.MORPH_GRADIENT,kernel).astype(bool)
                    pack["depth"][edge]=0
            with lock:
                rgb_out[:]=pack["rgb"]
                if "depth" in pack: depth_out[:]=pack["depth"]
                if "seg" in pack: seg_out[:]=pack["seg"]
            last_render=now; frame_count+=1; elapsed=now-fps_t0
            if elapsed>=1: status["fps"]=round(frame_count/elapsed,1); frame_count=0; fps_t0=now
            objs={}; K=env.camera_K(current_cam); Twc=env.T_world_cam(current_cam)
            for name in env.object_names:
                Tco=env.T_cam_obj(name,current_cam); p=K@Tco[:3,3]
                uv=[float(p[0]/p[2]),float(p[1]/p[2])] if p[2]>0 else None; spec=env.registry[name]
                objs[name]={"id":int(env.object_ids[name]),"T_world_obj":_jm(env.T_world_obj(name)),"T_cam_obj":_jm(Tco),"center_px":uv,"extents":(spec.bounds[1]-spec.bounds[0]).tolist(),"bounds":spec.bounds.tolist(),"mesh":spec.visual_obj}
            status["camera_K"]=_jm(K); status["T_world_cam"]=_jm(Twc); status["ee_pose"]=_jm(env.ee_pose())
            status["arm_qpos"]=env.arm_qpos().round(6).tolist(); status["objects"]=objs
            status["frame_seq"]=int(status.get("frame_seq",0))+1; status["timestamp"]=time.time()

        rtf_wall=time.monotonic(); rtf_sim=float(env.data.time)
        adapter.render_hook=publish
        status.update({"ready":False,"state":"starting","phase":"idle","error":None,"fps":0.0,"frame_seq":0,"camera":current_cam,"last_command":None,"held_object":None})
        publish(True); status["ready"]=True; status["state"]="ready"; next_step=time.monotonic(); parent_check=next_step; running=True
        while running:
            if stop_event is not None and stop_event.is_set(): break
            if parent_pid is not None and time.monotonic() >= parent_check:
                if os.getppid() != parent_pid: break
                parent_check = time.monotonic() + .25
            try: cmd=command_q.get_nowait()
            except queue.Empty: cmd=None
            if cmd:
                cid,op=cmd.get("id"),cmd.get("op")
                try:
                    status["active_command"]=cid
                    if op not in ("refresh","set_view"): status["teleop_enabled"]=False
                    if op=="shutdown": running=False
                    elif op=="refresh": pass
                    elif op=="teleop_render_pause":
                        humanoid_render_paused=bool(cmd.get("enabled",False))
                        status["humanoid_render_paused"]=humanoid_render_paused
                        frame_count=0; fps_t0=time.monotonic(); last_render=0.
                    elif op=="reset":
                        set_phase("reset"); env.reset(seed=cmd.get("seed"),randomize=cmd.get("randomize",False)); adapter=ControlAdapter(env,set_phase); adapter.render_hook=publish; status["held_object"]=None
                    elif op=="randomize":
                        set_phase("randomize"); env.reset(seed=cmd.get("seed"),randomize=True); adapter=ControlAdapter(env,set_phase); adapter.render_hook=publish; status["held_object"]=None
                    elif op=="set_view": current_cam=cmd.get("camera","front"); status["camera"]=current_cam
                    elif op=="pick":
                        name=cmd["name"]; raw=cmd.get("T_cam_obj");
                        if raw is None: raise ValueError("유효한 추정 자세가 필요합니다")
                        Tco=np.asarray(raw if raw is not None else env.T_cam_obj(name,current_cam),float)
                        Two=env.T_world_cam(current_cam)@Tco; ext=env.registry[name].bounds[1]-env.registry[name].bounds[0]
                        status["held_object"]=None
                        adapter.controller.gt_assist=bool(cmd.get("gt_assist", True))
                        res=adapter.controller.pick_object(Two,env.registry[name].bounds,phase_cb=set_phase,object_pose_fn=lambda:env.T_world_obj(name))
                        status["gripper_width"]=res["width"]; status["grasp_mode"]=res["mode"]; status["last_pick"]={"ok":bool(res["ok"]),"gt_lift_ok":res.get("gt_lift_ok"),"lifted_m":res.get("lifted")}
                        if not res["ok"]:
                            adapter.controller.open_gripper(); raise RuntimeError(f"집기 실패: 물체가 들리지 않았습니다 (들린 높이 {100*(res['lifted'] or 0):.1f}cm)")
                        status["held_object"]=name
                    elif op=="place":
                        name=status.get("held_object")
                        if not name: raise RuntimeError("집고 있는 물체가 없습니다")
                        xyz=np.asarray(cmd.get("xyz",[.55,.15,.34]),float)
                        if "gt_assist" in cmd: adapter.controller.gt_assist=bool(cmd["gt_assist"])
                        res=adapter.controller.place_object((float(xyz[0]),float(xyz[1])),lambda:env.T_world_obj(name),phase_cb=set_phase)
                        status["held_object"]=None; status["last_place"]={"err_mm":round(res["err_mm"],1),"upright":round(res["upright"],3)}
                        set_phase("home")
                        try:
                            status["last_home"]=adapter.controller.return_home(lambda:env.T_world_obj(name)); status["home_warning"]=None
                        except RuntimeError as exc:
                            status["last_home"]={"ok":False,"error":str(exc)}; status["home_warning"]=str(exc)
                    elif op=="add_object":
                        set_phase("cad.add"); env.add_object_from_mesh(cmd["name"],cmd["visual_obj"],cmd["collision_objs"],mass=cmd.get("mass",.1),rgba=cmd.get("rgba")); env.reset(randomize=False); adapter=ControlAdapter(env,set_phase); adapter.render_hook=publish
                    else: raise ValueError(f"unknown command: {op}")
                    publish(True); status["last_command"]={"id":cid,"op":op,"ok":True,"time":time.time()}; status["error"]=None
                except Exception as exc:
                    status["error"]=f"{type(exc).__name__}: {exc}"; status["last_traceback"]=traceback.format_exc(); status["last_command"]={"id":cid,"op":op,"ok":False,"error":status["error"],"time":time.time()}
                finally:
                    if status["last_command"]["ok"]: set_phase("idle")
                    else: status["phase"]="error"; status["state"]="error"
                    status["active_command"]=None
            now=time.monotonic(); steps=0
            while now>=next_step and steps<100:
                try: teleop.tick()
                except Exception as exc:
                    status["teleop_enabled"]=False
                    status["teleop_error"]=f"{type(exc).__name__}: {exc}"
                    # Isolate tracker faults: ordinary simulation/commands keep running.
                    teleop.was=False
                env.step(1); next_step += env.model.opt.timestep; steps += 1
            if steps==100 and now>=next_step: next_step=now+env.model.opt.timestep
            if time.monotonic()-rtf_wall>=1:
                status["rtf"]=(float(env.data.time)-rtf_sim)/(time.monotonic()-rtf_wall)
                status["sim_time"]=float(env.data.time)
                rtf_wall=time.monotonic(); rtf_sim=float(env.data.time)
            publish(); time.sleep(.001)
        env.close()
    except Exception as exc:
        status["ready"]=False; status["state"]="crashed"; status["error"]=f"{type(exc).__name__}: {exc}"; status["last_traceback"]=traceback.format_exc()
    finally:
        for shm in shms: shm.close()
