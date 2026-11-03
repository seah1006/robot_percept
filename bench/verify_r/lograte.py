import re,collections
c=collections.Counter();p=collections.Counter()
for l in open('/home/user/work/robot_percept/bench/verify_r/server5092.log',errors='ignore'):
    m=re.search(r'\[\d+/Nov/2026 (\d\d:\d\d:\d\d)\] "POST (/\S+)',l)
    if m:
        (c if m.group(2)=='/humanoid/update' else p)[m.group(1)]+=1
ks=sorted(c)
for k in ks[-70:-50]:print(k,c[k],p[k])