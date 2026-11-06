import json, os, sys, time, websocket
u='ws://127.0.0.1:5093/tracker/ws'
w=websocket.create_connection(u,timeout=2)
w.send(json.dumps({'route':'/humanoid/update','data':{'detected':False}}));print('valid',w.recv())
w.send('{');print('invalid',w.recv())
w.send(json.dumps({'route':'/humanoid/update','data':{'detected':False}}));print('survives',w.recv());w.close()
w=websocket.create_connection(u,timeout=2);w.send_binary(b'\xff\xd8'+b'x'*249997+b'\xff\xd9');print('oversize',w.recv());w.send_binary(b'\xff\xd8x\xff\xd9');print('preview_after_error',w.recv());w.close()
w=websocket.create_connection(u,timeout=2);t=time.perf_counter();w.send_binary(b'x'*(5<<20));w.settimeout(5)
try:r=w.recv();print('huge_5mb',round(time.perf_counter()-t,3),repr(r))
except Exception as e:print('huge_5mb',round(time.perf_counter()-t,3),type(e).__name__)
w.close()
s=websocket.create_connection('ws://127.0.0.1:5093/status/ws',timeout=2);print('status_types',[json.loads(s.recv())['type'] for _ in range(3)]);s.close();time.sleep(.3)
try:
 bad=websocket.create_connection(u,timeout=2,origin='http://evil.example');value=bad.recv();print('cross_origin','rejected' if not value else 'unexpected-data',repr(value))
except Exception as e: print('cross_origin','rejected',type(e).__name__)
time.sleep(1)
held=[websocket.create_connection('ws://127.0.0.1:5093/status/ws',timeout=2) for _ in range(9)]
held_values=[c.recv() for c in held];print('status_cap_nonempty',sum(bool(v) for v in held_values));[c.close() for c in held]
time.sleep(2);pid=int(sys.argv[1]);before=len(os.listdir(f'/proc/{pid}/task'))
for _ in range(24):
 c=websocket.create_connection('ws://127.0.0.1:5093/status/ws',timeout=2);c.recv();c.close()
time.sleep(2);after=len(os.listdir(f'/proc/{pid}/task'));print('status_threads_before_after',before,after)
