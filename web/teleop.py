import math,time,threading
from collections import deque
from flask import Blueprint,request,jsonify,Response

def create_blueprint(runtime):
 bp=Blueprint('teleop',__name__); st=runtime.status; preview={'jpeg':None,'seq':0}; mutex=threading.Condition(); times=deque(maxlen=90); preview_times=deque(maxlen=90); counts={'input':0}
 @bp.post('/teleop/update')
 def update():
  if request.content_length and request.content_length>8192:return jsonify(error='payload too large'),413
  data=request.get_json(silent=True)
  if not isinstance(data,dict):return jsonify(error='JSON object required'),400
  detected=data.get('detected',False)
  if not isinstance(detected,bool):return jsonify(error='detected must be boolean'),400
  sample={'detected':detected,'received_at':time.time()}
  if detected:
   for key,lo,hi in [('x',0,1),('y',0,1),('scale',.001,2),('pinch',0,10)]:
    value=data.get(key)
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not lo<=value<=hi:return jsonify(error='invalid '+key),400
    sample[key]=float(value)
  sent=data.get('sent_at')
  if isinstance(sent,(float,int)) and math.isfinite(sent):sample['latency_ms']=max(0,min(60000,(time.time()-sent)*1000))
  st['teleop_sample']=sample
  with mutex:times.append(time.monotonic());counts['input']+=1
  return jsonify(ok=True)
 @bp.post('/teleop/mode')
 def mode():
  data=request.get_json(silent=True)
  if not isinstance(data,dict):return jsonify(error='JSON object required'),400
  enabled=data.get('enabled')
  if not isinstance(enabled,bool):return jsonify(error='enabled must be boolean'),400
  if enabled and (st.get('active_command') or st.get('held_object')):return jsonify(error='busy or holding object'),409
  st['teleop_enabled']=enabled
  if enabled:st['teleop_neutral']=None
  return jsonify(ok=True,enabled=enabled)
 @bp.post('/teleop/calibrate')
 def calibrate():
  sample=st.get('teleop_sample',{})
  if not sample.get('detected') or time.time()-sample.get('received_at',0)>.3:return jsonify(error='no fresh hand'),409
  st['teleop_neutral']=sample; st['teleop_calibration']=time.time(); return jsonify(ok=True)
 @bp.get('/teleop/status')
 def status():
  sample=st.get('teleop_sample',{}); age=time.time()-sample.get('received_at',0)
  with mutex:
   recent=[t for t in times if time.monotonic()-t<2]
   precent=[t for t in preview_times if time.monotonic()-t<2]
   input_count=counts['input'];preview_count=preview['seq']
  hz=(len(recent)-1)/(recent[-1]-recent[0]) if len(recent)>1 else 0
  phz=(len(precent)-1)/(precent[-1]-precent[0]) if len(precent)>1 else 0
  return jsonify(input_count=input_count,preview_count=preview_count,preview_hz=round(phz,1),sample={k:sample.get(k) for k in ('x','y','scale','pinch')},neutral=st.get('teleop_neutral'),origin=st.get('teleop_origin'),camera_K=st.get('camera_K'),T_world_cam=st.get('T_world_cam'),enabled=bool(st.get('teleop_enabled')),detected=bool(sample.get('detected') and 0<=age<.3),hz=round(hz,1),latency_ms=round(sample.get('latency_ms',0),1),age_ms=round(min(age*1000,60000)),error=st.get('teleop_error'),rtf=st.get('rtf'),servo_ticks=st.get('teleop_ticks',0),sim_time=st.get('sim_time'),target=st.get('teleop_target'),closed=bool(st.get('teleop_closed')))
 @bp.post('/teleop/preview')
 def preview_post():
  if not request.content_length or request.content_length>250000:return jsonify(error='JPEG size limit 250KB'),413
  raw=request.get_data()
  if not raw.startswith(b'\xff\xd8') or not raw.endswith(b'\xff\xd9'):return jsonify(error='JPEG required'),400
  with mutex:
   preview['jpeg']=raw;preview['seq']+=1;preview_times.append(time.monotonic());mutex.notify_all()
  return jsonify(ok=True)
 @bp.get('/teleop/preview.mjpg')
 def preview_stream():
  def frames():
   seq=-1
   while True:
    with mutex:
     mutex.wait_for(lambda:preview['seq']!=seq,timeout=2)
     raw=preview['jpeg'];next_seq=preview['seq']
    if raw is None or next_seq==seq:continue
    seq=next_seq
    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+raw+b'\r\n'
  return Response(frames(),mimetype='multipart/x-mixed-replace; boundary=frame',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
 @bp.get('/teleop/preview.jpg')
 def preview_get():
  with mutex:raw=preview['jpeg']
  return Response(raw or b'',status=200 if raw else 204,mimetype='image/jpeg',headers={'Cache-Control':'no-store'})
 return bp
