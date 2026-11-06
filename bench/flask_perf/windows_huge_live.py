import json,os,sys,time,urllib3,websocket
port=int(sys.argv[1]);os.environ['NO_PROXY']='127.0.0.1,localhost';base=f'http://127.0.0.1:{port}';ws=f'ws://127.0.0.1:{port}/tracker/ws';http=urllib3.PoolManager()
for _ in range(100):
 try:
  if http.request('GET',base+'/status',timeout=.5,retries=False).status==200:break
 except Exception:time.sleep(.1)
else:raise SystemExit('Windows HTTP readiness failed')
out={}
for name,data,binary in [('text1m','x'*(1<<20),False),('binary5m',b'\xff\xd8'+b'x'*(5<<20),True)]:
 c=websocket.create_connection(ws,timeout=5,http_proxy_host=None);t=time.perf_counter()
 try:
  c.send_binary(data) if binary else c.send(data);c.settimeout(5);r=c.recv();result='empty-close' if not r else r[:120]
 except Exception as e:result=type(e).__name__
 finally:
  try:c.close()
  except Exception:pass
 out[name]={'seconds':round(time.perf_counter()-t,3),'result':result}
out['server_alive']=http.request('POST',base+'/humanoid/update',body=b'{"detected":false}',headers={'Content-Type':'application/json'},timeout=3,retries=False).status
print(json.dumps(out))
