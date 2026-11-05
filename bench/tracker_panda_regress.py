"""Panda OFF/ON FPS bench. Coordinate Windows slot and WSL flock first."""
import argparse,json,pathlib,subprocess,sys,time,urllib.request,statistics,os,tempfile

def request(url,data=None):
 raw=None if data is None else json.dumps(data).encode()
 with urllib.request.urlopen(urllib.request.Request(url,data=raw,headers={'Content-Type':'application/json'}),timeout=2) as r:return json.load(r)
def sample(url,seconds):
 rows=[];start=time.perf_counter();end=start+seconds
 before=request(url+'/teleop/status')
 while time.perf_counter()<end:
  rows.append({'t':time.time(),'main':request(url+'/status'),'teleop':request(url+'/teleop/status')});time.sleep(min(.2,max(0,end-time.perf_counter())))
 after=request(url+'/teleop/status');duration=time.perf_counter()-start
 def hz(key):
  b,e=before.get(key),after.get(key)
  return (e-b)/duration if isinstance(b,(int,float)) and isinstance(e,(int,float)) and e>=b else None
 return rows,dict(seconds=duration,input_hz=hz('input_count'),preview_hz=hz('preview_count'),before=before,after=after)

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--url',default='http://127.0.0.1:5095');p.add_argument('--seconds',type=float,default=30);p.add_argument('--warmup',type=float,default=5);p.add_argument('--output',default='tracker_panda_regress.json');a=p.parse_args()
 if ':5080' in a.url:p.error('user server 5080 forbidden')
 if a.seconds<=0 or a.warmup<0:p.error('seconds must be positive; warmup nonnegative')
 request(a.url+'/teleop/mode',{'enabled':False});time.sleep(a.warmup);baseline,bwindow=sample(a.url,a.seconds);proc=None
 env=os.environ.copy()
 for key in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','PIP_PREFIX','PYTHONNOUSERSITE'):env.pop(key,None)
 env['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
 tracker=pathlib.Path(__file__).resolve().parents[1]/'tools'/'teleop_tracker_win.py'
 metrics=pathlib.Path(a.output).with_suffix('.tracker.json');metrics.unlink(missing_ok=True)
 with tempfile.TemporaryFile(mode='w+',encoding='utf8') as log:
  try:
   request(a.url+'/teleop/mode',{'enabled':True});initial=request(a.url+'/teleop/status')
   proc=subprocess.Popen([sys.executable,str(tracker),'--mode','panda','--video',a.video,'--loop-video','--url',a.url,'--seconds',str(a.seconds+a.warmup+5),'--metrics-out',str(metrics)],stdout=log,stderr=log,env=env)
   # Wait for real uploads instead of timing model imports/downloads as active FPS.
   deadline=time.perf_counter()+120
   while True:
    if proc.poll() is not None:raise RuntimeError('tracker exited before first preview')
    current=request(a.url+'/teleop/status')
    if (isinstance(current.get('preview_count'),int) and current['preview_count']>initial.get('preview_count',0)) or current.get('preview_hz',0)>0:break
    if time.perf_counter()>deadline:raise TimeoutError('first tracker preview timeout')
    time.sleep(.1)
   time.sleep(a.warmup);active,awindow=sample(a.url,a.seconds);proc.wait(timeout=120)
  finally:
   if proc is not None and proc.poll() is None:proc.terminate();proc.wait(timeout=5)
   request(a.url+'/teleop/mode',{'enabled':False})
  log.seek(0);tracker_log=log.read()
 def avg(rows,key,group):
  values=[r[group].get(key) for r in rows];values=[v for v in values if isinstance(v,(int,float))];return statistics.mean(values) if values else None
 b=avg(baseline,'fps','main');v=avg(active,'fps','main');drop=100*(b-v)/b if b and v else None
 result=dict(baseline_fps=b,active_fps=v,fps_drop_percent=drop,fps_drop_lt10=drop<10 if drop is not None else None,warmup_seconds=a.warmup,baseline_window=bwindow,active_window=awindow,preview_hz_mean_reference=avg(active,'preview_hz','teleop'),baseline=baseline,active=active,tracker_returncode=proc.returncode,tracker_log=tracker_log[-4000:],blocked=[])
 if awindow['preview_hz'] is None:result['blocked'].append('cumulative preview_count unavailable')
 if proc.returncode:result['blocked'].append('tracker failed')
 if metrics.exists():result['tracker']=json.loads(metrics.read_text())
 pathlib.Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in result.items() if k not in ('baseline','active','tracker_log')}))
if __name__=='__main__':main()
