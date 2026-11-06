import json, os, signal, socket, subprocess, sys, time, urllib.request
from pathlib import Path
ROOT=Path('/home/my/work/robot_percept'); PORT=5095

def free():
    s=socket.socket(); s.settimeout(.1)
    try: return s.connect_ex(('127.0.0.1',PORT)) != 0
    finally: s.close()

def run(hz, rep):
    env=dict(os.environ,PORT=str(PORT),HOST='127.0.0.1',PERCEPTION='stub',RP_PERCEPTION_WARMUP='0',PYTHONPATH=str(ROOT))
    log=ROOT/'bench/verify_h/out'/f'status_{hz}_{rep}.log'
    with log.open('wb') as out:
        p=subprocess.Popen([sys.executable,'-m','web.app'],cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        t0=time.monotonic(); polls=0; ready=None; error=None
        try:
            deadline=t0+20
            while time.monotonic()<deadline:
                polls+=1
                try:
                    data=json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/status',timeout=.3))
                    if data.get('ready'):
                        ready=time.monotonic()-t0; break
                except Exception as exc: error=type(exc).__name__
                target=t0+polls/hz
                time.sleep(max(0,target-time.monotonic()))
        finally:
            if p.poll() is None: p.send_signal(signal.SIGTERM)
            try:p.wait(timeout=7)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        return {'hz':hz,'rep':rep,'ready_s':None if ready is None else round(ready,3),'polls':polls,'last_error':error,'rc':p.returncode,'port_free':free()}
rows=[]
for hz in (10,20):
    for rep in range(12):
        row=run(hz,rep); rows.append(row); print(json.dumps(row),flush=True)
(ROOT/'bench/verify_h/out/status_poll.json').write_text(json.dumps(rows,indent=2))
