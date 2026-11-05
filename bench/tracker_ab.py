"""Controlled A/B/A/B tracker comparison; caller owns global measurement lock."""
import json,pathlib,subprocess,sys,time,urllib.request,tempfile,os
ROOT=pathlib.Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:5095'
OUT=pathlib.Path(sys.argv[1])

def request(route,data=None,timeout=3):
 req=urllib.request.Request(URL+route,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 for attempt in range(4):
  try:
   with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
  except OSError:
   if attempt==3:raise
   time.sleep(.5)
def state():return request('/humanoid/status'),request('/teleop/status')
def main():
 deadline=time.perf_counter()+120
 while True:
  try:request('/status');break
  except Exception:
   if time.perf_counter()>deadline:raise
   time.sleep(.5)
 request('/humanoid/mode',{'enabled':True},timeout=90)
 env=os.environ.copy()
 for k in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','PIP_PREFIX','PYTHONNOUSERSITE'):env.pop(k,None)
 env['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
 rows=[]
 try:
  for label in ('A','B','A','B'):
   tracker=ROOT/'bench'/'tracker_baseline_temp.py' if label=='A' else ROOT/'tools'/'teleop_tracker_win.py'
   load=subprocess.run(['wsl','-d','Ubuntu-24.04','--','uptime'],capture_output=True,text=True).stdout.strip()
   gpu=subprocess.run(['wsl','-d','Ubuntu-24.04','--','nvidia-smi','--query-gpu=utilization.gpu,memory.used','--format=csv'],capture_output=True,text=True).stdout.strip()
   processes=subprocess.run(['wsl','-d','Ubuntu-24.04','--','ps','-eo','pid,args'],capture_output=True,text=True).stdout
   concurrent=[line for line in processes.splitlines() if 'bench/' in line or 'verify_' in line]
   initial,_=state();first=None;before=None;after=None
   with tempfile.TemporaryFile(mode='w+',encoding='utf8') as log:
    proc=subprocess.Popen([sys.executable,str(tracker),'--mode','humanoid','--url',URL,'--video',str(pathlib.Path.home()/'Documents/sam_camera/teleop_final_hand.mp4'),'--loop-video','--seconds','35'],stdout=log,stderr=log,env=env)
    try:
     while proc.poll() is None:
      hs,ts=state();now=time.perf_counter()
      if first is None and hs.get('input_count',0)>initial.get('input_count',0):first=now
      if first is not None and before is None and now>=first+2:before=(now,hs,ts)
      if before and after is None and now>=before[0]+30:after=(now,hs,ts)
      time.sleep(.5)
     proc.wait(timeout=120)
    finally:
     if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
    log.seek(0);output=log.read();metrics={}
    for line in output.splitlines():
     try:
      value=json.loads(line)
      if isinstance(value,dict) and 'processed_input_ratio' in value:metrics=value
     except (ValueError,TypeError):pass
   duration=after[0]-before[0] if before and after else None
   def rate(group,key):
    return (after[group][key]-before[group][key])/duration if duration and key in before[group] and key in after[group] else None
   row=dict(run=len(rows)+1,label=label,load=load,gpu=gpu,concurrent=concurrent,gpu_measure_lock_held=True,returncode=proc.returncode,window_seconds=duration,received_hz=rate(1,'input_count'),preview_fps=rate(2,'preview_count'),processing_ratio=metrics.get('processed_input_ratio'),neural_ms=metrics.get('stages_ms',{}).get('neural'),retarget_ms=metrics.get('stages_ms',{}).get('retarget'),overlay_ms=metrics.get('stages_ms',{}).get('overlay'),post_ms_p50=metrics.get('post_ms_p50'),post_ms_p95=metrics.get('post_ms_p95'),metrics=metrics)
   if not metrics:row['error_log']=output[-3000:]
   rows.append(row);OUT.write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps(row),flush=True)
 finally:request('/humanoid/mode',{'enabled':False},timeout=15)
if __name__=='__main__':main()
