"""벽시계 점프 프로브(타임스탬프 기록). sleep 기반(clock_nanosleep, 벽시계 영향 없음). 사용: clock_probe_ts.py 초 출력.jsonl"""
import time, sys, json
dur=float(sys.argv[1]); out=open(sys.argv[2],"w")
t_end=time.monotonic()+dur; pm,pr=time.monotonic(),time.time(); n=0
while time.monotonic()<t_end:
    time.sleep(0.02); m,r=time.monotonic(),time.time(); n+=1
    skew=(r-pr)-(m-pm)
    if abs(skew)>0.02: out.write(json.dumps({"mono":m,"skew_ms":round(skew*1000,1)})+"\n"); out.flush()
    pm,pr=m,r
out.write(json.dumps({"done":True,"n":n,"mono":time.monotonic()})+"\n")
