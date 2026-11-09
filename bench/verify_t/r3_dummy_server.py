import http.server,socketserver,sys
class H(http.server.BaseHTTPRequestHandler):
    def _r(self):
        n=int(self.headers.get('Content-Length') or 0)
        if n:self.rfile.read(n)
        b=b'{"ok":true}';self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    do_GET=do_POST=_r
    def log_message(self,*a):pass
socketserver.ThreadingTCPServer.allow_reuse_address=True
socketserver.ThreadingTCPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()
