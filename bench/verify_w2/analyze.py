import json,sys
fr=json.load(open(sys.argv[1])); ts=fr["ts"]
pr=[json.loads(l) for l in open(sys.argv[2])]
jumps=[p for p in pr if "skew_ms" in p]
gaps=[(ts[i],(ts[i]-ts[i-1])*1000) for i in range(1,len(ts))]
big=[(round(t-fr["t0"],2),round(g)) for t,g in gaps if g>200]
print("frames",len(ts),"dur",round(ts[-1]-ts[0],1),"fps",round(len(ts)/(ts[-1]-ts[0]),2) if len(ts)>1 else 0,"maxgap_ms",round(max(g for _,g in gaps)) if gaps else None)
print("walljumps(t_rel,skew_ms):",[(round(j["mono"]-fr["t0"],2),j["skew_ms"]) for j in jumps])
print("gaps>200ms(t_rel_end,gap_ms):",big)
