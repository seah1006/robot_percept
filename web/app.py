from __future__ import annotations
import atexit,json,multiprocessing as mp,os,re,subprocess,threading,time,uuid
from multiprocessing import shared_memory
from collections import deque
from pathlib import Path
import cv2
from flask import Flask,Response,jsonify,render_template,request
import numpy as np
from werkzeug.utils import secure_filename
from .monowait import sleep_until, wait_for, join_thread
from .perception_stub import PerceptionBackend, estimate_pose
from .sim_worker import run_worker
ROOT=Path(__file__).resolve().parents[1]; CAD_PYTHON=ROOT/".venvs/cad/bin/python"
WIDTH,HEIGHT=int(os.getenv("SIM_WIDTH","640")),int(os.getenv("SIM_HEIGHT","480"))

def _rerr(a,b):
 d=np.asarray(a)[:3,:3]@np.asarray(b)[:3,:3].T
 return float(np.degrees(np.arccos(np.clip((np.trace(d)-1)/2,-1,1))))

def _axes(img,K,T,scale=1.,length=.06,label=None):
 T,K=np.asarray(T),np.asarray(K); pts=np.array([[0,0,0],[length,0,0],[0,length,0],[0,0,length]],float)
 cam=(T[:3,:3]@pts.T).T+T[:3,3]
 if np.any(cam[:,2]<=0): return
 uv=(K@cam.T).T; uv=np.round(uv[:,:2]/uv[:,2:3]).astype(int); o=tuple(uv[0])
 for p,c in zip(uv[1:],[(0,0,int(255*scale)),(0,int(255*scale),0),(int(255*scale),0,0)]): cv2.line(img,o,tuple(p),c,2,cv2.LINE_AA)
 if label: cv2.putText(img,label,(o[0]+5,o[1]-5),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1,cv2.LINE_AA)

class Runtime:
 def __init__(self):
  ctx=mp.get_context("spawn"); self.manager=ctx.Manager(); self.status=self.manager.dict(); self.command_q=ctx.Queue(); self.lock=ctx.Lock()
  self.shms={"rgb":shared_memory.SharedMemory(create=True,size=HEIGHT*WIDTH*3),"depth":shared_memory.SharedMemory(create=True,size=HEIGHT*WIDTH*4),"seg":shared_memory.SharedMemory(create=True,size=HEIGHT*WIDTH*4)}
  self.rgb=np.ndarray((HEIGHT,WIDTH,3),np.uint8,buffer=self.shms["rgb"].buf); self.depth=np.ndarray((HEIGHT,WIDTH),np.float32,buffer=self.shms["depth"].buf); self.seg=np.ndarray((HEIGHT,WIDTH),np.int32,buffer=self.shms["seg"].buf)
  self.rgb.fill(0); self.depth.fill(0); self.seg.fill(-1)
  cfg={"width":WIDTH,"height":HEIGHT,"objects":["mustard"],"cam":"front","seed":7}; names={k:v.name for k,v in self.shms.items()}
  self.proc=ctx.Process(target=run_worker,args=(cfg,names,self.lock,self.command_q,self.status),daemon=True); self.proc.start()
  self.perception=PerceptionBackend(os.getenv("PERCEPTION","fp").lower()); self.selected=None; self.estimate=None; self.estimate_time_ms=None; self.logs=[]; self.state_lock=threading.RLock(); self.gpu_cache={"at":0,"value":None}; self.mask=None; self.metrics={}; self.tracking_hist={k:deque(maxlen=300) for k in ('status_copy','frame_copy','perception','commit')}; self.generation=0; self.running=True; self.perception_lock=threading.RLock(); threading.Thread(target=self.track_loop,daemon=True).start(); self._warmup_manager_thread=threading.Thread(target=self.warmup_loop,daemon=True); self._warmup_manager_thread.start()
 def _g1_requested(self):
  humanoid=getattr(self,'humanoid_runtime',None)
  return bool(getattr(self,'_humanoid_starting',False) or (humanoid is not None and (humanoid.ctrl.get('enabled',False) or (hasattr(humanoid,'running') and humanoid.running()))))
 def warmup_loop(self):
  if self.perception.mode!='fp' or os.getenv('RP_PERCEPTION_WARMUP','1').lower() in ('0','false','off'):
   self.perception.warmup_state='disabled';return
  try:
   deadline=time.monotonic()+60
   while self.running and time.monotonic()<deadline:
    st=self.status.copy()
    if st.get('ready') and st.get('camera_K') and st.get('objects'):break
    time.sleep(.05)
   else:return
   while self.running:
    if self._g1_requested():
     self.perception.warmup_state='deferred_g1';time.sleep(.25);continue
    with self.perception_lock:
     if not self.running:return
     if self._g1_requested():continue
     with self.state_lock:
      if self.selected is not None:return
     if getattr(self.perception,'warmup_g1_cancel_pending',False):
      old_thread=getattr(self.perception,'warmup_thread',None)
      if (old_thread is None or not old_thread.is_alive()) and getattr(self.perception,'proc',None) is not None:
       cleanup=getattr(self.perception,'suspend_worker',None)
       if cleanup is not None:cleanup()
      if (old_thread is not None and old_thread.is_alive()) or getattr(self.perception,'proc',None) is not None:
       time.sleep(.05);continue
      self.perception.warmup_g1_cancel_pending=False
     rgb,depth,_=self.frame();st=self.status.copy()
     thread=self.perception.warmup_async(rgb,depth,np.asarray(st['camera_K']),st['objects'])
     if thread is None:return
     thread.join()
     if getattr(self.perception,'warmup_state',None) not in ('deferred','deferred_g1'):return
  except Exception as exc:self.perception.warning='warmup: '+str(exc)
 def prioritize_humanoid(self):
  # Reserve G1 before cancellation, so an unwinding manager cannot respawn FP.
  self._humanoid_starting=True
  if getattr(self.perception,'warmup_state',None)!='running':return
  cancel=getattr(self.perception,'defer_warmup_for_g1',None)
  cancelled=False
  if cancel is not None:
   try:
    with self.state_lock:
     if self.selected is None:cancelled=bool(cancel())
   except Exception as exc:self.perception.warmup_priority_error='cancel: '+str(exc)
  if cancelled:
   thread=getattr(self.perception,'warmup_thread',None)
   if thread is not None:join_thread(thread,3)
   self.perception.warmup_g1_cancel_pending=bool((thread is not None and thread.is_alive()) or getattr(self.perception,'proc',None) is not None)
   manager=getattr(self,'_warmup_manager_thread',None)
   if manager is None or not manager.is_alive():
    self._warmup_manager_thread=threading.Thread(target=self.warmup_loop,daemon=True);self._warmup_manager_thread.start()
   return
  proc=getattr(self.perception,'proc',None)
  if proc is None or not proc.is_alive():return
  try:
   priority=max(19,os.getpriority(os.PRIO_PROCESS,proc.pid))
   os.setpriority(os.PRIO_PROCESS,proc.pid,priority)
   self.perception.warmup_g1_nice_applied=priority
  except (AttributeError,OSError) as exc:self.perception.warmup_priority_error=str(exc)
 def release_humanoid_start(self):
  self._humanoid_starting=False
 def drop(self):
  with self.state_lock:
   self.status["need_depth"]=False; self.generation+=1; self.selected=None; self.estimate=None; self.mask=None; self.metrics={}
 def track_loop(self):
  last_seq=-1; tracking_generation=None; tracking_start=None; update_count=0
  while self.running:
   time.sleep(.003)
   with self.state_lock: name=self.selected; generation=self.generation
   if generation!=tracking_generation:
    tracking_generation=generation; tracking_start=None; update_count=0
   if not name:continue  # P-area idle IPC guard, approved by integration owner
   status_t0=time.perf_counter()
   st=self.status.copy()  # one atomic Manager RPC, not one RPC per status key
   status_copy_ms=(time.perf_counter()-status_t0)*1000
   if st.get("frame_seq")==last_seq:continue
   if st.get("phase","idle")!="idle" or st.get("held_object") or st.get("active_command"):
    with self.state_lock:self.metrics["tracking_state"]="paused"
    continue
   if not self.perception_lock.acquire(blocking=False):continue
   try:
    with self.state_lock:
     if generation!=self.generation or name!=self.selected:continue
    frame_t0=time.perf_counter();rgb,depth,_=self.frame();frame_copy_ms=(time.perf_counter()-frame_t0)*1000;last_seq=st.get("frame_seq"); t=time.perf_counter()
    if self.perception.mode=="fp":
     result=self.perception.call("track",name=name,rgb=rgb,depth=depth,K=np.asarray(st["camera_K"]))
     est=np.asarray(result["pose"])
    else:est=estimate_pose(rgb,depth,None,{"gt_pose":st["objects"][name]["T_cam_obj"]},name)
    perception_ms=(time.perf_counter()-t)*1000;commit_t0=time.perf_counter()
    with self.state_lock:
     if generation==self.generation:
      self.estimate=est; self.metrics["tracking_state"]="tracking"
      now=time.perf_counter()
      if tracking_start is None:tracking_start=t
      update_count+=1
      self.metrics["tracking_updates"]=update_count
      self.metrics["tracking_fps"]=update_count/max(now-tracking_start,.0001)
      self.metrics["estimate_timestamp"]=time.time()
      for key,value in [('status_copy',status_copy_ms),('frame_copy',frame_copy_ms),('perception',perception_ms),('commit',(time.perf_counter()-commit_t0)*1000)]:self.tracking_hist[key].append(value)
      if now-getattr(self,'_tracking_profile_at',0)>=1:
       self._tracking_profile_at=now
       self.metrics['tracking_pipeline_ms']={key:{'p50':round(float(np.percentile(values,50)),3),'p95':round(float(np.percentile(values,95)),3),'n':len(values)} for key,values in self.tracking_hist.items() if values}
   except Exception as exc:
    self.perception.warning=str(exc).splitlines()[-1]
    with self.state_lock:self.estimate=None
   finally:self.perception_lock.release()
 def frame(self,rgb_only=False):
  with self.lock:
   if rgb_only:return self.rgb.copy()
   return self.rgb.copy(),self.depth.copy(),self.seg.copy()
 def fresh_frame(self):
  result=self.wait(self.send("refresh"),timeout=30)
  if not result.get("ok"):raise RuntimeError(result.get("error","refresh failed"))
  return self.frame()
 def send(self,op,**kwargs):
  cid=uuid.uuid4().hex[:10]; self.command_q.put({"id":cid,"op":op,**kwargs}); return cid
 def wait(self,cid,timeout=30):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   last=dict(self.status).get("last_command")
   if last and last.get("id")==cid: return last
   sleep_until(min(end,time.monotonic()+.05))
  return {"id":cid,"ok":False,"error":"command timeout"}
 def log(self,text):
  with self.state_lock: self.logs=([{"time":time.strftime("%H:%M:%S"),"message":text}]+self.logs)[:40]
 def gpu(self):
  now=time.time()
  if now-self.gpu_cache["at"]<2: return self.gpu_cache["value"]
  try:
   out=subprocess.check_output(["/usr/lib/wsl/lib/nvidia-smi","--query-gpu=utilization.gpu,memory.used,memory.total","--format=csv,noheader,nounits"],text=True,timeout=2).strip().split(",")
   val={"util":int(out[0]),"memory_used_mb":int(out[1]),"memory_total_mb":int(out[2])}
  except Exception: val=None
  self.gpu_cache={"at":now,"value":val}; return val
 def close(self):
  self.running=False
  try:self.command_q.put({"id":"shutdown","op":"shutdown"})
  except Exception:pass
  if self.proc.is_alive():self.proc.join(timeout=3)
  if self.proc.is_alive():self.proc.terminate()
  self.perception.close()
  for shm in self.shms.values():
   try:shm.close();shm.unlink()
   except FileNotFoundError:pass
  self.manager.shutdown()

def create_app():
 app=Flask(__name__); app.config["MAX_CONTENT_LENGTH"]=100*1024*1024; rt=Runtime(); app.extensions["sim_runtime"]=rt; atexit.register(rt.close)
 from .teleop import create_blueprint as teleop_blueprint
 teleop_bp=teleop_blueprint(rt);app.register_blueprint(teleop_bp)
 from .humanoid import create_blueprint as humanoid_blueprint
 humanoid_bp=humanoid_blueprint(panda_runtime=rt)
 rt.humanoid_runtime=humanoid_bp.humanoid_runtime
 app.register_blueprint(humanoid_bp)  # G1 worker starts only on /humanoid/mode
 from .focus import focus; app.register_blueprint(focus)
 @app.get("/")
 def index():return render_template("index.html",width=WIDTH,height=HEIGHT)
 def overlay(show_gt=False):
  rgb=rt.frame(rgb_only=True); out=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR); st=dict(rt.status); K=st.get("camera_K")
  with rt.state_lock:selected,est=rt.selected,None if rt.estimate is None else rt.estimate.copy()
  paused=st.get("phase","idle")!="idle" or bool(st.get("held_object"))
  if paused:
   est=None
   if selected:cv2.putText(out,"tracking paused (robot moving / holding)",(12,48),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,220,255),1,cv2.LINE_AA)
  if selected and not paused and selected in st.get("objects",{}):
   mask=rt.mask if rt.mask is not None else np.zeros((HEIGHT,WIDTH),bool); tint=np.zeros_like(out);tint[...,1]=255;out[mask]=cv2.addWeighted(out,.55,tint,.45,0)[mask]
  if selected and K is not None and est is not None:
   _axes(out,K,est,1.,label="EST")
   obj=st.get("objects",{}).get(selected,{})
   if obj.get("bounds"):
    bounds=np.asarray(obj["bounds"]);corners=np.array([[bounds[i,0],bounds[j,1],bounds[k,2]] for i in (0,1) for j in (0,1) for k in (0,1)])
    pts=(est[:3,:3]@corners.T).T+est[:3,3];uv=(np.asarray(K)@pts.T).T
    if np.all(pts[:,2]>0):
     uv=np.rint(uv[:,:2]/uv[:,2:3]).astype(int)
     for i in range(8):
      for bit in (1,2,4):
       if not i&bit:cv2.line(out,tuple(uv[i]),tuple(uv[i|bit]),(0,220,255),1,cv2.LINE_AA)

  if show_gt and K is not None and selected in st.get("objects",{}):_axes(out,K,st["objects"][selected]["T_cam_obj"],.55,label="GT")
  if K is not None and st.get("ee_pose") and st.get("T_world_cam"):_axes(out,K,np.linalg.inv(np.asarray(st["T_world_cam"]))@np.asarray(st["ee_pose"]),.75,length=.08,label="TCP")
  # 단계/FPS 는 웹 UI 의 HUD 칩으로 표시 (영상 안 텍스트 제거)
  return out
 # A lazy shared producer per overlay variant, never one encoder per client.
 video_condition=threading.Condition(); video_cache={}; video_threads=set(); video_consumers={}; video_access={}
 def produce_video(show_gt):
  last_seq=-1
  while rt.running:
   with video_condition:
    if not video_consumers.get(show_gt,0) and time.monotonic()-video_access.get(show_gt,0)>2:
     video_threads.discard(show_gt);video_cache.pop(show_gt,None);return  # 오래 쉰 뒤 첫 프레임이 stale 하지 않게
   seq=rt.status.get("frame_seq",0)
   if seq==last_seq:time.sleep(.003);continue
   last_seq=seq
   ok,jpg=cv2.imencode(".jpg",overlay(show_gt),[cv2.IMWRITE_JPEG_QUALITY,80])
   if ok:
    with video_condition:
     video_cache[show_gt]=(seq,jpg.tobytes());video_condition.notify_all()
 def cached_video(show_gt,last_seq=None):
  with video_condition:
   video_access[show_gt]=time.monotonic()
   if show_gt not in video_threads:
    video_threads.add(show_gt);threading.Thread(target=produce_video,args=(show_gt,),daemon=True).start()
  wait_for(lambda: show_gt in video_cache and video_cache[show_gt][0] != last_seq, 2, slice_s=.01)
  with video_condition:
   return video_cache.get(show_gt)
 @app.get("/video")
 def video():
  show_gt=request.args.get("gt","0") in ("1","true","on")
  def gen():
   last_seq=None
   with video_condition:
    video_consumers[show_gt]=video_consumers.get(show_gt,0)+1
    rt.status['video_viewers']=sum(video_consumers.values())
    # Wait for a new worker frame rather than serving an old idle cache.
    last_seq=rt.status.get('frame_seq',0)
   try:
    while rt.running:
     item=cached_video(show_gt,last_seq)
     if item is None or item[0]==last_seq:continue
     last_seq,jpg=item
     yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"+jpg+b"\r\n"
   finally:
    with video_condition:
     video_consumers[show_gt]-=1
     rt.status['video_viewers']=sum(video_consumers.values())
  return Response(gen(),mimetype="multipart/x-mixed-replace; boundary=frame")
 @app.get("/frame.jpg")
 def frame_jpg():
  rt.status['video_until']=time.monotonic()+.25
  item=cached_video(request.args.get("gt")=="1")
  return Response(item[1] if item else b"",mimetype="image/jpeg")
 @app.post("/click")
 def click():
  data=request.get_json(force=True);x,y=int(round(float(data["x"]))),int(round(float(data["y"])))
  if not(0<=x<WIDTH and 0<=y<HEIGHT):return jsonify(ok=False,error="클릭 좌표가 영상 밖입니다"),400
  with rt.perception_lock:
   rgb,depth,seg=rt.fresh_frame();st=dict(rt.status);objects=st.get("objects",{});K=np.asarray(st["camera_K"])
   if data.get("mode")=="place":
    z=float(depth[y,x])
    if not np.isfinite(z) or z<=0:return jsonify(ok=False,error="유효한 깊이가 없습니다"),400
    point=np.asarray(st["T_world_cam"])@np.r_[np.linalg.inv(K)@np.array([x,y,1])*z,1]
    cid=rt.send("place",xyz=point[:3].tolist())
    if rt.selected:threading.Thread(target=reacquire_after,args=(cid,[point[0],point[1],getattr(rt,"obj_center_z",point[2]+.08)]),daemon=True).start()
    return jsonify(ok=True,command_id=cid,xyz=point[:3].tolist()),202
   body,code=select_at(x,y,rgb,depth,seg,st,objects,K)
   return jsonify(body),code
 def select_at(x,y,rgb,depth,seg,st,objects,K):
   generation=rt.generation  # 실패한 클릭은 기존 선택을 지우지 않음 (성공 시에만 교체)
   t0=time.perf_counter();metrics={}
   try:
    if rt.perception.mode=="fp":
     result=rt.perception.call("segment",rgb=rgb,depth=depth,click=(x,y));mask=result["mask"];metrics["sam_ms"]=result["ms"];metrics["sam_selected"]=result["sam_selected"]
    else:mask=seg==int(seg[y,x]);metrics["sam_ms"]=0
    overlaps={n:int(np.count_nonzero(mask & (seg==int(o["id"])))) for n,o in objects.items()}
    name=max(overlaps,key=overlaps.get) if overlaps else None
    if name is None or overlaps[name]==0:return dict(ok=False,error="물체가 아닌 곳을 클릭했어요. 병이나 물체 위를 클릭해 주세요"),404
    gt=np.asarray(objects[name]["T_cam_obj"])
    if rt.perception.mode=="fp":
     result=rt.perception.call("register",name=name,mesh=objects[name]["mesh"],rgb=rgb,depth=depth,mask=mask,K=K)
     est=np.asarray(result["pose"]);metrics["register_ms"]=result["ms"];metrics["peak_mb"]=result["peak_mb"]
    else:est=estimate_pose(rgb,depth,K,{"gt_pose":gt},name);metrics["register_ms"]=0
   except Exception as exc:return dict(ok=False,error=str(exc)),500
   gtmask=seg==int(objects[name]["id"]);metrics["mask_iou"]=float(np.count_nonzero(mask&gtmask)/max(np.count_nonzero(mask|gtmask),1));metrics["tracking_fps"]=0;metrics["estimate_timestamp"]=time.time()
   ms=(time.perf_counter()-t0)*1000
   with rt.state_lock:
    if generation!=rt.generation:return dict(ok=False,error="장면이 변경되었습니다. 다시 선택하세요"),409
    rt.generation+=1  # 이전 물체 추적 결과가 새 선택을 덮어쓰지 않게
    rt.selected,rt.estimate,rt.estimate_time_ms,rt.mask,rt.metrics=name,est,ms,mask,metrics
    rt.status["need_depth"]=True
   trans=float(np.linalg.norm(est[:3,3]-gt[:3,3])*1000);rot=_rerr(est,gt);rt.log(f"{name} 선택, 추정 오차 {trans:.1f} mm / {rot:.1f} deg")
   return dict(ok=True,object=name,pixel=[x,y],estimate=est.tolist(),error_mm=trans,error_deg=rot,timing_ms=ms,**metrics),200
 def reacquire_after(cid,xyz):
  """놓기가 끝나면, 로봇이 놓은 위치(로봇이 아는 값)를 영상에 투영해서 그 픽셀로 SAM2+FoundationPose 다시 등록"""
  res=rt.wait(cid,timeout=180)
  if not res.get("ok"):return
  time.sleep(.6)
  with rt.perception_lock:
   rgb,depth,seg=rt.fresh_frame();st=dict(rt.status);objects=st.get("objects",{});K=np.asarray(st["camera_K"])
   p=np.linalg.inv(np.asarray(st["T_world_cam"]))@np.r_[np.asarray(xyz,float),1];uv=K@p[:3]
   if uv[2]<=0:return
   u,v=int(round(uv[0]/uv[2])),int(round(uv[1]/uv[2]))
   if not(0<=u<WIDTH and 0<=v<HEIGHT):return
   body,code=select_at(u,v,rgb,depth,seg,st,objects,K)
  rt.log("놓은 위치에서 다시 인식: "+("성공" if code==200 else body.get("error","실패")))
 @app.post("/robot/pick")
 def pick():
  data=request.get_json(silent=True) or {}
  with rt.state_lock:name=data.get("target") or rt.selected;est=None if rt.estimate is None else rt.estimate.tolist()
  if not name or est is None or name!=rt.selected:return jsonify(ok=False,error="먼저 영상에서 물체를 선택하세요"),400
  st=dict(rt.status);rt.obj_center_z=float((np.asarray(st["T_world_cam"])@np.asarray(est))[2,3])
  cid=rt.send("pick",name=name,T_cam_obj=est,gt_assist=data.get("gt_assist",True));rt.log(f"집기 명령: {name} ({cid})");return jsonify(ok=True,command_id=cid,target=name),202
 @app.post("/robot/place")
 def place():
  data=request.get_json(silent=True) or {};xyz=data.get("xyz")
  if xyz is None and all(k in data for k in ("x","y","z")):xyz=[data["x"],data["y"],data["z"]]
  if xyz is None:xyz=[.55,.18,.34]
  if len(xyz)!=3:return jsonify(ok=False,error="xyz는 길이 3이어야 합니다"),400
  cid=rt.send("place",xyz=[float(v) for v in xyz],**({"gt_assist":data["gt_assist"]} if "gt_assist" in data else {}));rt.log(f"놓기 명령 ({cid})")
  if rt.selected:threading.Thread(target=reacquire_after,args=(cid,[float(xyz[0]),float(xyz[1]),getattr(rt,"obj_center_z",float(xyz[2])+.08)]),daemon=True).start()
  return jsonify(ok=True,command_id=cid,xyz=xyz),202
 @app.post("/reset")
 def reset():
  rt.drop(); cid=rt.send("reset",randomize=False);rt.log("시뮬레이션 리셋");return jsonify(ok=True,command_id=cid),202
 @app.post("/scene/randomize")
 def randomize():
  rt.drop(); cid=rt.send("randomize",seed=int(time.time())&0xffff);rt.log("장면 랜덤 배치");return jsonify(ok=True,command_id=cid),202
 @app.post("/cad/upload")
 def cad_upload():
  f=request.files.get("file")
  if not f or not f.filename:return jsonify(ok=False,error="file 필드가 필요합니다"),400
  filename=secure_filename(f.filename);ext=Path(filename).suffix.lower()
  if ext not in (".stp",".step"):return jsonify(ok=False,error=".stp/.step만 지원합니다"),400
  stem=re.sub(r"[^A-Za-z0-9_-]","_",Path(filename).stem)
  if not stem or stem[0].isdigit():stem="cad_"+stem
  rt.drop(); name=f"{stem}_{uuid.uuid4().hex[:5]}";out=ROOT/"cad_uploads/web"/name;out.mkdir(parents=True,exist_ok=True);src=out/(name+ext);f.save(src)
  cmd=[str(CAD_PYTHON),str(ROOT/"tools/stp_to_mesh.py"),str(src),"-o",str(out),"--name",name,"--center","bbox","--collision",request.form.get("collision","hull")]
  if request.form.get("unit"):cmd += ["--unit",request.form["unit"]]
  try:subprocess.run(cmd,check=True,text=True,capture_output=True,timeout=180)
  except subprocess.CalledProcessError as exc:return jsonify(ok=False,error=exc.stderr[-1500:]),422
  meta=json.loads((out/f"{name}.json").read_text());visual=str(out/f"{name}.obj");collisions=[str(out/c["file"]) for c in meta["files"]["collision"]];cid=rt.send("add_object",name=name,visual_obj=visual,collision_objs=collisions or [visual]);result=rt.wait(cid,timeout=60)
  if not result.get("ok"):return jsonify(ok=False,error=result.get("error"),command_id=cid),500
  rt.log(f"CAD 추가: {name}");return jsonify(ok=True,name=name,command_id=cid,extents_m=meta["mesh"]["extents_m"],triangles=meta["mesh"]["triangles"],files=meta["files"])
 @app.get("/objects")
 def objects():return jsonify(ok=True,objects=dict(rt.status).get("objects",{}))
 def status_payload():
  st=dict(rt.status)
  with rt.state_lock:selected,est,ms,logs=rt.selected,rt.estimate,rt.estimate_time_ms,list(rt.logs)
  pose=None
  paused=st.get("phase","idle")!="idle" or bool(st.get("held_object"))
  if selected and est is not None and not paused and selected in st.get("objects",{}):
   gt=np.asarray(st["objects"][selected]["T_cam_obj"]);pose={"estimate":est.tolist(),"error_mm":float(np.linalg.norm(est[:3,3]-gt[:3,3])*1000),"error_deg":_rerr(est,gt),"timing_ms":ms,**rt.metrics}
  st["perception_warmup"]={"state":getattr(rt.perception,"warmup_state","idle"),"error":getattr(rt.perception,"warmup_error",None),"seconds":getattr(rt.perception,"warmup_seconds",None),"g1_cpu_nice":getattr(rt.perception,"warmup_g1_nice_applied",None),"priority_error":getattr(rt.perception,"warmup_priority_error",None)}
  st.update({"tracking_state":"paused" if (selected and paused) else rt.metrics.get("tracking_state","idle" if not selected else "tracking"),"selected_object":selected,"pose":pose,"perception":rt.perception.mode,"perception_warning":rt.perception.warning,"gpu":rt.gpu(),"logs":logs});return st
 @app.get("/status")
 def status():return jsonify(status_payload())
 from .realtime import register_realtime
 app.extensions["realtime_sock"]=register_realtime(app,status_payload,teleop_bp,humanoid_bp)
 return app

if __name__=="__main__":
 mp.set_start_method("spawn",force=True);app=create_app();app.run(host=os.getenv("HOST","127.0.0.1"),port=int(os.getenv("PORT","5080")),threaded=True,use_reloader=False)
