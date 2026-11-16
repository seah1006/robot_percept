import os,time,json,subprocess,sys,urllib.request,urllib.error,socket,tempfile

def main():
    port=5096
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',port))==0: raise RuntimeError('5096 occupied; will not touch owner')
    env=os.environ.copy(); env.update(PORT=str(port),HOST='127.0.0.1',PERCEPTION='stub',RP_PERCEPTION_WARMUP='0',SIM_WIDTH='160',SIM_HEIGHT='120',RP_CELL_DB=tempfile.mktemp(suffix='.sqlite3'))
    log=open('/tmp/ik_r3_server.log','w'); p=subprocess.Popen([sys.executable,'-m','web.app'],env=env,stdout=log,stderr=log,start_new_session=True)
    def call(path,data=None):
        req=urllib.request.Request('http://127.0.0.1:5096'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=2) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    try:
        deadline=time.monotonic()+25
        while True:
            try:
                _,st=call('/status')
                if st.get('ready'):break
            except OSError:pass
            if time.monotonic()>deadline:raise TimeoutError('ready')
            time.sleep(.05)
        code,body=call('/cell/estop',{}); print('estop',code,body,flush=True)
        deadline=time.monotonic()+5; attempts=[]
        while time.monotonic()<deadline:
            _,st=call('/status'); data={'version':st['cell']['version'],'confirmed':True,'scene_confirmed':True,'held_object_ack':None}
            code,body=call('/cell/reset-stop',data); attempts.append({'status':code,'failed':body.get('failed')})
            if code==200:break
            time.sleep(.1)
        print(json.dumps({'reset_status':code,'body':body,'attempts':attempts,'observation':st.get('recovery_observation')},ensure_ascii=False),flush=True)
        assert code==200
    finally:
        t=time.monotonic(); p.terminate(); p.wait(timeout=6);log.close();print('shutdown_s',time.monotonic()-t,flush=True)
if __name__=='__main__':main()
