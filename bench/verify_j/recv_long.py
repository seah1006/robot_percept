import sys
S=[l.strip().split(",") for l in open(sys.argv[1])]
S=[(float(m),int(c)) for _,m,c,*r in S if c not in("ERR","None","")]
seg=[];cur=[S[0]]
for p,q in zip(S,S[1:]):
    if q[1]>p[1]: cur.append(q)
    else:
        if len(cur)>1 and q[0]-cur[-1][0]>2: seg.append(cur);cur=[q]
        elif len(cur)==1: cur=[q]
seg.append(cur)
for i,s in enumerate(seg,1):
    if len(s)<20: continue
    print(f"run{i}: {s[-1][1]-s[0][1]} updates in {s[-1][0]-s[0][0]:.1f}s = {(s[-1][1]-s[0][1])/(s[-1][0]-s[0][0]):.3f} Hz")
