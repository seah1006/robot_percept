"""Camera acceptance; --video --dry-run is not physical camera acceptance."""
import argparse,json,pathlib,subprocess,sys,time,threading,urllib.request,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

def get(url):
 try:
  with urllib.request.urlopen(url,timeout=1) as r:return json.load(r)
 except Exception:return {}

def main():
 p=argparse.ArgumentParser();p.add_argument('--video');p.add_argument('--dry-run',action='store_true');p.add_argument('--seconds',type=float,default=30);p.add_argument('--warmup',type=float,default=2);p.add_argument('--camera',type=int,default=0);p.add_argument('--url',default='http://127.0.0.1:5095');p.add_argument('--mode',choices=['humanoid','panda'],default='humanoid');p.add_argument('--output',default='camera_acceptance.json');a=p.parse_args()
 if a.seconds<=0 or a.warmup<0:p.error('--seconds positive, warmup nonnegative required')
 if ':5080' in a.url:p.error('user server 5080 forbidden')
 if a.dry_run and not a.video:p.error('--dry-run requires --video')
 arrivals=[];latencies=[];previews=[];server=None;observations=[];stop=threading.Event()
 if a.dry_run:
  class Handler(BaseHTTPRequestHandler):
   def do_POST(self):
    raw=self.rfile.read(int(self.headers.get('Content-Length',0)));now=time.time()
    if self.path in ('/humanoid/update','/teleop/update'):
     data=json.loads(raw);arrivals.append(time.perf_counter())
     if isinstance(data.get('capture_at'),(float,int)):latencies.append((time.perf_counter(),(now-data['capture_at'])*1000))
    if self.path=='/teleop/preview':previews.append(time.perf_counter())
    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"ok":true,"process_ms":0}')
   def do_GET(self):
    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
    self.wfile.write(json.dumps(dict(input_count=len(arrivals),preview_count=len(previews))).encode())
   def log_message(self,*args):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();a.url='http://127.0.0.1:'+str(server.server_port)
 endpoint='/humanoid/status' if a.mode=='humanoid' else '/teleop/status'
 def status():
  s=get(a.url+endpoint)
  if a.mode=='humanoid':s['preview_count']=get(a.url+'/teleop/status').get('preview_count')
  return s
 def monitor():
  while not stop.wait(.1):observations.append((time.perf_counter(),status()))
 before=status();mt=threading.Thread(target=monitor,daemon=True);mt.start()
 metrics_path=pathlib.Path(a.output).with_suffix('.tracker.json')
 if metrics_path.exists():metrics_path.unlink()
 cmd=[sys.executable,str(pathlib.Path(__file__).with_name('teleop_tracker_win.py')),'--mode',a.mode,'--url',a.url,'--seconds',str(a.seconds+a.warmup+5),'--camera',str(a.camera),'--metrics-out',str(metrics_path)]
 if a.video:cmd+=['--video',a.video,'--loop-video']
 env=os.environ.copy()
 for k in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','PIP_PREFIX','PYTHONNOUSERSITE'):env.pop(k,None)
 env['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
 try:run=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=a.seconds+a.warmup+125)
 finally:
  stop.set();mt.join(timeout=2)
  if server:server.shutdown();server.server_close()
 after=status() if not a.dry_run else {};metrics=json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
 window_seconds=a.seconds;window_start=None;window_end=None;window_complete=False
 if a.dry_run and arrivals:
  window_start=arrivals[0]+a.warmup;window_end=window_start+a.seconds;window_complete=arrivals[-1]>=window_end
 elif not a.dry_run:
  changed=[(t,s) for t,s in observations if isinstance(s.get('input_count'),(int,float)) and s['input_count']>before.get('input_count',0)]
  if changed:
   candidates=[(t,s) for t,s in observations if t>=changed[0][0]+a.warmup]
   if candidates:
    window_start,before=candidates[0];ends=[(t,s) for t,s in candidates if t>=window_start+a.seconds]
    if ends:
     window_end,after=ends[0];window_seconds=window_end-window_start;window_complete=True
 def delta(key):
  x,y=before.get(key),after.get(key)
  return y-x if isinstance(x,(int,float)) and isinstance(y,(int,float)) and y>=x else None
 received=sum(window_start<=t<window_end for t in arrivals) if a.dry_run and window_start is not None else delta('input_count') if window_complete else None
 preview_count=sum(window_start<=t<window_end for t in previews) if a.dry_run and window_start is not None else delta('preview_count') if window_complete else None
 if a.dry_run:latencies=[v for t,v in latencies if window_start is not None and window_end is not None and window_start<=t<window_end]
 if not latencies:latencies=[s['capture_latency_ms'] for t,s in observations if window_start is not None and window_end is not None and window_start<=t<=window_end and isinstance(s.get('capture_latency_ms'),(float,int))]
 def pct(values,q):
  v=sorted(values);return v[int((len(v)-1)*q)] if v else None
 duration=metrics.get('seconds',a.seconds)
 result=dict(test='video-dry-run' if a.video else 'live-camera',collector='local-independent-http' if a.dry_run else 'server-status',camera_acceptance='NOT_PERFORMED' if a.video else 'REVIEW_REQUIRED',returncode=run.returncode,source_fps=metrics.get('source_fps'),camera_fps=None if a.video else metrics.get('source_frames_due',0)/max(.001,duration),processing_ratio=metrics.get('processed_input_ratio'),hand_detection_rate=metrics.get('hand_detection_rate'),pose_detection_rate=metrics.get('pose_detection_rate'),server_received_count=received,measurement_seconds=window_seconds,window_complete=window_complete,server_received_hz=received/window_seconds if received is not None else None,preview_count=preview_count,preview_hz=preview_count/window_seconds if preview_count is not None else None,capture_to_arrival_ms_p50=pct(latencies,.5),capture_to_arrival_ms_p95=pct(latencies,.95),latency_clock='same host' if a.dry_run else 'cross-host wall clocks; sync required',tracker=metrics,stderr=run.stderr[-2000:])
 result['blocked']=[]
 if not window_complete:result['blocked'].append('full measurement window unavailable')
 if not metrics:result['blocked'].append('tracker metrics missing/camera failed')
 if received is None:result['blocked'].append('input_count unavailable; send count is not receive count')
 if preview_count is None:result['blocked'].append('preview_count unavailable')
 if not latencies:result['blocked'].append('capture_latency_ms unavailable')
 if a.video:result['blocked'].append('physical camera not tested')
 pathlib.Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf8')
 print('| metric | value |\n|---|---|')
 for k,v in result.items():
  if k not in ('tracker','stderr'):print('| '+k+' | '+str(v)+' |')
 print(json.dumps(result));return run.returncode
if __name__=='__main__':sys.exit(main())
