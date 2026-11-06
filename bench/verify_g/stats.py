import re,math,sys
f=sys.argv[1]
d={}
for l in open(f):
    m=re.match(r"(\w+?)_(ON|OFF)_\d+ children=(\d+) elapsed=([0-9.]+)s left=(\d+)",l)
    if m: d.setdefault(m[1]+"_"+m[2],[]).append((float(m[4]),int(m[5]),int(m[3])))
for k,v in d.items():
    e=sorted(x for x,_,_ in v); p95=e[min(len(e)-1,math.ceil(.95*len(e))-1)]
    print(k,"n",len(v),"children",sorted(set(c for _,_,c in v)),"left_sum",sum(y for _,y,_ in v),"p50",e[len(e)//2],"p95",p95,"max",e[-1])
