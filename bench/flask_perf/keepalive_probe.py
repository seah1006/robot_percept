import json, multiprocessing as mp, time
from flask import Flask, request
from werkzeug.serving import make_server, WSGIRequestHandler
import urllib3

class HTTP11RequestHandler(WSGIRequestHandler):
    protocol_version='HTTP/1.1'


def serve(port, handler):
    app=Flask(__name__)
    @app.get('/peer')
    def peer():
        sock=request.environ.get('werkzeug.socket')
        return {'peer_port':sock.getpeername()[1] if sock else None,'protocol':request.environ.get('SERVER_PROTOCOL')}
    make_server('127.0.0.1',port,app,threaded=True,request_handler=handler).serve_forever()


def probe(port):
    pool=urllib3.PoolManager(num_pools=1,maxsize=1)
    rows=[]
    for _ in range(5):
        r=pool.request('GET',f'http://127.0.0.1:{port}/peer',retries=False)
        rows.append(json.loads(r.data));r.release_conn()
    pool.clear();return rows


if __name__=='__main__':
    out={}
    for name,port,handler in [('http10',5095,WSGIRequestHandler),('http11',5093,HTTP11RequestHandler)]:
        p=mp.Process(target=serve,args=(port,handler));p.start();time.sleep(.4)
        try: out[name]=probe(port)
        finally:p.terminate();p.join()
    print(json.dumps(out,indent=2))
