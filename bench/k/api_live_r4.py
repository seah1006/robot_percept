import os,json,time,threading,urllib.request,urllib.error,socket,tempfile
from werkzeug.serving import make_server
from simple_websocket import Client

def main():
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',5096))==0:raise RuntimeError('5096 occupied')
    os.environ.update(PERCEPTION='stub',RP_PERCEPTION_WARMUP='0',SIM_WIDTH='160',SIM_HEIGHT='120',RP_CELL_DB=tempfile.mktemp(suffix='.sqlite3'))
    from web.app import create_app
    app=create_app();rt=app.extensions['sim_runtime']; server=make_server('127.0.0.1',5096,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def call(path,data,key='live-r4'):
        req=urllib.request.Request('http://127.0.0.1:5096'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Idempotency-Key':key})
        try:
            with urllib.request.urlopen(req,timeout=3) as res:return res.status,json.load(res)
        except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
    try:
        deadline=time.monotonic()+20
        while not rt.status.get('ready') and time.monotonic()<deadline:time.sleep(.02)
        stale=rt.wait(rt.send('refresh',epoch=rt.safety['epoch'].value-1),timeout=3)
        assert stale['status']=='stale_epoch' and stale['error_code']=='STALE_EPOCH'
        data={'instruction':'머스타드를 집어줘','source':'sim','schema_version':1}
        rt.status['held_object']='mustard' # explicit simulated held-slot injection, not a physical grasp claim
        held=call('/tasks',data,'held');rt.status['held_object']=None
        task=call('/tasks',data); duplicate=call('/tasks',data)
        conflict=call('/tasks',{**data,'instruction':'컵'},'live-r4')
        humanoid=call('/humanoid/mode',{'enabled':True})
        ws=Client.connect('ws://127.0.0.1:5096/status/ws'); messages=[]
        for _ in range(12):
            msg=json.loads(ws.receive(timeout=3));messages.append(msg)
            if msg.get('type')=='cell':break
        ws.close(); cell=next(x for x in messages if x['type']=='cell')
        result={'badge':'[시뮬GT]','held_slot_injected':True,'stale_ack':stale,'held409':held,'task':task,'duplicate':duplicate,'conflict':conflict,'humanoid409':humanoid,'ws_cell':cell}
        print(json.dumps(result,ensure_ascii=False),flush=True)
        assert held[0]==409 and humanoid[0]==409 and duplicate[1]['task_id']==task[1]['task_id'] and conflict[0]==409
    finally:server.shutdown();rt.close();thread.join(1)
if __name__=='__main__':main()
