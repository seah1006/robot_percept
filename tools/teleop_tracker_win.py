"""Windows USB hand tracker. Tasks API, video and JSONL replay supported."""
import argparse,json,time,math,urllib.request,pathlib,threading,concurrent.futures,itertools,queue
import os
os.environ['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
import numpy as np
import cv2
# Windows Python 3.12 monotonic uses 15.625 ms GetTickCount64 ticks.
# Use QPC perf_counter for pacing/filter dt; time.time is only HTTP wall time.

def preview_coords(values):
 # Invisible MediaPipe feet can extrapolate far outside the image. Limit only
 # display coordinates; metric world landmarks used for control stay unchanged.
 return np.clip(values,-2.,2.).tolist()

def pipeline_enabled(mode,requested=None):
 return mode!='panda' if requested is None else bool(requested)

def update_routes(mode,sample,humanoid):
 routes=[]
 if sample is not None and mode!='humanoid':routes.append(('/teleop/update',sample))
 if humanoid is not None and mode!='panda':routes.append(('/humanoid/update',humanoid))
 return routes


# JSONL v2 preserves endpoint payloads; v1 features recordings remain readable.
def recording_row(t, seq, capture_at, mode, sample, humanoid, landmarks=None):
 return dict(schema='robot_percept.tracker.v2',t=t,seq=seq,capture_at=capture_at,
             mode=mode,features=sample,humanoid=humanoid,landmarks=landmarks or [])

def replay_routes(row, mode, now):
 capture=now-max(0.,float(row.get('t',0))-float(row.get('capture_t',row.get('t',0))))
 sample=row.get('features',row if 'schema' not in row else None)
 humanoid=row.get('humanoid')
 routes=[]
 for route,payload in update_routes(mode,sample,humanoid):
  payload=dict(payload);payload['sent_at']=now;payload['capture_at']=capture
  payload['seq']=row.get('seq',0);routes.append((route,payload))
 return routes


def websocket_route_enabled(transport,raw=False):
 return transport=='ws' and not raw


def build_parser():
 p=argparse.ArgumentParser(); p.add_argument('--transport',choices=['http','ws'],default='ws'); p.add_argument('--http-client',choices=['requests','urllib3'],default=None); p.add_argument('--hand-hold-ms',type=float,default=150); p.add_argument('--metrics-out'); p.add_argument('--prefetch-video',action=argparse.BooleanOptionalAction,default=True); p.add_argument('--pipeline',action=argparse.BooleanOptionalAction,default=None); p.add_argument('--opencv-threads',type=int,default=1); p.add_argument('--infer-width',type=int,choices=[320,480,640],default=640); p.add_argument('--serial',action='store_true'); p.add_argument('--loop-video',action='store_true'); p.add_argument('--mode',choices=['panda','humanoid','both'],default='panda'); p.add_argument('--pose-model',default=str(pathlib.Path.home()/'Documents/sam_camera/models/pose_landmarker_lite.task')); p.add_argument('--url',default='http://localhost:5089'); p.add_argument('--video'); p.add_argument('--replay'); p.add_argument('--record'); p.add_argument('--seconds',type=float,default=0); p.add_argument('--camera',type=int,default=0); p.add_argument('--model',default=str(pathlib.Path.home()/'Documents/sam_camera/models/hand_landmarker.task')); return p


def parse_args(argv=None):
 return build_parser().parse_args(argv)


class WebSocketTransport:
 def __init__(self,url,connector=None,timeout=.6):
  self.url=url.replace('http://','ws://').replace('https://','wss://').rstrip('/')+'/tracker/ws';self.connector=connector;self.timeout=timeout;self.ws=None
 def close(self):
  if self.ws is not None:
   try:self.ws.close()
   except Exception:pass
   self.ws=None
 def _open(self):
  if self.connector is None:
   import websocket
   self.connector=websocket.create_connection
  self.ws=self.connector(self.url,timeout=self.timeout,enable_multithread=True)
 def request(self,route,data,raw=False):
  message=data if raw else json.dumps({'route':route,'data':data},separators=(',',':'))
  last=None
  for attempt in range(2):
   try:
    if self.ws is None:self._open()
    if raw:self.ws.send_binary(message)
    else:self.ws.send(message)
    reply=json.loads(self.ws.recv())
    if not reply.get('ok'):raise RuntimeError('WS '+str(reply.get('status',500))+': '+str(reply.get('error','request failed')))
    return reply
   except Exception as exc:
    last=exc;self.close()
    if attempt==0:time.sleep(.05)
  raise last


def exception_chain(exc):
 while exc is not None:
  yield exc
  exc=exc.__cause__ or exc.__context__


def missing_websocket_client(exc):
 return any(isinstance(item,ModuleNotFoundError) and item.name=='websocket' for item in exception_chain(exc))


def websocket_status(exc):
 for item in exception_chain(exc):
  status=getattr(item,'status_code',None)
  if status is not None:return status
 return None


def websocket_error_summary(exc,limit=200):
 lines=[line.strip() for line in str(exc).splitlines() if line.strip()]
 summary=lines[0] if lines else type(exc).__name__
 status=websocket_status(exc)
 if status is not None and str(status) not in summary:summary=f'HTTP {status}: {summary}'
 return summary[:limit]


def permanent_ws_failure(exc):
 return missing_websocket_client(exc) or websocket_status(exc)==404


class FallbackTransport:
 """Fall back to HTTP; retry transient startup failures, but pin unsupported WS sessions."""
 def __init__(self,http_post,ws_factory,warn=print,clock=time.monotonic,retry_interval=30.):
  self.http_post=http_post;self.ws_factory=ws_factory;self.warn=warn;self.clock=clock;self.retry_interval=retry_interval;self.ws=None
  self.effective='ws';self.fallback=False;self.ws_succeeded=False;self.warned=False;self.retry_at=None
 def _warn_once(self,exc,permanent):
  if self.warned:return
  if permanent:message='WebSocket is unsupported; falling back to HTTP for this session. Restart the tracker to retry WS.'
  else:message=f'WebSocket connection failed; using HTTP temporarily and retrying WS every {self.retry_interval:g} seconds.'
  if missing_websocket_client(exc):message+=' Run: python -m pip install websocket-client==1.8.0'
  self.warn(json.dumps({'warning':message,'ws_error':websocket_error_summary(exc),'transport':'http'},ensure_ascii=False),flush=True)
  self.warned=True
 def _fallback(self,exc):
  permanent=permanent_ws_failure(exc);self.effective='http';self.fallback=True
  self.retry_at=None if permanent else self.clock()+self.retry_interval
  self._warn_once(exc,permanent)
 def request(self,route,data,raw=False):
  if raw:return self.http_post(route,data,raw)
  if self.effective=='http':
   if self.retry_at is None or self.clock()<self.retry_at:return self.http_post(route,data,raw)
   self.effective='ws';self.ws=None;self.retry_at=None
  try:
   if self.ws is None:self.ws=self.ws_factory()
   reply=self.ws.request(route,data,False);self.ws_succeeded=True;return reply
  except Exception as exc:
   if self.ws_succeeded:raise
   self._fallback(exc);return self.http_post(route,data,raw)

class HandHold:
 def __init__(self, milliseconds=150):self.limit=milliseconds;self.last={}
 def apply(self, sample, now):
  hands=sample.setdefault('hands',{});quality={}
  for side in ('left','right'):
   if side in hands:
    self.last[side]=(now,hands[side]);quality[side]=dict(state='tracked',confidence=1.,age_ms=0.)
   elif sample.get('detected') and side in self.last and (now-self.last[side][0])*1000<=self.limit:
    age=(now-self.last[side][0])*1000;hands[side]=self.last[side][1]
    quality[side]=dict(state='held',confidence=max(0.,1-age/max(1,self.limit)),age_ms=age)
   else:quality[side]=dict(state='missing',confidence=0.,age_ms=None)
  sample.setdefault('quality',{})['hands']=quality
  return sample

class OneEuro:
 def __init__(self):self.v=None; self.t=None; self.d=None
 def __call__(self,v,t):
  v=np.array(v,float)
  if self.v is None:self.v=v; self.t=t; self.d=np.zeros_like(v); return v
  dt=max(.001,t-self.t); raw=(v-self.v)/dt; a=1/(1+1/(2*math.pi*dt)); self.d+=a*(raw-self.d)
  a=1/(1+1/(2*math.pi*(1.5+.03*np.abs(self.d))*dt)); self.v+=a*(v-self.v); self.t=t; return self.v.copy()

def main():
 a=parse_args()
 a.pipeline=pipeline_enabled(a.mode,a.pipeline)
 a.http_client=a.http_client or ('requests' if a.mode=='panda' else 'urllib3')
 a.url=a.url.replace('://localhost', '://127.0.0.1')
 if a.mode!='panda':cv2.setNumThreads(a.opencv_threads)
 details={k:[] for k in ['visibility','hold_quality','timestamp','capture_lock','pose_overlay','panda_features_overlay','hand_overlay','http_headers','http_body','http_response_decode','ws_roundtrip']}
 stages={k:[] for k in ['pacing','preprocess','neural','retarget','overlay','queue']};post_ms=[];json_ms=[];payload_bytes=[];server_ms=[];loop_ms=[];preview_encode_ms=[];preview_post_ms=[]
 # requests uses persistent HTTP connections; standard library is fallback.
 try:
  import requests
  http_local=threading.local()
  def post(route,data,raw=False):
   if not hasattr(http_local,'session'):http_local.session=requests.Session();http_local.session.trust_env=False
   t0=time.perf_counter();body=data if raw else json.dumps(data,separators=(',',':')).encode();t1=time.perf_counter()
   headers={'Content-Type':'image/jpeg' if raw else 'application/json'}
   if a.http_client=='urllib3':
    import urllib3
    if not hasattr(http_local,'pool'):http_local.pool=urllib3.PoolManager(num_pools=1,maxsize=1)
    response=http_local.pool.request('POST',a.url+route,body=body,headers=headers,timeout=urllib3.Timeout(total=.6),retries=False,preload_content=False)
    th=time.perf_counter();raw_response=response.read();tb=time.perf_counter();response.release_conn()
    if response.status>=400:raise RuntimeError('HTTP '+str(response.status)+': '+raw_response.decode(errors='replace')[:300])
    elapsed_headers=th-t1;elapsed_body=tb-th
   else:
    response=http_local.session.post(a.url+route,data=body,headers=headers,timeout=.6)
    tb=time.perf_counter();raw_response=response.content;response.raise_for_status()
    elapsed_headers=response.elapsed.total_seconds();elapsed_body=max(0.,tb-t1-elapsed_headers)
   if route=='/humanoid/update':
    json_ms.append((t1-t0)*1000);payload_bytes.append(len(body));post_ms.append((tb-t1)*1000)
    details['http_headers'].append(elapsed_headers*1000);details['http_body'].append(elapsed_body*1000)
    td=time.perf_counter();server_ms.append(json.loads(raw_response).get('process_ms',0));details['http_response_decode'].append((time.perf_counter()-td)*1000)
   return response
 except ImportError:
  def post(route,data,raw=False):return urllib.request.urlopen(urllib.request.Request(a.url+route,data=data if raw else json.dumps(data).encode(),headers={'Content-Type':'image/jpeg' if raw else 'application/json'}),timeout=.6)
 http_post=post;transport_state=None
 if a.transport=='ws':
  transport_state=FallbackTransport(http_post,lambda:WebSocketTransport(a.url))
  def post(route,data,raw=False):
   # Windows localhost→WSL에서 binary WS는 약 40ms 지연 ACK 회귀가 있어 preview는 HTTP 유지.
   if not websocket_route_enabled(a.transport,raw):return http_post(route,data,raw)
   t0=time.perf_counter();body=json.dumps(data,separators=(',',':')).encode();t1=time.perf_counter()
   reply=transport_state.request(route,data,False);t2=time.perf_counter()
   if route=='/humanoid/update' and transport_state.effective=='ws':
    json_ms.append((t1-t0)*1000);payload_bytes.append(len(body));post_ms.append((t2-t1)*1000);server_ms.append(reply.get('process_ms',0));details['ws_roundtrip'].append((t2-t1)*1000)
   return reply
 hold=HandHold(a.hand_hold_ms); detection_counts={'hand':0,'pose':0};capture_times={}
 start=time.perf_counter(); count=0; errors=0; filt=OneEuro(); out=None; log=None; cap=None
 if a.record:
  prefix=pathlib.Path(a.record); prefix.parent.mkdir(parents=True,exist_ok=True); log=open(str(prefix)+'.jsonl','w')
 if a.replay:
  for line in open(a.replay):
   row=json.loads(line); target=start+row.get('t',count/30); time.sleep(max(0,target-time.perf_counter()))
   for route,payload in replay_routes(row,a.mode,time.time()):post(route,payload)
   count+=1
   if a.seconds and time.perf_counter()-start>a.seconds:break
  print(json.dumps({'updates':count,'seconds':time.perf_counter()-start}));return
 import mediapipe as mp
 model=pathlib.Path(a.model)
 if not model.exists():
  model.parent.mkdir(parents=True,exist_ok=True); urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',model)
 options=mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_hands=1 if a.mode=='panda' else 2)
 detector=mp.tasks.vision.HandLandmarker.create_from_options(options)
 pool=concurrent.futures.ThreadPoolExecutor(max_workers=2); pose_detector=None; pose_filters={}; infer_times=[]; hand_times=[]; pose_times=[]
 if a.mode!='panda':
  pose_model=pathlib.Path(a.pose_model)
  if not pose_model.exists():
   pose_model.parent.mkdir(parents=True,exist_ok=True);urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',pose_model)
  pose_detector=mp.tasks.vision.PoseLandmarker.create_from_options(mp.tasks.vision.PoseLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(pose_model)),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_poses=1))
 cap=cv2.VideoCapture(a.video) if a.video else cv2.VideoCapture(a.camera,cv2.CAP_MSMF)
 if not a.video:
  cap.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*'MJPG'));cap.set(cv2.CAP_PROP_FRAME_WIDTH,1280);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720);cap.set(cv2.CAP_PROP_FPS,30)
 if not cap.isOpened():
  print(json.dumps({'error':'camera/video cannot open; check USB connection or use --video RECORDING.mp4','camera_test':'not performed when disconnected'}));detector.close();pool.shutdown()
  if pose_detector is not None:pose_detector.close()
  return
 source_fps=(cap.get(cv2.CAP_PROP_FPS) or 30.) if a.video else 30.
 start=time.perf_counter(); preview_at=0; last_stamp=-1
 latest={'frame':None,'seq':0,'stop':False,'capture_at':None,'failed':False}; camera_lock=threading.Lock(); consumed=0
 preview_pending={'jpeg':None};preview_lock=threading.Lock()
 update_pending={'sample':None,'humanoid':None};update_lock=threading.Lock();sent_count=0
 def control_sender():
  nonlocal errors,sent_count
  while not latest['stop'] or update_pending['sample'] is not None or update_pending['humanoid'] is not None:
   with update_lock:sample=update_pending['sample'];hsample=update_pending['humanoid'];update_pending['sample']=None;update_pending['humanoid']=None
   if sample is None and hsample is None:time.sleep(.002);continue
   try:
    for route,payload in update_routes(a.mode,sample,hsample):post(route,payload)
    sent_count+=1
   except Exception as exc:
    errors+=1
    if errors<=3:print(json.dumps({'upload_error':str(exc),'response':getattr(getattr(exc,'response',None),'text','')[:300]}),flush=True)
 update_thread=threading.Thread(target=control_sender,daemon=True);update_thread.start()
 def preview_sender():
  while not latest['stop'] or preview_pending['jpeg'] is not None:
   with preview_lock:jpeg=preview_pending['jpeg'];preview_pending['jpeg']=None
   if jpeg is None:time.sleep(.005);continue
   try:
    if isinstance(jpeg,np.ndarray):
     te=time.perf_counter();ok,encoded=cv2.imencode('.jpg',jpeg,[cv2.IMWRITE_JPEG_QUALITY,65]);preview_encode_ms.append((time.perf_counter()-te)*1000)
     if not ok:continue
     jpeg=encoded.tobytes()
    te=time.perf_counter();post('/teleop/preview',jpeg,raw=True);preview_post_ms.append((time.perf_counter()-te)*1000)
   except Exception:pass
 preview_thread=threading.Thread(target=preview_sender,daemon=True);preview_thread.start()
 def capture_latest():
  while not latest['stop']:
   ok,image=cap.read()
   if not ok:
    latest['failed']=True;break
   with camera_lock:latest['frame']=image;latest['seq']+=1;latest['capture_at']=time.time()
 if not a.video:
  capture_thread=threading.Thread(target=capture_latest,daemon=True);capture_thread.start()
 acquire_index=0
 def acquire_frame():
  nonlocal acquire_index,last_stamp,consumed
  tick=time.perf_counter()
  if a.video:
   ok,frame=cap.read()
   if not ok and a.loop_video:cap.set(cv2.CAP_PROP_POS_FRAMES,0);ok,frame=cap.read()
   if not ok:return None
   frame_capture_at=time.time()
   pacing_start=time.perf_counter();fps=cap.get(cv2.CAP_PROP_FPS) or 30
   time.sleep(max(0,start+acquire_index/fps-time.perf_counter()));stages['pacing'].append((time.perf_counter()-pacing_start)*1000)
  else:
   while not latest['stop']:
    lock_start=time.perf_counter()
    with camera_lock:
     ok=latest['seq']!=consumed;frame=latest['frame'];consumed=latest['seq'];frame_capture_at=latest['capture_at']
    details['capture_lock'].append((time.perf_counter()-lock_start)*1000)
    if ok:break
    if latest['failed'] or (a.seconds and time.perf_counter()-start>=a.seconds):return None
    time.sleep(.002)
   else:return None
  acquire_index+=1;preprocess_start=time.perf_counter()
  frame=cv2.flip(frame,1)
  if frame.shape[:2]!=(360,640):frame=cv2.resize(frame,(640,360))
  stamp=max(last_stamp+1,int((time.perf_counter()-start)*1000));last_stamp=stamp;capture_times[stamp]=frame_capture_at
  infer_t=time.perf_counter();iw=640 if a.mode=='panda' else a.infer_width
  image=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(frame if iw==640 else cv2.resize(frame,(iw,iw*9//16)),cv2.COLOR_BGR2RGB))
  stages['preprocess'].append((time.perf_counter()-preprocess_start)*1000)
  return tick,frame,stamp,image,infer_t
 source_queue=queue.Queue(maxsize=2) if a.pipeline and a.video and a.prefetch_video else None
 source_thread=None
 def prepare_source():
  while not latest['stop']:
   item=acquire_frame()
   while not latest['stop']:
    try:source_queue.put(item,timeout=.05);break
    except queue.Full:pass
   if item is None:break
 if source_queue is not None:
  source_thread=threading.Thread(target=prepare_source,name='video-source',daemon=True);source_thread.start()
 def acquire_infer():
  if source_queue is not None:
   while not latest['stop']:
    try:item=source_queue.get(timeout=.1);break
    except queue.Empty:pass
   else:return None
  else:item=acquire_frame()
  if item is None:return None
  tick,frame,stamp,image,infer_t=item
  infer_t=time.perf_counter();neural_start=infer_t

  def infer_task(task):
   ti=time.perf_counter();r=task.detect_for_video(image,stamp);return r,(time.perf_counter()-ti)*1000
  if pose_detector is not None and not a.serial:
   fh=pool.submit(infer_task,detector);fp=pool.submit(infer_task,pose_detector);result,hm=fh.result();pr,pm=fp.result()
  else:
   result,hm=infer_task(detector);pr=None;pm=0.
   if pose_detector is not None:pr,pm=infer_task(pose_detector)
  hand_times.append(hm)
  if pose_detector is not None:pose_times.append(pm)
  stages['neural'].append((time.perf_counter()-neural_start)*1000)
  return tick,frame,stamp,result,pr,infer_t
 pipeline_pool=concurrent.futures.ThreadPoolExecutor(1) if a.pipeline else None
 pending_inference=pipeline_pool.submit(acquire_infer) if a.pipeline else None
 try:
  while True:
   if a.pipeline:
    data=pending_inference.result()
    if data is None:break
    tick,frame,stamp,result,pr,infer_t=data
    pending_inference=pipeline_pool.submit(acquire_infer)
    record_frame=frame.copy() if a.record else None
    retarget_start=time.perf_counter()
   else:
    tick=time.perf_counter()
    if a.video:ok,frame=cap.read()
    else:
     lock_start=time.perf_counter()
     with camera_lock:
      ok=latest['seq']!=consumed;frame=latest['frame'];consumed=latest['seq'];frame_capture_at=latest['capture_at']
     details['capture_lock'].append((time.perf_counter()-lock_start)*1000)
     if not ok:
      if latest['failed'] or (a.seconds and time.perf_counter()-start>=a.seconds):break
      time.sleep(.002);continue
    if not ok and a.video and a.loop_video:
     cap.set(cv2.CAP_PROP_POS_FRAMES,0);ok,frame=cap.read()
    if not ok:break
    if a.video:frame_capture_at=time.time()
    pacing_start=time.perf_counter()
    if a.video:
     fps=cap.get(cv2.CAP_PROP_FPS) or 30; time.sleep(max(0,start+count/fps-time.perf_counter()))
    stages['pacing'].append((time.perf_counter()-pacing_start)*1000);preprocess_start=time.perf_counter()
    frame=cv2.resize(cv2.flip(frame,1),(640,360)); stamp=max(last_stamp+1,int((time.perf_counter()-start)*1000));last_stamp=stamp;capture_times[stamp]=frame_capture_at
    record_frame=frame.copy() if a.record else None
    infer_t=time.perf_counter()
    iw=640 if a.mode=='panda' else a.infer_width
    image=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(frame if iw==640 else cv2.resize(frame,(iw,iw*9//16)),cv2.COLOR_BGR2RGB))
    def infer(task):
     ti=time.perf_counter();result=task.detect_for_video(image,stamp);return result,(time.perf_counter()-ti)*1000
    stages['preprocess'].append((time.perf_counter()-preprocess_start)*1000);neural_start=time.perf_counter()
    if pose_detector is not None and not a.serial:
     hf=pool.submit(infer,detector);pf=pool.submit(infer,pose_detector)
     result,hm=hf.result();pr,pm=pf.result();hand_times.append(hm);pose_times.append(pm)
    else:
     result,hm=infer(detector);hand_times.append(hm)
     if pose_detector is not None:pr,pm=infer(pose_detector);pose_times.append(pm)
    stages['neural'].append((time.perf_counter()-neural_start)*1000);retarget_start=time.perf_counter()
   detail_start=time.perf_counter();capture_at=capture_times.pop(stamp,time.time());details['timestamp'].append((time.perf_counter()-detail_start)*1000); detection_counts['hand']+=bool(result.hand_landmarks)
   hsample={'detected':False,'sent_at':time.time(),'capture_at':capture_at,'seq':count}
   if pose_detector is not None:
    if pr.pose_world_landmarks:
     pw=np.array([[v.x,v.y,v.z,v.visibility] for v in pr.pose_world_landmarks[0]]);p2=np.array([[v.x,v.y] for v in pr.pose_landmarks[0]])
     pf=pose_filters.get('pose')
     if pf is None:pf=pose_filters['pose']=OneEuro()
     pw[:,:3]=pf(pw[:,:3],time.perf_counter())
     detail_start=time.perf_counter();upper=all(v.visibility>=.3 for v in pr.pose_world_landmarks[0][11:17]);hips=all(pr.pose_world_landmarks[0][i].visibility>=.3 for i in (23,24));details['visibility'].append((time.perf_counter()-detail_start)*1000)
     hsample['quality']={'upper_body_visible':upper,'hips_visible':hips}
     detection_counts['pose']+=1
     hsample.update(detected=upper,pose=pw.tolist(),pose2d=preview_coords(p2),hands={},hands2d={})
     # Global minimum-distance assignment, not handedness labels (mirrored frame).
     candidates=[]
     for hi,h in enumerate(result.hand_landmarks):
      for side,wi in [('left',15),('right',16)]:candidates.append((float(np.linalg.norm(np.array([h[0].x,h[0].y])-p2[wi])),hi,side))
     # At most two hands: exhaustive minimum-sum one-to-one assignment.
     valid=[c for c in candidates if c[0]<=.3]
     pairs=[pair for pair in itertools.combinations(valid,2) if pair[0][1]!=pair[1][1] and pair[0][2]!=pair[1][2]]
     candidates=min(pairs,key=lambda pair:sum(c[0] for c in pair)) if pairs else sorted(valid)[:1]
     used_h=set();used_s=set()
     for distance,hi,side in sorted(candidates):
      if hi in used_h or side in used_s or distance>.3:continue
      used_h.add(hi);used_s.add(side)
      hw=np.array([[v.x,v.y,v.z] for v in result.hand_world_landmarks[hi]])
      hf=pose_filters.get(side)
      if hf is None:hf=pose_filters[side]=OneEuro()
      hsample['hands'][side]=hf(hw,time.perf_counter()).tolist();hsample['hands2d'][side]=preview_coords([[v.x,v.y] for v in result.hand_landmarks[hi]])
     detail_start=time.perf_counter();pose_uv=(p2*[640,360]).astype(int)
     for u,v in [(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24)]:cv2.line(frame,tuple(pose_uv[u]),tuple(pose_uv[v]),(90,230,90),2)
     details['pose_overlay'].append((time.perf_counter()-detail_start)*1000)
   if pose_detector is not None:
    detail_start=time.perf_counter();hold.apply(hsample,detail_start);details['hold_quality'].append((time.perf_counter()-detail_start)*1000)
   infer_times.append((time.perf_counter()-infer_t)*1000)
   stages['retarget'].append((time.perf_counter()-retarget_start)*1000);overlay_start=time.perf_counter()
   sample={'detected':False}; points=[];detail_start=time.perf_counter()
   if result.hand_landmarks and (a.mode!='humanoid' or log is not None):
    points=[[q.x,q.y,q.z] for q in result.hand_landmarks[0]]; pts=np.array(points); scale=max(.001,float(np.linalg.norm(pts[0,:2]-pts[9,:2]))); center=pts[[0,5,9,13,17],:2].mean(axis=0); pinch=float(np.linalg.norm(pts[4,:2]-pts[8,:2])/scale)
    values=filt([*center,scale,pinch],time.perf_counter()); sample=dict(detected=True,x=float(np.clip(values[0],0,1)),y=float(np.clip(values[1],0,1)),scale=float(values[2]),pinch=float(max(0,values[3])))
    h,w=frame.shape[:2]; uv=(pts[:,:2]*[w,h]).astype(int)
    for chain in ([0,1,2,3,4],[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20],[5,9,13,17]):
     for u,v in zip(chain,chain[1:]):cv2.line(frame,tuple(uv[u]),tuple(uv[v]),(0,230,90),2)
    for x,y in uv:cv2.circle(frame,(x,y),3,(240,130,0),-1)
   details['panda_features_overlay'].append((time.perf_counter()-detail_start)*1000);detail_start=time.perf_counter()
   for hand in result.hand_landmarks:
    uvh=(np.array([[v.x,v.y] for v in hand])*[640,360]).astype(int)
    for chain in ([0,1,2,3,4],[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20],[5,9,13,17]):
     for u,v in zip(chain,chain[1:]):cv2.line(frame,tuple(uvh[u]),tuple(uvh[v]),(0,230,90),1)
    for tip,color in zip([4,8,12,16,20],[(107,107,255),(64,204,255),(115,217,77),(250,165,96),(252,132,192)]):cv2.circle(frame,tuple(uvh[tip]),6,color,-1)
    cv2.circle(frame,tuple(uvh[[0,5,9,13,17]].mean(axis=0).astype(int)),2,(255,255,255),-1)
   details['hand_overlay'].append((time.perf_counter()-detail_start)*1000)
   sample['sent_at']=time.time();sample['capture_at']=capture_at;sample['seq']=count
   stages['overlay'].append((time.perf_counter()-overlay_start)*1000);queue_start=time.perf_counter()
   try:
    with update_lock:update_pending['sample']=sample;update_pending['humanoid']=hsample if a.mode!='panda' else None
    if True:  # one preview per processed frame, no old 20 Hz cap
     if a.mode=='panda':
      _,jpeg=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,65]);pending=jpeg.tobytes()
     else:pending=frame  # latest-only immutable frame, encode on preview sender thread
     with preview_lock:preview_pending['jpeg']=pending
     preview_at=time.perf_counter()
   except Exception:errors+=1
   stages['queue'].append((time.perf_counter()-queue_start)*1000)
   if log:log.write(json.dumps(dict(recording_row(time.perf_counter()-start,count,capture_at,a.mode,sample,hsample if a.mode!='panda' else None,points),capture_t=capture_at-(time.time()-time.perf_counter()+start)))+'\n');log.flush()
   if a.record:
    if out is None:out=cv2.VideoWriter(str(prefix)+'.mp4',cv2.VideoWriter_fourcc(*'mp4v'),30,(frame.shape[1],frame.shape[0]))
    out.write(record_frame)
   loop_ms.append((time.perf_counter()-tick)*1000)
   count+=1
   if a.seconds and time.perf_counter()-start>=a.seconds:break
   if not a.video:time.sleep(max(0,1/30-(time.perf_counter()-tick)))
 finally:
  processing_seconds=time.perf_counter()-start
  source_frames_due=int(math.floor(processing_seconds*source_fps))+1 if a.video else latest['seq']
  latest['stop']=True
  preview_thread.join(timeout=1);update_thread.join(timeout=1)
  if not a.video:capture_thread.join(timeout=2)
  if pipeline_pool:pipeline_pool.shutdown()
  if source_thread:source_thread.join(timeout=1)
  cap.release();pool.shutdown();detector.close()
  if pose_detector is not None:pose_detector.close()
  if out:out.release()
  if log:log.close()
 metrics={'detail_ms':{k:{'p50':float(np.median(v)),'p95':float(np.percentile(v,95)),'n':len(v)} for k,v in details.items() if v},'transport':transport_state.effective if transport_state else 'http','transport_requested':a.transport,'transport_fallback':bool(transport_state and transport_state.fallback),'preview_transport':'http','http_client':a.http_client,'hand_detection_rate':detection_counts['hand']/max(1,count),'pose_detection_rate':detection_counts['pose']/max(1,count),'camera_read_failed':latest['failed'],'capture_clock':'unix wall clock at decode completion/video or read completion/camera','stages_ms':{k:{'p50':float(np.median(v)),'p95':float(np.percentile(v,95))} for k,v in stages.items() if v},'source_fps':source_fps,'source_frames_due':source_frames_due,'processed_input_ratio':count/max(1,source_frames_due),'unprocessed_source_slots':max(0,source_frames_due-count),'dropped_frames':0 if a.video else max(0,source_frames_due-count),'updates':count,'seconds':round(processing_seconds,3),'hz':round(count/processing_seconds,3),'network_errors':errors,'sent_updates':sent_count,'preview_sent':len(preview_post_ms),'preview_encode_ms_p50':float(np.median(preview_encode_ms)) if preview_encode_ms else None,'preview_post_ms_p50':float(np.median(preview_post_ms)) if preview_post_ms else None,'post_ms_p50':float(np.median(post_ms)) if post_ms else None,'post_ms_p95':float(np.percentile(post_ms,95)) if post_ms else None,'json_ms_p50':float(np.median(json_ms)) if json_ms else None,'payload_bytes_p50':float(np.median(payload_bytes)) if payload_bytes else None,'server_ms_p50':float(np.median(server_ms)) if server_ms else None,'loop_ms_p50':float(np.median(loop_ms)) if loop_ms else None,'inference_ms_p50':float(np.median(infer_times)) if infer_times else None,'inference_ms_p95':float(np.percentile(infer_times,95)) if infer_times else None,'hand_ms_p50':float(np.median(hand_times)) if hand_times else None,'pose_ms_p50':float(np.median(pose_times)) if pose_times else None}
 print(json.dumps(metrics))
 if a.metrics_out:pathlib.Path(a.metrics_out).write_text(json.dumps(metrics,indent=2),encoding='utf8')
if __name__=='__main__':main()
