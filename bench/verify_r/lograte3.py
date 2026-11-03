import re,collections
c=collections.Counter()
for l in open('/home/user/work/robot_percept/bench/verify_r/server5092.log',errors='ignore'):
    m=re.search(r'\[\d+/Nov/2026 (\d\d:\d\d:\d\d)\] "POST /humanoid/update',l)
    if m: c[m.group(1)]+=1
ks=[k for k in sorted(c) if '09:46:20'<=k<='09:47:15']
print(' '.join(f'{k[3:]}:{c[k]}' for k in ks))