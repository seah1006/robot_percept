import json,urllib.request,re
d=json.loads(urllib.request.urlopen('http://127.0.0.1:5092/humanoid/status').read())
print({k:d.get(k) for k in ('state','fps','input_hz','human_detected','tracking','latency_ms')})
log=open('/home/user/work/robot_percept/bench/verify_r/server5092.log',errors='ignore').read()
print('400s',len(re.findall(r'" 400 -',log)),'updates200',len(re.findall(r'humanoid/update HTTP/1.1" 200',log)))