"""Loopback collector (V-W): logs POST bodies to JSONL. usage: collector.py PORT OUT.jsonl"""
import sys, json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
out = open(sys.argv[2], 'w')
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def do_GET(self):
        b = b'{}'; self.send_response(200); self.send_header('Content-Length', str(len(b))); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); body = self.rfile.read(n)
        if self.path != '/teleop/preview':
            try: out.write(json.dumps({'rx': time.time(), 'path': self.path, 'body': json.loads(body)}) + '\n'); out.flush()
            except Exception: pass
        else:
            out.write(json.dumps({'rx': time.time(), 'path': self.path, 'len': n}) + '\n'); out.flush()
        b = b'{"ok":true,"process_ms":0.1}'; self.send_response(200); self.send_header('Content-Length', str(len(b))); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b)
ThreadingHTTPServer(('0.0.0.0', int(sys.argv[1])), H).serve_forever()
