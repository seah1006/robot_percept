"""Own measure->gpu externally. Operational warmup uses no coordination locks."""
import os,time,json,threading,requests,atexit,subprocess
import numpy as np
from werkzeug.serving import make_server
from tools.humanoid_synth import payload
from web.shm_channel import wait_monotonic
BASE='http://127.0.0.1:5091'
def next_input_deadline(previous, now, period=1/30):
 deadline=previous+period
 return (now+period,True) if deadline<now else (deadline,False)
def main():
 os.environ.update(PERCEPTION='fp',RP_PERCEPTION_WARMUP='0',RP_GPU_SERIALIZE='0')
 from web.app import create_app
 app=create_app();rt=app.extensions['sim_runtime'];hr=app.blueprints['humanoid'].humanoid_runtime
 server=make_server('0.0.0.0',5091,app,threaded=True);threading.Thread(target=server.serve_forever,daemon=True).start()
 stop=threading.Event();sending=threading.Event();sending.set();times=[];input_result={'sent':0,'errors':0,'pacing_resets':0}
 def send():
  t0=time.monotonic();deadline=t0
  while not stop.is_set():
   if not wait_monotonic(sending,.1):deadline=time.monotonic();continue
   p,_=payload((time.monotonic()-t0)%20)
   try:requests.post(BASE+'/humanoid/update',json=p,timeout=2).raise_for_status();input_result['sent']+=1
   except Exception:input_result['errors']+=1
   now=time.monotonic();deadline,reset=next_input_deadline(deadline,now)
   input_result['pacing_resets']+=int(reset)
   wait_monotonic(stop,max(0,deadline-now))
 def receive():
  try:
   with requests.get(BASE+'/humanoid/video',stream=True,timeout=4) as r:
    buf=b''
    for chunk in r.iter_content(4096):
     buf+=chunk
     while b'\xff\xd9' in buf:
      _,buf=buf.split(b'\xff\xd9',1);times.append(time.monotonic())
     if stop.is_set():return
  except Exception:pass
 def window(start,end):
  x=[t for t in times if start<=t<end];gaps=[b-a for a,b in zip(x,x[1:])]
  return {'fp_worker_started':rt.perception.proc is not None and rt.perception.proc.is_alive(),'first_frame_delay_ms':None if not x else (x[0]-start)*1000,'long_gaps':[{'at_s':a-start,'ms':(b-a)*1000} for a,b in zip(x,x[1:]) if b-a>.1],'seconds':end-start,'frames':len(x),'fps':len(x)/(end-start),'max_gap_ms':max(gaps or [0])*1000,'status':hr.status(),'load':os.getloadavg(),'gpu':subprocess.getoutput('nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader')}
 try:
  deadline=time.monotonic()+60
  while not rt.status.get('ready'):
   if time.monotonic()>deadline:raise RuntimeError('Panda startup timeout')
   time.sleep(.1)
  if os.getenv('RP_WARMUP_GUARD_ONLY','0')=='1':
   os.environ['RP_PERCEPTION_WARMUP']='1';rt.warmup_loop()
   if getattr(rt.perception,'warmup_state',None)!='ready':raise RuntimeError('guard warmup failed')
   scene=requests.get(BASE+'/status').json();uv=scene['objects']['mustard']['center_px'];t_click=time.monotonic()
   clicked=requests.post(BASE+'/click',json={'x':uv[0],'y':uv[1]},timeout=30);body=clicked.json();click_seconds=time.monotonic()-t_click
   before=requests.get(BASE+'/status').json().get('selected_object');pid_before=rt.perception.proc.pid
   on=requests.post(BASE+'/humanoid/mode',json={'enabled':True},timeout=75)
   after=requests.get(BASE+'/status').json().get('selected_object');alive=rt.perception.proc is not None and rt.perception.proc.is_alive();pid_after=rt.perception.proc.pid if alive else None
   print(json.dumps({'definition':'real object selected immediately before G1 ON; preserve selected object and FP worker','click_http':clicked.status_code,'click_ok':body.get('ok'),'click_seconds':click_seconds,'selected_before':before,'selected_after':after,'mode_http':on.status_code,'worker_pid_before':pid_before,'worker_pid_after':pid_after,'worker_alive':alive,'preserved':bool(before and before==after and pid_before==pid_after and alive),'load':os.getloadavg()}),flush=True)
   return
  requests.post(BASE+'/humanoid/mode',json={'enabled':True},timeout=75).raise_for_status()
  safety_api={'default':requests.get(BASE+'/humanoid/status').json().get('safety_brake')}
  for enabled in (False,True):
   response=requests.post(BASE+'/humanoid/options',json={'safety_brake':enabled},timeout=3);response.raise_for_status();until=time.monotonic()+3
   while True:
    state=requests.get(BASE+'/humanoid/status',timeout=3).json()
    if state.get('safety_brake')==enabled and state.get('options',{}).get('safety_brake')==enabled:break
    if time.monotonic()>until:raise RuntimeError('safety_brake actual status mismatch')
    time.sleep(.02)
   safety_api[str(enabled)]=state['safety_brake']
  safety_api['invalid_http']=requests.post(BASE+'/humanoid/options',json={'safety_brake':'false'}).status_code
  threading.Thread(target=send,daemon=True).start();threading.Thread(target=receive,daemon=True).start()
  time.sleep(5);t=time.monotonic();time.sleep(30);baseline=window(t,t+30)
  rgb,depth,_=rt.frame();st=dict(rt.status);meshes={name:{'mesh':info['mesh']} for name,info in st['objects'].items()}
  os.environ['RP_PERCEPTION_WARMUP']='1';warm_start=time.monotonic();defer_test=os.getenv('RP_WARMUP_DEFER_TEST','0')=='1';deferred_state=None
  start_then_on=os.getenv('RP_WARMUP_START_THEN_G1','0')=='1';reentry_ready_ms=None
  recovery_1s=None;cancel_result=None;first_click=None;resume_seconds=None
  if start_then_on:
   sending.clear();requests.post(BASE+'/humanoid/mode',json={'enabled':False},timeout=15).raise_for_status()
   worker=rt.perception.warmup_async(rgb,depth,np.asarray(st['camera_K']),meshes);time.sleep(2)
   original_pid=rt.perception.proc.pid if rt.perception.proc is not None else None
   if worker is None or not worker.is_alive() or original_pid is None:raise RuntimeError('warmup was not active before G1 ON')
   reentry_t0=time.monotonic();requests.post(BASE+'/humanoid/mode',json={'enabled':True},timeout=75).raise_for_status();reentry_ready_ms=(time.monotonic()-reentry_t0)*1000
   sending.set();threading.Thread(target=receive,daemon=True).start();warm_start=time.monotonic()
   time.sleep(1);recovery_1s=window(warm_start,warm_start+1)
   time.sleep(max(0,warm_start+30-time.monotonic()));during=window(warm_start,warm_start+30)
   cancel_result={'original_pid':original_pid,'thread_joined':not worker.is_alive(),'worker_absent':rt.perception.proc is None,'state':getattr(rt.perception,'warmup_state',None),'closed':rt.perception.closed,'pending':getattr(rt.perception,'warmup_g1_cancel_pending',None)}
   sending.clear();requests.post(BASE+'/humanoid/mode',json={'enabled':False},timeout=15).raise_for_status();resume_t0=time.monotonic()
   while getattr(rt.perception,'warmup_state',None)!='ready':
    if time.monotonic()-resume_t0>100:raise RuntimeError('automatic warmup restart did not become ready within 100s')
    time.sleep(.05)
   resume_seconds=time.monotonic()-resume_t0
   scene=requests.get(BASE+'/status').json();uv=scene['objects']['mustard']['center_px'];click_t0=time.monotonic()
   click=requests.post(BASE+'/click',json={'x':uv[0],'y':uv[1]},timeout=30);body=click.json()
   first_click={'http':click.status_code,'ok':body.get('ok'),'seconds':time.monotonic()-click_t0,'error':body.get('error'),'object':body.get('object')}
   with rt.perception_lock:rt.drop();rt.perception.call('drop')
   requests.post(BASE+'/humanoid/mode',json={'enabled':True},timeout=75).raise_for_status()
   sending.set();threading.Thread(target=receive,daemon=True).start();time.sleep(5)
  elif defer_test:
   worker=threading.Thread(target=rt.warmup_loop,daemon=True);worker.start();time.sleep(30)
   during=window(warm_start,warm_start+30);deferred_state=getattr(rt.perception,'warmup_state',None)
   sending.clear()
   requests.post(BASE+'/humanoid/mode',json={'enabled':False},timeout=15).raise_for_status()
   worker.join(timeout=100)
   if worker.is_alive():raise RuntimeError('deferred warmup did not finish within 100s')
   requests.post(BASE+'/humanoid/mode',json={'enabled':True},timeout=75).raise_for_status()
   sending.set();threading.Thread(target=receive,daemon=True).start();time.sleep(5)
  else:
   worker=rt.perception.warmup_async(rgb,depth,np.asarray(st['camera_K']),meshes)
   if worker is not None:
    worker.join(timeout=100)
    if worker.is_alive():raise RuntimeError('warmup did not finish within 100s')
   warm_end=time.monotonic();during=window(warm_start,warm_end)
  t=time.monotonic();time.sleep(30);after=window(t,t+30)
  out={'definition':'real FP Flask Runtime, automatic warmup disabled; external harness owns measure->gpu, RP_GPU_SERIALIZE=0 manual backend warmup trigger with real RGB-D/K and mesh-only objects','baseline':baseline,'during':during,'after':after,'fp_worker_nice':os.getpriority(os.PRIO_PROCESS,rt.perception.proc.pid) if rt.perception.proc is not None and rt.perception.proc.is_alive() else None,'fp_cpu_threads_requested':os.getenv('RP_PERCEPTION_CPU_THREADS'),'safety_api':safety_api,'recovery_1s':recovery_1s,'cancel_result':cancel_result,'resume_seconds':resume_seconds,'first_click':first_click,'start_then_on':start_then_on,'reentry_ready_ms':reentry_ready_ms,'g1_cpu_nice_applied':getattr(rt.perception,'warmup_g1_nice_applied',None),'g1_priority_error':getattr(rt.perception,'warmup_priority_error',None),'defer_test':defer_test,'deferred_state':deferred_state,'during_definition':'warmup-only FP worker cancelled on G1 ON; automatic restart and first click after OFF' if start_then_on else ('G1-on deferred window; actual warmup starts only after G1 off' if defer_test else 'FP warmup and G1 overlap'),'warmup_state':getattr(rt.perception,'warmup_state',None),'warmup_seconds':getattr(rt.perception,'warmup_seconds',None),'warmup_error':getattr(rt.perception,'warmup_error',None),'input':input_result}
  print(json.dumps(out),flush=True)
 finally:
  stop.set();hr.close();server.shutdown();server.server_close();atexit.unregister(hr.close);atexit.unregister(rt.close);rt.close()
if __name__=='__main__':main()