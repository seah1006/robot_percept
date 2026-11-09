"""WS만 10~15초 차단. HTTP는 전달. 실제 tracker WS->HTTP->WS 시각을 수집."""
import argparse,json,pathlib,select,socket,socketserver,subprocess,sys,threading,time
from urllib.parse import urlsplit

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:5095');p.add_argument('--out',required=True);p.add_argument('--video',required=True);a=p.parse_args();u=urlsplit(a.url)
 if u.port==5080:p.error('5080 forbidden')
 started=time.perf_counter();fault=[]
 class Handler(socketserver.BaseRequestHandler):
  def handle(self):
   conn=self.request;conn.settimeout(3);data=b''
   try:
    while b'\r\n\r\n' not in data:
     b=conn.recv(65536)
     if not b:return
     data+=b
     if len(data)>131072:return
    ws=b'upgrade: websocket' in data.lower()
    if ws and 10<=time.perf_counter()-started<15:
     conn.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n');return
    with socket.create_connection((u.hostname,u.port or 80),timeout=3) as remote:
     remote.sendall(data)
     while True:
      if ws and 10<=time.perf_counter()-started<15:
       fault.append(time.perf_counter()-started);return
      ready,_,_=select.select([conn,remote],[],[],.025)
      for src in ready:
       b=src.recv(65536)
       if not b:return
       (remote if src is conn else conn).sendall(b)
   except OSError:return
 class Proxy(socketserver.ThreadingTCPServer):allow_reuse_address=True;daemon_threads=True
 proxy=Proxy(('127.0.0.1',0),Handler);threading.Thread(target=proxy.serve_forever,daemon=True).start()
 try:
  subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('tracker_r3_company.py')),'--url',f'http://127.0.0.1:{proxy.server_address[1]}','--out',a.out,'--seconds','55','--order','ws','--videos',a.video],check=True)
  out=pathlib.Path(a.out);files=list(out.glob('*.metrics.json'));m=json.loads(files[0].read_text()) if files else {};events=m.get('transport_events',[]);falls=[e for e in events if e['event']=='http_fallback'];back=[e for e in events if e['event']=='ws_connected' and falls and e['elapsed_s']>falls[0]['elapsed_s']]
  # Events use tracker-local QPC origin; align via observed fault and fallback time.
  recovery=back[0]['elapsed_s']-falls[0]['elapsed_s'] if back else None
  restore_to_ws=back[0]['qpc_s']-(started+15) if back else None
  result=dict(ws_block_proxy_seconds=[10,15],observed_fault_s=fault,events=events,fallback_to_ws_s=recovery,return_after_restore_s=restore_to_ws,within_30s=bool(fault and restore_to_ws is not None and 0<=restore_to_ws<=30),verdict='REVIEW_REQUIRED',note='fallback retry deadline=30s; actual path timings include failed connection attempts. Inspect raw events; do not infer return from accepted input.')
  (out/'recovery.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
 finally:proxy.shutdown();proxy.server_close()
if __name__=='__main__':main()
