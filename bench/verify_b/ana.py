import json, random, statistics, os
D=os.path.expanduser("~/work/robot_percept/bench/verify_g/out/ab3")
random.seed(7)
def load(l):
    r=json.load(open(f"{D}/AB_{l}.json")); t=json.load(open(f"{D}/AB_{l}.ts.json")); return r,t
W={l:load(l) for l in ("A1","B1","A2","B2")}
def boot(a,b,f=statistics.fmean,n=5000):
    d=[]
    for _ in range(n):
        d.append(f([random.choice(b) for _ in b])-f([random.choice(a) for _ in a]))
    d.sort(); return f(b)-f(a), d[int(.025*n)], d[int(.975*n)]
def p95(x): x=sorted(x); return x[int(.95*(len(x)-1))]
for l,(r,t) in W.items():
    g=r["g1_window"]
    print(l,"load0",r["load0"][0],"fps",g["fps_count"],g["frames"],"gap max/p95",g["max_gap_ms"],g["gap_p95_ms"],"cpu main/tree",r["cpu"]["main_pct"],r["cpu"]["tree_pct"],"procs",r["cpu"]["procs"],"int_p95",r["server_latency_ms"]["receive_publish"]["p95"],"proc",r["sender"].get("server_processed_ratio"),r["sender"].get("preview_processed_ratio"))
def rtts(l): t=W[l][1]; return [ (b-a)*1000 for a,b in zip(t["ts_send"],t["ts_recv"])]
A=rtts("A1")+rtts("A2"); B=rtts("B1")+rtts("B2")
m,lo,hi=boot(A,B); print(f"update RTT mean(ms) A={statistics.fmean(A):.3f} B={statistics.fmean(B):.3f} diff={m:.3f} CI[{lo:.3f},{hi:.3f}]", "p95 A/B",round(p95(A),2),round(p95(B),2))
def cmp(name,fa,fb):
    a=[fa(W[l][0]) for l in ("A1","A2")]; b=[fb(W[l][0]) for l in ("B1","B2")]
    d=[y-x for x in a for y in b]
    print(name,"A",a,"B",b,"B-A 쌍 차이 범위",round(min(d),3),round(max(d),3),"-> 0 포함" if min(d)<=0<=max(d) else "-> 0 미포함(방향 일관)")
cmp("fps",lambda r:r["g1_window"]["fps_count"],lambda r:r["g1_window"]["fps_count"])
cmp("tree cpu%",lambda r:r["cpu"]["tree_pct"],lambda r:r["cpu"]["tree_pct"])
cmp("main cpu%",lambda r:r["cpu"]["main_pct"],lambda r:r["cpu"]["main_pct"])
cmp("gap p95 ms",lambda r:r["g1_window"]["gap_p95_ms"],lambda r:r["g1_window"]["gap_p95_ms"])
