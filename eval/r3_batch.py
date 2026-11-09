"""Resumable r3 adaptive batches, immutable started chunks and <=240s measurement slots."""
import argparse,json,subprocess,sys,time,shlex
from pathlib import Path
from collections import defaultdict
from eval.harness.metrics import wilson
ROOT=Path(__file__).resolve().parents[1]
def summarize_unlocked(base):
 meta=base/'run_info.json'
 if not meta.exists():meta.write_text(json.dumps(dict(started=(base/'plan.json').stat().st_mtime)))
 groups=defaultdict(list);validation=[]
 for item in json.loads((base/'plan.json').read_text()):
  key=(item['stage'],item['p'],item['a'],item['obj']); found={}
  f=base/item['id']/'trials.jsonl'
  if f.exists():
   for s in f.read_text().splitlines():
    try:
     r=json.loads(s)
     if r['object']!=item['obj'] or r['seed'] in found:raise ValueError('duplicate/wrong object')
     found[r['seed']]=r
    except json.JSONDecodeError:pass
  expected=list(range(item['seed'],item['seed']+item['n']))
  if set(found)-set(expected):raise ValueError('unexpected seed')
  for seed in expected:
   missing=seed not in found
   r=found.get(seed,dict(object=item['obj'],seed=seed,config=dict(perception=item['p'],gt_assist=item['a'],pick='on' if item['stage']=='matrix' else 'off',frames=5),success=False,frames=[],failure_reasons=['missing_trial: unexecuted/interrupted/timeout'],pick_success=False,place_success=False,register_s=None,tracking_fps=None,missing_predictions=5))
   # Preserve raw capture flag; an after-end chunk cannot overlap the closed user window.
   context_file=base/'concurrent_window.json'
   if context_file.exists():
    window=json.loads(context_file.read_text());acquired=base/(item['id']+'.lock_acquired.txt')
    if acquired.exists() and float(acquired.read_text())>=window['ended_unix'] and r.get('concurrent_context'):
     r=dict(r,recorded_concurrent_context=r['concurrent_context'],concurrent_context='',context_correction='chunk acquired after user test end; raw flag preserved separately')
   r=dict(r,stage=item['stage'],chunk=item['id'],missing_trial=missing,register_phase='cold' if seed==item['seed'] else 'warm')
   groups[key].append(r)
  validation.append(dict(chunk=item['id'],expected_seeds=expected,observed_seeds=sorted(found),missing_seeds=sorted(set(expected)-set(found))))
 lines=['# r3 회사 GPU 평가 진행','',f'Unix 갱신: {time.time():.3f}', 'GT oracle identity/click, known extrinsics/contact association 사용. GT-assist off도 deployable perception-only 아님.', '사용자 테스트 동시 진행: 2026-11-09 13:03~13:06 구간 cold/warm 지연에만 적용. 이후 슬롯 전체 최대240초.', 'Wilson95 분모=계획 N30/N20. 미실행/timeout/누락 trial도 실패로 포함. 진행 중의 수치는 잠정 하한이며 최종 PASS 아님.','', '|단계|perception|GT assist|물체|완료/계획|누락 실패|pose Wilson95|pick Wilson95|place Wilson95|cold/warm register median s|','|-|-|-|-|-:|-:|-|-|-|-|']
 actual=[]
 for key,rows in sorted(groups.items()):
  actual+=rows;n=len(rows);missing=sum(r['missing_trial'] for r in rows);rates=[]
  for field in ['success','pick_success','place_success']:
   k=sum(bool(r.get(field)) for r in rows);lo,hi=wilson(k,n)
   rates.append('비대상' if key[0]=='pilot' and field!='success' else f'{k}/{n} [{lo:.3f},{hi:.3f}]')
  import statistics
  timings=[]
  for phase in ['cold','warm']:
   values=[r['register_s'] for r in rows if not r['missing_trial'] and r['register_phase']==phase and r.get('register_s') is not None]
   timings.append(f'{statistics.median(values):.3f}' if values else '-')
  lines.append('|'+ '|'.join(key)+f'|{n-missing}/{n}|{missing}|'+ '|'.join(rates)+'|'+'/'.join(timings)+'|')
 lines+=['','총 계획 330 trials = FP N30/object 90 + matrix N20/object 240. 5frames/trial. 청크 첫 register=cold, 나머지=warm(추론된 초기화 위치, 캐시 상태 보장 아님). Track FPS는 등록 후 actual-wall 기준. 기존 결과 덮어쓰기 없음.']
 (ROOT/'eval/report'/f'r3_{base.name}.md').write_text('\n'.join(lines)+'\n')
 agg=base/'aggregate';agg.mkdir(exist_ok=True);(agg/'trials.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in actual))
 (agg/'validation.json').write_text(json.dumps(dict(planned=len(actual),observed=sum(not r['missing_trial'] for r in actual),chunks=validation),indent=2))
 from eval.harness.report import report
 for stage in ['pilot','matrix']:
  sub=agg/stage;sub.mkdir(exist_ok=True);selected=[r for key,rows in groups.items() if key[0]==stage for r in rows]
  (sub/'trials.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected));report(sub)
  import shutil
  image=ROOT/'eval/report'/f'r3_{base.name}_{stage}.png';shutil.copyfile(sub/'success.png',image)
  lines+=['',f'![{stage} planned-denominator success]({image.name})']
 completed=sum(not r['missing_trial'] for r in actual);now=time.time();started=json.loads(meta.read_text())['started'];elapsed=max(1,now-started);rate=completed*3600/elapsed
 statuses=[json.loads(f.read_text()) for f in base.glob('*.status.json')];waits=[s['lock_wait_s'] for s in statuses if s.get('lock_wait_s') is not None]
 import statistics,datetime
 remaining=[it for it in json.loads((base/'plan.json').read_text()) if not (base/(it['id']+'.status.json')).exists()]
 wait=statistics.median(waits) if waits else 300
 projected_s=sum(it.get('estimated_slot_s',60)+wait+5 for it in remaining)
 progress=dict(completed=completed,planned=len(actual),missing=len(actual)-completed,trials_per_hour=rate,observed_eta_unix=now+(len(actual)-completed)*3600/rate if rate else None,adaptive_eta_unix=now+projected_s,assumed_queue_wait_s=wait,lock_wait_samples=waits,chunk_failures=sum(s.get('exit') not in (0,None) for s in statuses),timeouts=sum(s.get('exit') in (124,137) for s in statuses))
 (base/'progress.json').write_text(json.dumps(progress,indent=2))
 eta=datetime.datetime.fromtimestamp(now+projected_s).astimezone().isoformat(timespec='seconds')
 lines+=['',f'진행 {completed}/{len(actual)}; observed {rate:.1f} trial/h; adaptive ETA {eta} (queue assumed {wait:.1f}s/chunk, provisional).']
 (ROOT/'eval/report'/f'r3_{base.name}.md').write_text('\n'.join(lines)+'\n')
 return completed
def summarize(base):
 # Plot/scoring CPU work must not contaminate another pair's measurement slot.
 import fcntl
 with open('/tmp/rp_measure.lock','a') as measure, open('/tmp/rp_gpu.lock','a') as gpu:
  for handle in [measure,gpu]:
   deadline=time.monotonic()+900
   while True:
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);break
    except BlockingIOError:
     if time.monotonic()>deadline:raise TimeoutError('report lock wait exceeded900s')
     time.sleep(.1)
  return summarize_unlocked(base)
def optimize_plan(base):
 """Preserve started chunks; regroup only unstarted seeds, target <=210s + cleanup."""
 import statistics,math
 plan=json.loads((base/'plan.json').read_text()); kept=[];todo=defaultdict(list);observed=defaultdict(lambda: {'cold':[],'warm':[]})
 for it in plan:
  dest=base/it['id'];key=(it['stage'],it['p'],it['a'],it['obj'])
  if dest.exists() or (base/(it['id']+'.status.json')).exists():
   kept.append(it)
   f=dest/'trials.jsonl'
   if f.exists():
    for line in f.read_text().splitlines():
     try:r=json.loads(line)
     except json.JSONDecodeError:continue
     if r.get('trial_wall_s'):
      phase='cold' if r['seed']==it['seed'] else 'warm';observed[(it['stage'],it['p'],it['a'])][phase].append(r['trial_wall_s'])
  else:todo[key].extend(range(it['seed'],it['seed']+it['n']))
 fresh=[]
 for key,seeds in todo.items():
  obs=observed[key[:3]];cold=statistics.median(obs['cold']) if obs['cold'] else (60 if key[1]=='fp' else 30);warm=statistics.median(obs['warm']) if obs['warm'] else 30
  # 25% safety margin, max24 reduces unknown-scene risk. Matrix starts conservative until measured.
  size=max(1,min(24,1+int(max(0,210-cold*1.25)/(warm*1.25))))
  seeds=sorted(seeds)
  while seeds:
   block=[seeds.pop(0)]
   while seeds and len(block)<size and seeds[0]==block[-1]+1:block.append(seeds.pop(0))
   stage,p,a,obj=key;fresh.append(dict(id=f'{stage}_{p}_{a}_{obj}_{block[0]:03d}_a{len(block)}',stage=stage,p=p,a=a,obj=obj,seed=block[0],n=len(block),estimated_slot_s=cold+warm*(len(block)-1)))
 revised=kept+fresh
 if revised!=plan:
  backup=base/f'plan_before_{time.time_ns()}.json';backup.write_text(json.dumps(plan,indent=2));(base/'plan.json').write_text(json.dumps(revised,indent=2))
 return revised
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--resume',action='store_true');p.add_argument('--report-only',action='store_true');a=p.parse_args();base=Path(a.out)
 if a.report_only:summarize(base);return
 if a.resume:plan=json.loads((base/'plan.json').read_text())
 else:
  base.mkdir(parents=True,exist_ok=False);plan=[]
  for stage,per,assist,n in [('pilot','fp','on',30)]+[('matrix',p,a,20) for p in ['gt','fp'] for a in ['on','off']]:
   for obj in ['mustard','box','cup']:
    for seed in range(0,n,2):plan.append(dict(id=f'{stage}_{per}_{assist}_{obj}_{seed:03d}',stage=stage,p=per,a=assist,obj=obj,seed=seed,n=min(2,n-seed)))
  (base/'plan.json').write_text(json.dumps(plan,indent=2))
 summarize(base)
 while True:
  plan=optimize_plan(base)
  pending=[it for it in plan if not (base/(it['id']+'.status.json')).exists()]
  if not pending:break
  it=pending[0]
  dest=base/it['id'];status=base/(it['id']+'.status.json')
  if status.exists():continue
  if dest.exists():
   status.write_text(json.dumps(dict(exit=None,reason='previous interrupted chunk preserved; no overwrite')));continue
  while True:
   free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()[0])
   if free>=4200:break
   print('VRAM wait',free,flush=True);time.sleep(15)
  cmd=[sys.executable,'-m','eval.run_benchmark','--perception',it['p'],'--gt-assist',it['a'],'--objects',it['obj'],'--n',str(it['n']),'--seed',str(it['seed']),'--pick','on' if it['stage']=='matrix' else 'off','--out',str(dest)]
  acquired=base/(it['id']+'.lock_acquired.txt')
  submitted=time.time()
  shell='date +%s.%N > '+shlex.quote(str(acquired))+'; date; uptime; nvidia-smi; ps -eo pid,pcpu,pmem,args --sort=-pcpu | head -20; timeout --signal=INT --kill-after=5s 225s '+shlex.join(cmd)+'; code=$?; nvidia-smi; exit "$code"'
  print('START',it['id'],flush=True)
  logpath=base/(it['id']+'.env.txt')
  if logpath.exists():logpath=base/(it['id']+f'.retry_{time.time_ns()}.env.txt')
  with logpath.open('x') as log:r=subprocess.run(['flock','-w','900','/tmp/rp_measure.lock','flock','-w','900','/tmp/rp_gpu.lock','timeout','--signal=INT','--kill-after=5s','235s','bash','-c',shell],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  status.write_text(json.dumps(dict(exit=r.returncode,ended=time.time(),submitted=submitted,lock_wait_s=float(acquired.read_text())-submitted if acquired.exists() else None,slot_s=time.time()-float(acquired.read_text()) if acquired.exists() else None)))
  print('DONE',it['id'],r.returncode,'rows',summarize(base),flush=True)
  time.sleep(5) # yield between measurement slots
if __name__=='__main__':main()