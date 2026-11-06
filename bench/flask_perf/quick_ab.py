import json,time,threading,statistics,http.client,urllib.parse,os,sys
import urllib3,websocket
URL='http://127.0.0.1:5093'; WS='ws://127.0.0.1:5093'
D=os.environ.get('RP_FLASK_PAYLOAD','/tmp/rp_flask_payload');pl=json.load(open(os.path.join(D,'payloads.json')));jpg=open(os.path.join(D,'preview.jpg'),'rb').read()
def pct(v,q):return round(sorted(v)[min(len(v)-1,int(len(v)*q))],3)
def run_transport(kind,dur=10):
 vals={'update':[],'preview':[]}; errs=[];t0=time.perf_counter()
 def loop(name):
  n=0;use_ws=kind=='ws' or (kind=='hybrid' and name=='update');pool=urllib3.PoolManager(num_pools=1,maxsize=1) if not use_ws else None;ws=websocket.create_connection(WS+'/tracker/ws',timeout=2) if use_ws else None
  while time.perf_counter()-t0<dur:
   data=jpg if name=='preview' else dict(pl[n%len(pl)],sent_at=time.time(),capture_at=time.time(),seq=n)
   a=time.perf_counter()
   try:
    if not use_ws:
     route='/teleop/preview' if name=='preview' else '/humanoid/update';body=data if name=='preview' else json.dumps(data,separators=(',',':')).encode();r=pool.request('POST',URL+route,body=body,headers={'Content-Type':'image/jpeg' if name=='preview' else 'application/json'},timeout=.6,retries=False);r.read();code=r.status
    else:
     ws.send_binary(data) if name=='preview' else ws.send(json.dumps({'route':'/humanoid/update','data':data},separators=(',',':')));code=json.loads(ws.recv())['status']
    if code<400:vals[name].append((time.perf_counter()-a)*1000)
    else:errs.append(code)
   except Exception as e:errs.append(type(e).__name__)
   n+=1;d=t0+n/30-time.perf_counter()
   if d>0:time.sleep(d)
  if ws:ws.close()
 th=[threading.Thread(target=loop,args=(x,)) for x in vals]
 [x.start() for x in th];[x.join() for x in th]
 return {'transport':kind,'errors':errs,'update':{'n':len(vals['update']),'p50':pct(vals['update'],.5),'p95':pct(vals['update'],.95)},'preview':{'n':len(vals['preview']),'p50':pct(vals['preview'],.5),'p95':pct(vals['preview'],.95)}}
def cpu_ticks(pid):
 f=open(f'/proc/{pid}/stat').read().rsplit(')',1)[1].split();return int(f[11])+int(f[12])
def run_status(kind,pid,dur=10):
 start=cpu_ticks(pid);t0=time.monotonic();count=0
 if kind=='poll':
  stop=False
  def loop(path,hz):
   nonlocal count
   c=http.client.HTTPConnection('127.0.0.1',5093,timeout=3);n=0
   while time.monotonic()-t0<dur:
    try:c.request('GET',path);r=c.getresponse();r.read();count+=1
    except Exception:c.close();c=http.client.HTTPConnection('127.0.0.1',5093,timeout=3)
    n+=1;time.sleep(max(0,t0+n/hz-time.monotonic()))
  th=[threading.Thread(target=loop,args=x) for x in [('/status',3),('/teleop/status',10),('/humanoid/status',10)]];[x.start() for x in th];[x.join() for x in th]
 else:
  w=websocket.create_connection(WS+'/status/ws',timeout=3)
  while time.monotonic()-t0<dur:
   try:w.settimeout(max(.1,dur-(time.monotonic()-t0)));w.recv();count+=1
   except Exception:break
  w.close()
 elapsed=time.monotonic()-t0;cpu=(cpu_ticks(pid)-start)/os.sysconf('SC_CLK_TCK')/elapsed*100
 return {'status':kind,'messages_or_requests':count,'rate':round(count/elapsed,2),'server_main_cpu_pct':round(cpu,2)}
if __name__=='__main__':
 pid=int(sys.argv[1]);out=[]
 for kind in ['http','hybrid','http','hybrid']:out.append(run_transport(kind))
 for kind in ['poll','push','poll','push']:out.append(run_status(kind,pid))
 print(json.dumps(out,indent=2))
