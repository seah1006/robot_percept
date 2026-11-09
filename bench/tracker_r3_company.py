"""Windows 회사 녹화본 교차/장시간 하네스. WSL flock 안에서 Windows Python으로 실행."""
import argparse,json,os,pathlib,shutil,subprocess,sys,tempfile,time,urllib.request

def get(url):
 try:
  with urllib.request.urlopen(url,timeout=2) as r:return json.load(r)
 except Exception:return {}
def main():
 p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:5095');p.add_argument('--out',required=True);p.add_argument('--seconds',type=float,default=30);p.add_argument('--long',action='store_true');p.add_argument('--server-pid',type=int);p.add_argument('--order',default='http,ws');p.add_argument('--videos',nargs='+',default=[str(pathlib.Path.home()/'Documents/sam_camera'/v) for v in ['teleop_final_hand.mp4','teleop_round2_async.mp4']]);a=p.parse_args()
 if ':5080' in a.url:p.error('5080 forbidden')
 if a.long and a.seconds<3600:p.error('--long requires --seconds >=3600')
 out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=False);repo=pathlib.Path(__file__).resolve().parents[1];tmp=pathlib.Path(tempfile.mkdtemp(prefix='rp_tracker_r3_'));tk=tmp/'teleop_tracker_win.py';shutil.copy2(repo/'tools/teleop_tracker_win.py',tk)
 env=os.environ.copy()
 for key in ['PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','PIP_PREFIX','PYTHONNOUSERSITE']:env.pop(key,None)
 env['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS']='0'
 (out/'manifest.json').write_text(json.dumps(dict(started=time.strftime('%Y-%m-%dT%H:%M:%S%z'),camera_acceptance='NOT_PERFORMED',long=a.long,concurrent_load='See WSL env log. Long-run performance observational only.'),indent=2))
 def memory(pid):
  # Handle-based Start-Process CPU was invalid previously; query live process by PID.
  cmd=f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; if($p){{$p.WorkingSet64}}"
  r=subprocess.run(['powershell.exe','-NoProfile','-Command',cmd],capture_output=True,text=True)
  return int(r.stdout.strip()) if r.stdout.strip().isdigit() else None
 try:
  runs=[(v,tr) for v in a.videos for tr in a.order.split(',')]
  if a.long:runs=[(a.videos[0],'ws')]
  for i,(video,tr) in enumerate(runs):
   label=f'{i+1:02d}_{pathlib.Path(video).stem}_{tr}';mp=out/(label+'.metrics.json');rows=[];t0=time.perf_counter();next_mem=0
   cmd=[sys.executable,str(tk),'--mode','humanoid','--transport',tr,'--url',a.url,'--video',video,'--loop-video','--seconds',str(a.seconds+7),'--metrics-out',str(mp)]
   with (out/(label+'.stdout')).open('w') as so,(out/(label+'.stderr')).open('w') as se:
    proc=subprocess.Popen(cmd,env=env,stdout=so,stderr=se)
    while proc.poll() is None:
     t=time.perf_counter()-t0;s=get(a.url+'/humanoid/status');pv=get(a.url+'/teleop/status');row=dict(elapsed_s=t,input_count=s.get('input_count'),preview_count=pv.get('preview_count'))
     if t>=next_mem:
      row['tracker_rss_bytes']=memory(proc.pid)
      if a.server_pid:
       r=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--exec','awk','/^VmRSS:/{print $2}',f'/proc/{a.server_pid}/status'],capture_output=True,text=True);row['server_rss_kib']=int(r.stdout.strip()) if r.stdout.strip().isdigit() else None
      next_mem+=300
     rows.append(row)
     with (out/(label+'.samples.jsonl')).open('a') as f:f.write(json.dumps(row)+'\n')
     time.sleep(5 if a.long else .1)
   result=dict(returncode=proc.returncode,video=pathlib.Path(video).name,transport=tr,window_complete=False)
   good=[r for r in rows if isinstance(r['input_count'],int)];changed=[r for r in good if r['input_count']>good[0]['input_count']] if good else []
   if changed:
    starts=[r for r in good if r['elapsed_s']>=changed[0]['elapsed_s']+2]
    if starts:
     first=starts[0];ends=[r for r in good if r['elapsed_s']>=first['elapsed_s']+a.seconds]
     if ends:
      last=ends[0];dt=last['elapsed_s']-first['elapsed_s'];result.update(window_complete=True,window_seconds=dt,server_received_hz=(last['input_count']-first['input_count'])/dt,preview_fps=(last['preview_count']-first['preview_count'])/dt if all(isinstance(r['preview_count'],int) for r in [first,last]) else None)
   if mp.exists():result['tracker']=json.loads(mp.read_text())
   (out/(label+'.result.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 finally:shutil.rmtree(tmp,ignore_errors=True)
if __name__=='__main__':main()
