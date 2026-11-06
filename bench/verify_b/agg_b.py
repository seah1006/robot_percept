import json,glob,math,collections,os
V=os.path.expanduser('~/work/robot_percept/bench/verify_b/c/')
def wilson(k,n,z=1.96):
    p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return round(100*(c-h),1),round(100*(c+h),1)
def fmt(k,n): lo,hi=wilson(k,n);return f'{k}/{n} (Wilson {lo}-{hi}%)'
single=collections.defaultdict(list);multi=[]
for f in sorted(glob.glob(V+'on_single_*.json')):
    for k,v in json.load(open(f)).items():
        if k!='gtcalls':single[k]+=v
for f in sorted(glob.glob(V+'on_multi_*.json')):
    multi+=json.load(open(f)).get('multi',[])
def row(name,rows):
    n=len(rows);pk=sum(r['pick'] for r in rows);pl=sum(bool(r.get('place')) for r in rows);hm=sum(bool(r.get('home_ok')) for r in rows)
    mv=max((r.get('obj_maxmove_mm',0) for r in rows),default=0)
    el=sorted(r['elapsed'] for r in rows)
    print(f'{name}: pick {fmt(pk,n)} | place {fmt(pl,n)} | home {fmt(hm,n)} | home max obj move {mv:.3f} mm | elapsed/trial median {el[len(el)//2]}s')
    for i,r in enumerate(rows):
        if not(r['pick'] and r.get('place') and r.get('home_ok')): print('   FAIL',i,{k:r.get(k) for k in('pick','place','home_ok','home_err','error','err_mm')})
for k,r in single.items(): row('single '+k,r)
for i,k in enumerate(('mustard','box','cup')): row('multi '+k,[t[i] for t in multi])
print('multi all-three', fmt(sum(all(r['pick'] and r.get('place') for r in t) for t in multi),len(multi)), 'with home', fmt(sum(all(r['pick'] and r.get('place') and r.get('home_ok') for r in t) for t in multi),len(multi)))
print('== home obstacle')
vs=collections.Counter();sk=0
for f in sorted(glob.glob(V+'ho_*.json')):
    for r in json.load(open(f))['rows']:
        if 'skipped' in r: sk+=1;continue
        vs[r['verdict']]+=1
        print(r.get('seed'),r.get('case') or (r.get('blocker','')[:4],r.get('f')),r['verdict'],(r.get('err') or '')[:70],'pen_mm',r.get('pen_mm'))
print(dict(vs),'skipped',sk)
