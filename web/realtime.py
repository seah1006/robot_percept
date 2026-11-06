"""Flask-Sock tracker input and browser status push channels."""
from __future__ import annotations

import json
import threading
import time
from urllib.parse import urlsplit
from flask import request
from flask_sock import Sock
from simple_websocket.errors import ConnectionClosed

from .monowait import sleep_until

TRACKER_JSON_LIMIT = 262144
TRACKER_PREVIEW_LIMIT = 250000
# Windows localhost→WSL relay can buffer a large frame before WSL sees it. The
# transport cap must drain the 5MB P0 probe so the app can reply 413 instead of
# deadlocking the sender; route limits below remain 8KB/64KB/250KB.
TRACKER_MESSAGE_LIMIT = 6 << 20
MAX_STATUS_CONNECTIONS = 8


def origin_allowed(origin, host):
    if not origin: return True
    try: return urlsplit(origin).netloc.lower() == host.lower()
    except ValueError: return False


class ConnectionLimiter:
    def __init__(self, limit): self.limit=limit; self.count=0; self.lock=threading.Lock()
    def acquire(self):
        with self.lock:
            if self.count >= self.limit: return False
            self.count += 1; return True
    def release(self):
        with self.lock: self.count=max(0,self.count-1)


def handle_tracker_message(message, teleop, humanoid):
    """Handle one WS message and return the JSON reply without closing on errors."""
    if isinstance(message, bytes):
        if len(message) > TRACKER_PREVIEW_LIMIT:
            return {'ok': False, 'status': 413, 'error': 'JPEG size limit 250KB'}
        body, status = teleop.accept_preview(message)
        return {'ok': status < 400, 'status': status, 'route': '/teleop/preview', **body}
    if not isinstance(message, str):
        return {'ok': False, 'status': 400, 'error': 'text JSON or binary JPEG required'}
    if len(message.encode('utf-8')) > TRACKER_JSON_LIMIT:
        return {'ok': False, 'status': 413, 'error': 'payload too large'}
    try:
        envelope = json.loads(message)
    except (TypeError, ValueError):
        return {'ok': False, 'status': 400, 'error': 'JSON object required'}
    if not isinstance(envelope, dict) or not isinstance(envelope.get('data'), dict):
        return {'ok': False, 'status': 400, 'error': 'route and data object required'}
    route = envelope.get('route')
    data = envelope['data']
    payload_size = len(json.dumps(data, separators=(',', ':')).encode('utf-8'))
    if route == '/humanoid/update':
        if payload_size > 65536: return {'ok': False, 'status': 413, 'route': route, 'error': 'payload too large'}
        body, status = humanoid.accept_update(data)
    elif route == '/teleop/update':
        if payload_size > 8192: return {'ok': False, 'status': 413, 'route': route, 'error': 'payload too large'}
        body, status = teleop.accept_update(data)
    else:
        return {'ok': False, 'status': 404, 'route': route, 'error': 'unsupported tracker route'}
    return {'ok': status < 400, 'status': status, 'route': route, **body}


class StatusSchedule:
    """Per-connection monotonic schedule; inactive modes fall back to 1 Hz."""
    def __init__(self, now=None):
        now = time.monotonic() if now is None else now
        self.next = {'robot': now, 'teleop': now, 'humanoid': now}
        self.active = {'teleop': False, 'humanoid': False}

    def due(self, now):
        return [name for name, deadline in self.next.items() if now >= deadline]

    def sent(self, name, now, payload):
        if name == 'teleop': self.active[name] = bool(payload.get('enabled'))
        if name == 'humanoid': self.active[name] = bool(payload.get('mode'))
        interval = 1/3 if name == 'robot' else (.1 if self.active[name] else 1.)
        self.next[name] = now + interval


def register_realtime(app, robot_status, teleop, humanoid):
    app.config.setdefault('SOCK_SERVER_OPTIONS', {'ping_interval': 25, 'max_message_size': TRACKER_MESSAGE_LIMIT})
    sock = Sock(app)
    status_connections = ConnectionLimiter(MAX_STATUS_CONNECTIONS)

    @sock.route('/tracker/ws')
    def tracker_ws(ws):
        if not origin_allowed(request.headers.get('Origin'), request.host):
            ws.close(reason=1008, message='origin not allowed'); return
        while True:
            try: message = ws.receive()
            except (ConnectionClosed, OSError): return
            if message is None: return
            reply = handle_tracker_message(message, teleop, humanoid)
            try: ws.send(json.dumps(reply, separators=(',', ':')))
            except (ConnectionClosed, OSError): return

    @sock.route('/status/ws')
    def status_ws(ws):
        if not origin_allowed(request.headers.get('Origin'), request.host):
            ws.close(reason=1008, message='origin not allowed'); return
        if not status_connections.acquire():
            ws.close(reason=1013, message='too many status connections'); return
        try:
            schedule = StatusSchedule()
            builders = {'robot': robot_status, 'teleop': teleop.status_payload, 'humanoid': humanoid.status_payload}
            while True:
                now = time.monotonic()
                for name in schedule.due(now):
                    payload = builders[name]()
                    try: ws.send(json.dumps({'type': name, 'data': payload}, separators=(',', ':')))
                    except (ConnectionClosed, OSError): return
                    schedule.sent(name, now, payload)
                sleep_until(time.monotonic() + .02)
        finally: status_connections.release()

    return sock
