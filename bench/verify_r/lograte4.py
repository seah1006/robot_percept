import re,collections,datetime
c=collections.Counter();p=collections.Counter()
for l in open('/home/user/work/robot_percept/bench/verify_r/server5092.log',errors='ignore'):
    m=re.search(r'\[\d+/Nov/2026 (\d\d:\d\d:\d\d)\] "POST (/humanoid/update|/teleop/preview)',l)
    if m: (c if m.group(2)=='/humanoid/update' else p)[m.group(1)]+=1
ks=sorted(c)
# last contiguous run (gaps <=3s)
t=lambda s:datetime.datetime.strptime(s,'%H:%M:%S')
run=[ks[-1]]
for k in reversed(ks[:-1]):
    if (t(run[0])-t(k)).total_seconds()<=3: run.insert(0,k)
    else: break
print('run',run[0],run[-1],len(run),'s total update',sum(c[k] for k in run),'preview',sum(p[k] for k in run))
# best 30s window inside middle (skip first 3s, last 3s)
mid=run[3:-3]
import itertools
best=[]
for i in range(0,len(mid)-29):
    w=mid[i:i+30]; best.append(sum(c[k] for k in w))
print('30s window counts min/max/mean',min(best),max(best),sum(best)/len(best),'-> Hz',min(best)/30,max(best)/30)
print('per-sec min/max',min(c[k] for k in mid),max(c[k] for k in mid))