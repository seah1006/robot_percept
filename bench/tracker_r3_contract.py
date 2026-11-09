"""구현자 단위 계약. 실측 판정 아님."""
from tools.teleop_tracker_win import FallbackTransport
now=[0.];http=[];fail=[False]
class WS:
 def request(self,*args):
  if fail[0]:raise TimeoutError('temporary')
  return 'ws'
t=FallbackTransport(lambda *a:http.append(a) or 'http',WS,warn=lambda *a,**k:None,clock=lambda:now[0])
assert t.request('/humanoid/update',{})=='ws'
now[0]=10;fail[0]=True;assert t.request('/humanoid/update',{})=='http'
now[0]=15;fail[0]=False;assert t.request('/humanoid/update',{})=='http'
now[0]=40;assert t.request('/humanoid/update',{})=='ws'
assert t.effective=='ws' and t.ws_failures==1 and t.ws_connections==2
assert [e['event'] for e in t.events]==['ws_connected','http_fallback','ws_connected']
assert t.request('/teleop/preview',b'jpg',True)=='http'
print('r3 contract: 8 assertions PASS (established WS failure -> HTTP -> WS; raw preview HTTP)')
