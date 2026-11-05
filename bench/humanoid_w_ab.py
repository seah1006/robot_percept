"""Frozen-source A/B/A/B on 5091; run under rp_measure.lock."""
import pathlib,tempfile,shutil,os,subprocess,sys,time,json,requests,psutil,signal,re,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:5091'
web=ROOT/'web';app=(web/'app.py').read_text();worker=(web/'sim_worker.py').read_text()
oldapp=app.replace("   if not name:continue  # P-area idle IPC guard, approved by integration owner\n   st=dict(self.status)\n   if st.get(\"frame_seq\")==last_seq:continue",'   st=dict(self.status)\n   if not name or st.get("frame_seq")==last_seq:continue')
oldapp=oldapp.replace("   if not name:continue  # P-area idle IPC guard, approved by integration owner\n   st=self.status.copy()  # one atomic Manager RPC, not one RPC per status key\n   if st.get(\"frame_seq\")==last_seq:continue",'   st=dict(self.status)\n   if not name or st.get("frame_seq")==last_seq:continue')
oldapp=oldapp.replace("   with video_condition:\n    video_consumers[show_gt]=video_consumers.get(show_gt,0)+1\n    rt.status['video_viewers']=sum(video_consumers.values())\n    # Wait for a new worker frame rather than serving an old idle cache.\n    last_seq=rt.status.get('frame_seq',0)",'   with video_condition:video_consumers[show_gt]=video_consumers.get(show_gt,0)+1')
oldapp=oldapp.replace("    with video_condition:\n     video_consumers[show_gt]-=1\n     rt.status['video_viewers']=sum(video_consumers.values())",'    with video_condition:video_consumers[show_gt]-=1')
oldapp=oldapp.replace("  rt.status['video_until']=time.monotonic()+.25\n",'')
oldworker=re.sub(r'def render_period\(status, now\):.*?(?=def run_worker)', '',worker,flags=re.S)
oldworker=oldworker.replace('        demand_check=0.; render_interval=.5\n','').replace('nonlocal last_render,frame_count,fps_t0,demand_check,render_interval','nonlocal last_render,frame_count,fps_t0')
oldworker=oldworker.replace('            if now-demand_check >= .025:\n                render_interval=render_period(status,now); demand_check=now\n            if not force and now-last_render < render_interval: return\n            status["render_idle"]=render_interval > 1/30','            if not force and now-last_render < 1/30: return')
if os.getenv('RP_AB_HEAD_APP','1')=='1':
 oldapp=subprocess.check_output(['git','show','1da4b93:web/app.py'],cwd=ROOT,text=True)
start_index=int(os.getenv('RP_AB_START','0'))
if start_index:
 frozen=pathlib.Path('/tmp/rp_w_ab_ob8laj7j')
 oldapp=(frozen/'0/web/app.py').read_text();oldworker=(frozen/'0/web/sim_worker.py').read_text()
 app=(frozen/'1/web/app.py').read_text();worker=(frozen/'1/web/sim_worker.py').read_text()
def cpu(parent,sec):
 ps=[parent]+parent.children(recursive=True)
 def total():
  t=0
  for p in ps:
   try:c=p.cpu_times();t+=c.user+c.system
   except psutil.Error:pass
  return t
 a=total();t=time.monotonic();time.sleep(sec);return (total()-a)/(time.monotonic()-t)*100
with tempfile.TemporaryDirectory(prefix='rp_w_ab_') as tmp:
 sequence=os.getenv('RP_AB_SEQUENCE','ABAB')
 for i,variant in enumerate(sequence[start_index:],start=start_index):
  folder=pathlib.Path(tmp)/str(i);shutil.copytree(web,folder/'web',ignore=shutil.ignore_patterns('__pycache__'))
  (folder/'web/app.py').write_text(oldapp if variant=='A' else app);(folder/'web/sim_worker.py').write_text(oldworker if variant=='A' else worker)
  env={**os.environ,'PYTHONPATH':str(folder)+':'+str(ROOT),'PORT':'5091','PERCEPTION':'stub','HOST':'0.0.0.0'}
  logfile=open(ROOT/f'notes/humanoid_w_ab_{i}.log','w');proc=subprocess.Popen([sys.executable,'-m','web.app'],cwd=folder,env=env,stdout=logfile,stderr=logfile);parent=psutil.Process(proc.pid)
  try:
   deadline=time.monotonic()+60
   while True:
    try:
     if requests.get(BASE+'/status',timeout=2).json().get('ready'):break
    except requests.RequestException:pass
    if time.monotonic()>deadline:raise RuntimeError('startup timeout')
    time.sleep(.1)
   time.sleep(1);idle=cpu(parent,5);t=time.monotonic();ts=[]
   with requests.get(BASE+'/video',stream=True,timeout=5) as r:
    buf=b''
    for chunk in r.iter_content(4096):
     buf+=chunk
     while b'\xff\xd9' in buf:
      _,buf=buf.split(b'\xff\xd9',1);ts.append(time.monotonic())
     if ts and time.monotonic()-ts[0]>=31:break
   chosen=[x for x in ts if ts[0]+1<=x<ts[0]+31]
   st=requests.get(BASE+'/status').json();uv=st['objects']['mustard']['center_px'];r=requests.post(BASE+'/click',json={'x':uv[0],'y':uv[1]},timeout=35)
   selected0=requests.get(BASE+'/status').json();tracking_t0=time.monotonic()
   time.sleep(10);selected=requests.get(BASE+'/status').json();tracking_elapsed=time.monotonic()-tracking_t0
   tracking_delta=(selected.get('pose') or {}).get('tracking_updates',0)-(selected0.get('pose') or {}).get('tracking_updates',0)
   requests.post(BASE+'/reset',json={});time.sleep(.5);cleared=requests.get(BASE+'/status').json()
   result={'variant':variant,'index':i,'idle_cpu_pct':idle,'first_frame_ms':(ts[0]-t)*1000,'fps30':len(chosen)/30,'frames30':len(chosen),'select_http':r.status_code,'tracking_updates':(selected.get('pose') or {}).get('tracking_updates'),'tracking_fps':(selected.get('pose') or {}).get('tracking_fps'),'tracking_delta_hz':tracking_delta/tracking_elapsed,'tracking_profile':(selected.get('pose') or {}).get('tracking_pipeline_ms'),'tracking_worker_fps':selected.get('fps'),'tracking_worker_delta_hz':(selected.get('frame_seq',0)-selected0.get('frame_seq',0))/tracking_elapsed,'tracking_rtf':selected.get('rtf'),'tracking_elapsed':tracking_elapsed,'tracking_none':cleared.get('tracking_state'),'cleared':cleared.get('selected_object') is None,'load':os.getloadavg(),'app_sha':hashlib.sha256((oldapp if variant=='A' else app).encode()).hexdigest(),'worker_sha':hashlib.sha256((oldworker if variant=='A' else worker).encode()).hexdigest()}
   print(json.dumps(result),flush=True)
   if i==len(sequence)-1 and os.getenv('RP_AB_SKIP_G1','0')!='1':
    with open(ROOT/'notes/humanoid_w_measure_final.json','w') as out:subprocess.run([sys.executable,str(ROOT/'bench/humanoid_w_runtime.py')],cwd=ROOT,env=env,stdout=out,check=True)
  finally:
   children=parent.children(recursive=True)
   proc.send_signal(signal.SIGINT)
   try:proc.wait(timeout=12)
   except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=5)
   for child in children:
    try:
     if child.is_running():child.terminate()
    except psutil.Error:pass
   logfile.close()