"""Own port 5091 only. Run under measure -> gpu locks, maximum 290 seconds."""
import json,os,time,threading,subprocess,re,urllib.request,urllib.error,signal,gc
from tools.humanoid_synth import payload
from web.shm_channel import wait_monotonic
URL='http://127.0.0.1:5091'
def interrupted(sig,frame):raise KeyboardInterrupt()
signal.signal(signal.SIGTERM,interrupted)
def req(path,body=None):
 data=None if body is None else json.dumps(body).encode()
 with urllib.request.urlopen(urllib.request.Request(URL+path,data=data,headers={'Content-Type':'application/json'}),timeout=12) as r:return json.loads(r.read())
def main():
 client_gc=[];gc_started={}
 def trace_gc(phase,info):
  generation=info.get('generation',-1)
  if phase=='start':gc_started[generation]=(time.monotonic(),time.process_time())
  elif generation in gc_started:
   start,cpu=gc_started.pop(generation);elapsed=(time.monotonic()-start)*1000
   if elapsed>50:client_gc.append({'at_mono':time.monotonic(),'wall_ms':elapsed,'cpu_ms':(time.process_time()-cpu)*1000,'generation':generation})
 gc.callbacks.append(trace_gc)
 if os.environ.get('RP_STALL_PRERUN','1')=='1':
  from bench.humanoid_s_round2 import dynamic_actual
  print('DEFAULT_ON_CAPS='+json.dumps(dynamic_actual()),flush=True)
 assert not subprocess.check_output(['ss','-ltnp','sport = :5091'],text=True).splitlines()[1:],'5091 already in use'
 env=dict(os.environ,PORT='5091',HOST='0.0.0.0',PERCEPTION='stub');log=open('/tmp/humanoid_s_5091.log','w');proc=subprocess.Popen(['python','-m','web.app'],env=env,stdout=log,stderr=log);stop=threading.Event();errors=[];stats=[];status_records=[]
 try:
  for _ in range(180):
   try:req('/humanoid/status');break
   except Exception:time.sleep(.5)
  req('/humanoid/mode',{'enabled':True})
  for _ in range(180):
   st=req('/humanoid/status')
   if st.get('state')=='ready':break
   time.sleep(.5)
  assert st.get('state')=='ready',st
  options={'safety_brake':True}
  if os.environ.get('RP_COLLISION_TEST')=='1':options['collision_avoidance']=True
  req('/humanoid/options',options)
  def stream():
   t0=time.monotonic();i=0
   while not stop.is_set():
    p,_=payload((i/30)%20);p['sent_at']=time.time()
    try:req('/humanoid/update',p)
    except Exception as x:errors.append(str(x))
    i+=1;wait_monotonic(stop,max(0,t0+i/30-time.monotonic()))
  def poll():
   while not wait_monotonic(stop,.1):
    try:
     request_start=time.monotonic();status=req('/humanoid/status');received=time.monotonic()
     stats.append(status);status_records.append(dict(received_mono=received,http_ms=(received-request_start)*1000,status=status))
    except Exception as x:errors.append(str(x))
  threading.Thread(target=stream,daemon=True).start();threading.Thread(target=poll,daemon=True).start();time.sleep(3.)
  times=[];buf=b'';t0=time.monotonic()
  with urllib.request.urlopen(URL+'/humanoid/video',timeout=12) as response:
   while time.monotonic()-t0<30:
    buf+=response.read1(65536)
    while True:
     a=buf.find(b'\xff\xd8');b=buf.find(b'\xff\xd9',a+2) if a>=0 else -1
     if b<0:break
     times.append(time.monotonic());buf=buf[b+2:]
  stop.set();import numpy as np
  ik=[s['ik'][z]['time_ms'] for s in stats for z in ('left','right') if s.get('ik',{}).get(z) and 'time_ms' in s['ik'][z]]
  pair=[s.get('ik_ms_p95') for s in stats if s.get('ik_ms_p95') is not None]
  ticks=[s['tick_ms_p95'] for s in stats if s.get('tick_ms_p95') is not None]
  out=dict(load=open('/proc/loadavg').read().strip(),frames=len(times),window_s=times[-1]-times[0],fps=(len(times)-1)/(times[-1]-times[0]),max_gap_ms=float(np.max(np.diff(times))*1000),individual_ik_p95_ms=float(np.percentile(ik,95)) if ik else None,paired_ik_p95_max_ms=max(pair) if pair else None,tick_p95_max_ms=max(ticks) if ticks else None,safety_brake=stats[-1].get('options',{}).get('safety_brake'),root_safety_brake=stats[-1].get('safety_brake'),collision_state=stats[-1].get('collision_state'),servo_profile=stats[-1].get('servo_profile'),collision_options=stats[-1].get('options',{}).get('collision_avoidance'),errors=errors)
  from pathlib import Path
  tag=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+('_on' if os.environ.get('RP_COLLISION_TEST')=='1' else '_off')
  base=Path('bench/humanoid_w_stall_out')/('render_'+tag);base.parent.mkdir(exist_ok=True)
  status_path=base.with_suffix('.jsonl');arrival_path=base.with_suffix('.arrivals.json')
  status_path.write_text(''.join(json.dumps(row)+'\n' for row in status_records))
  arrival_path.write_text(json.dumps(dict(window_begin_mono=t0,window_end_mono=time.monotonic(),arrivals_mono=times)))
  out.update(raw_status=str(status_path),raw_arrivals=str(arrival_path),client_gc_events=client_gc,client_pid=os.getpid())
  print(json.dumps(out),flush=True)
 finally:
  stop.set()
  try:req('/humanoid/mode',{'enabled':False})
  except Exception:pass
  listener=subprocess.check_output(['ss','-ltnp','sport = :5091'],text=True)
  if re.search(r'pid='+str(proc.pid)+r'[,)]',listener):proc.terminate()
  try:proc.wait(timeout=15)
  except subprocess.TimeoutExpired:pass
  log.close()
  if trace_gc in gc.callbacks:gc.callbacks.remove(trace_gc)
if __name__=='__main__':main()