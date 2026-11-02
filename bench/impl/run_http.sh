source /home/user/anaconda3/etc/profile.d/conda.sh
conda activate robot_percept
cd /home/user/work/robot_percept
source sim_test/gl_env.sh
PYTHONPATH=. python bench/impl/profile_stages.py > bench/impl/optimized_stages.json
cat bench/impl/optimized_stages.json
HOST=127.0.0.1 PORT=5081 PERCEPTION=fp FP_INPLANE_STEP=120 python -m web.app > /tmp/fpsi_server.log 2>&1 &
pid=$!
trap 'kill $pid 2>/dev/null || true' EXIT
python - <<'PY'
import requests,time,json,threading
base='http://127.0.0.1:5081'
for _ in range(150):
 try:
  s=requests.get(base+'/status',timeout=3).json()
  if s.get('ready'):break
 except Exception:pass
 time.sleep(.3)
print('READY',s.get('ready'),s.get('error'))
a=requests.get(base+'/status').json();t=time.monotonic()
with requests.get(base+'/video',stream=True) as r:
 n=0
 for chunk in r.iter_content(chunk_size=8192):
  n+=chunk.count(b'--frame')
  if time.monotonic()-t>5:break
b=requests.get(base+'/status').json()
result={'idle_video_fps':n/(time.monotonic()-t),'sim_fps':b.get('fps'),'sim_seq_rate':(b['frame_seq']-a['frame_seq'])/(time.monotonic()-t)}
print(json.dumps(result));open('bench/impl/optimized_http.json','w').write(json.dumps(result,indent=2))
xy=b['objects']['mustard']['center_px'];t=time.monotonic();c=requests.post(base+'/click',json={'x':xy[0],'y':xy[1]},timeout=180); print('CLICK',c.status_code,c.text)
rows=[]
for _ in range(15):
 time.sleep(.5);st=requests.get(base+'/status').json();rows.append(st.get('pose'))
print('TRACK',json.dumps(rows));open('bench/impl/tracking_http.json','w').write(json.dumps(rows,indent=2))
PY