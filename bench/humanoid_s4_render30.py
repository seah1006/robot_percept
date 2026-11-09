"""포트5093, 패턴별30초 JPEG 개수. 외부 measure→GPU 락, GT보조."""
import os,sys,time,json,subprocess,threading,socket,urllib.request
from pathlib import Path
from tools import humanoid_synth as hs
from bench.humanoid_s3_profile import frame_for
OUT=Path('bench/humanoid_s4_out/round5');OUT.mkdir(exist_ok=True)
URL='http://127.0.0.1:5093'
def req(path,body=None):
 data=None if body is None else json.dumps(body).encode()
 with urllib.request.urlopen(urllib.request.Request(URL+path,data=data,headers={'Content-Type':'application/json'}),timeout=15) as r:return json.loads(r.read())
def main():
 with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',5093))!=0,'5093 busy'
 env=dict(os.environ,PORT='5093',HOST='127.0.0.1',PERCEPTION='stub',RP_PERCEPTION_WARMUP='0')
 stop=threading.Event();errors=[];active={'pattern':'sweep','at':time.monotonic()};rows=[];old=hs.frame
 log=(OUT/'render_server.log').open('w');proc=subprocess.Popen([sys.executable,'-m','web.app'],env=env,stdout=log,stderr=log)
 def sender():
  deadline=time.monotonic();i=0
  while not stop.is_set():
   hs.frame=lambda t:frame_for(active['pattern'],t)
   p,_=hs.payload(time.monotonic()-active['at'])
   try:req('/humanoid/update',p)
   except Exception as e:errors.append(type(e).__name__)
   i+=1;deadline+=1/30
   while not stop.is_set() and time.monotonic()<deadline:time.sleep(min(.005,max(0,deadline-time.monotonic())))
 try:
  end=time.monotonic()+45
  while time.monotonic()<end:
   try:req('/humanoid/status');break
   except Exception:
    if proc.poll() is not None:raise RuntimeError('server exited')
    time.sleep(.1)
  req('/humanoid/mode',{'enabled':True});req('/humanoid/options',{'collision_avoidance':True,'safety_brake':True})
  thread=threading.Thread(target=sender,daemon=True);thread.start()
  for pattern in ('sweep','chest','jump','twist'):
   active.update(pattern=pattern,at=time.monotonic());time.sleep(3)
   arrivals=[];buf=b'';begin=time.monotonic();finish=begin+30
   with urllib.request.urlopen(URL+'/humanoid/video',timeout=12) as response:
    while time.monotonic()<finish:
     buf+=response.read1(65536)
     while True:
      a=buf.find(b'\xff\xd8');b=buf.find(b'\xff\xd9',a+2) if a>=0 else -1
      if b<0:break
      at=time.monotonic()
      if at<finish:arrivals.append(at)
      buf=buf[b+2:]
   status=req('/humanoid/status')
   row=dict(pattern=pattern,window_s=30.,frames=len(arrivals),fps_count=len(arrivals)/30,arrivals_mono=arrivals,status=status,errors=list(errors));rows.append(row)
   (OUT/'render30.json').write_text(json.dumps(dict(GT_auxiliary=True,load=Path('/proc/loadavg').read_text(),patterns=rows),indent=2));print(json.dumps({k:v for k,v in row.items() if k not in ('arrivals_mono','status')}),flush=True)
 finally:
  stop.set();hs.frame=old
  if 'thread' in locals():thread.join(timeout=2)
  try:req('/humanoid/mode',{'enabled':False})
  except Exception:pass
  if proc.poll() is None:proc.terminate()
  try:proc.wait(timeout=7)
  except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)
  log.close()
if __name__=='__main__':main()