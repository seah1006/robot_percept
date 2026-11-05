import json,time,requests,psutil,subprocess,re,threading
BASE='http://127.0.0.1:5091'
while True:
 try:
  if requests.get(BASE+'/status').json().get('ready'):break
 except Exception:pass
 time.sleep(.2)
s=subprocess.check_output(['ss','-ltnp','sport = :5091'],text=True);pid=int(re.search(r'pid=(\d+)',s)[1]);parent=psutil.Process(pid)
def measure(sec):
 procs=[parent]+parent.children(recursive=True)
 def total():
  t=0
  for p in procs:
   try:c=p.cpu_times();t+=c.user+c.system
   except psutil.Error:pass
  return t
 t=time.monotonic();a=total();time.sleep(sec);return round((total()-a)/(time.monotonic()-t)*100,2)
time.sleep(2)
print(json.dumps({'pid':pid,'cpu_idle_pct':measure(6),'status':requests.get(BASE+'/status').json()},ensure_ascii=False),flush=True)