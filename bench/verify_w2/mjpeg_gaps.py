"""MJPEG 수신: 프레임별 monotonic 도착시각 기록. 사용: mjpeg_gaps.py URL 초 출력.json"""
import socket, time, sys, json, re
from urllib.parse import urlparse
u=urlparse(sys.argv[1]); dur=float(sys.argv[2])
s=socket.create_connection((u.hostname,u.port)); s.settimeout(10)
s.sendall(("GET %s HTTP/1.0\r\nHost: x\r\n\r\n"%(u.path)).encode())
buf=b""; ts=[]; t0=time.monotonic()
while time.monotonic()-t0<dur:
    try: d=s.recv(262144)
    except socket.timeout: continue
    if not d: break
    buf+=d
    while True:
        i=buf.find(b"\xff\xd8")
        if i<0: buf=buf[-1:]; break
        j=buf.find(b"\xff\xd9",i+2)
        if j<0: buf=buf[i:]; break
        ts.append(time.monotonic()); buf=buf[j+2:]
json.dump({"t0":t0,"ts":ts},open(sys.argv[3],"w"))
