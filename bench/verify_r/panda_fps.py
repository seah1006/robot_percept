import sys,time,http.client,json
port=int(sys.argv[1]);sec=float(sys.argv[2]) if len(sys.argv)>2 else 20
c=http.client.HTTPConnection('127.0.0.1',port,timeout=10);c.request('GET','/video');r=c.getresponse();buf=b'';ts=[];end=time.time()+sec
while time.time()<end:
    ch=r.read1(65536)
    if not ch:break
    buf+=ch
    while True:
        i=buf.find(b'\xff\xd8');j=buf.find(b'\xff\xd9',i+2) if i>=0 else -1
        if i<0 or j<0:break
        ts.append(time.perf_counter());buf=buf[j+2:]
import numpy as np
g=np.diff(ts)
st=json.loads(__import__('urllib.request').request.urlopen(f'http://127.0.0.1:{port}/status').read())
print(json.dumps({'port':port,'frames':len(ts),'fps':round((len(ts)-1)/(ts[-1]-ts[0]),2),'gap_p95_ms':round(float(np.percentile(g,95))*1000,1),'gap_max_ms':round(float(g.max())*1000,1),'status_fps':st.get('fps') or st.get('render_fps'),'load':open('/proc/loadavg').read().split()[:3]}))