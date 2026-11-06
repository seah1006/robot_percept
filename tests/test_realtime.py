import json
from pathlib import Path
from types import SimpleNamespace

from web.realtime import ConnectionLimiter, StatusSchedule, handle_tracker_message, origin_allowed
from tools.teleop_tracker_win import WebSocketTransport, websocket_route_enabled


class Endpoint:
    def __init__(self): self.updates=[]; self.previews=[]
    def accept_update(self,data): self.updates.append(data); return ({'ok':True,'process_ms':.2},200)
    def accept_preview(self,data):
        self.previews.append(data)
        return ({'ok':True},200) if data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9') else ({'error':'JPEG required'},400)


def test_tracker_ws_reuses_http_validation_and_keeps_errors_as_replies():
    teleop=Endpoint(); humanoid=Endpoint()
    ok=handle_tracker_message(json.dumps({'route':'/humanoid/update','data':{'detected':False}}),teleop,humanoid)
    assert ok['ok'] and ok['status']==200 and humanoid.updates==[{'detected':False}]
    bad=handle_tracker_message('{',teleop,humanoid)
    assert bad=={'ok':False,'status':400,'error':'JSON object required'}
    unsupported=handle_tracker_message(json.dumps({'route':'/reset','data':{}}),teleop,humanoid)
    assert unsupported['status']==404


def test_tracker_ws_route_specific_json_limits():
    teleop=Endpoint(); humanoid=Endpoint()
    t=handle_tracker_message(json.dumps({'route':'/teleop/update','data':{'detected':False,'pad':'x'*8200}}),teleop,humanoid)
    h=handle_tracker_message(json.dumps({'route':'/humanoid/update','data':{'detected':False,'pad':'x'*65600}}),teleop,humanoid)
    assert t['status']==413 and h['status']==413
    assert not teleop.updates and not humanoid.updates


def test_websocket_origin_and_connection_limit_guards():
    assert origin_allowed(None,'127.0.0.1:5093')
    assert origin_allowed('http://127.0.0.1:5093','127.0.0.1:5093')
    assert not origin_allowed('https://evil.example','127.0.0.1:5093')
    limit=ConnectionLimiter(2)
    assert limit.acquire() and limit.acquire() and not limit.acquire()
    for _ in range(24): limit.release(); assert limit.acquire()
    limit.release();limit.release();assert limit.count==0


def test_tracker_ws_binary_preview_limits_and_validation():
    teleop=Endpoint(); humanoid=Endpoint()
    assert handle_tracker_message(b'bad',teleop,humanoid)['status']==400
    assert handle_tracker_message(b'\xff\xd8x\xff\xd9',teleop,humanoid)['ok']
    assert handle_tracker_message(b'x'*250001,teleop,humanoid)['status']==413


def test_browser_push_event_does_not_reenter_robot_status_dispatch():
    app=(Path(__file__).parents[1]/'web/static/app.js').read_text()
    stream=(Path(__file__).parents[1]/'web/static/status-stream.js').read_text()
    assert "addEventListener('robot-push'" in app
    assert "dispatchEvent(new CustomEvent('robot-status'" in app
    assert "addEventListener('robot-status'" not in app
    assert "m.type+'-push'" in stream


def test_status_schedule_uses_push_rates_and_inactive_backoff():
    s=StatusSchedule(now=10)
    assert set(s.due(10))=={'robot','teleop','humanoid'}
    s.sent('robot',10,{})
    s.sent('teleop',10,{'enabled':False})
    s.sent('humanoid',10,{'mode':True})
    assert s.due(10.11)==['humanoid']
    assert set(s.due(11.01))=={'robot','teleop','humanoid'}


def test_ws_mode_uses_websocket_for_control_and_http_for_preview():
    assert websocket_route_enabled('ws',False)
    assert not websocket_route_enabled('ws',True)
    assert not websocket_route_enabled('http',False)


def test_windows_ws_transport_reconnects_once_and_preserves_default_protocol():
    class Broken:
        def send(self,_): raise OSError('first connection lost')
        def close(self): pass
    class Good:
        sent=None
        def send(self,value): self.sent=value
        def send_binary(self,value): self.sent=value
        def recv(self): return '{"ok":true,"status":200,"process_ms":0.1}'
        def close(self): pass
    made=[]
    def connector(url,**kwargs):
        ws=Broken() if not made else Good();made.append((url,kwargs,ws));return ws
    t=WebSocketTransport('http://127.0.0.1:5093',connector=connector)
    reply=t.request('/humanoid/update',{'detected':False})
    assert reply['ok'] and len(made)==2
    assert made[0][0]=='ws://127.0.0.1:5093/tracker/ws'
    assert json.loads(made[1][2].sent)['route']=='/humanoid/update'
