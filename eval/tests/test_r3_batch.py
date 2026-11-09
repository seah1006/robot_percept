import json
from eval.r3_batch import optimize_plan

def test_adaptive_preserves_started_and_seeds(tmp_path):
 plan=[dict(id=f'old_{i}',stage='pilot',p='fp',a='on',obj='mustard',seed=i,n=2) for i in range(0,30,2)]
 (tmp_path/'plan.json').write_text(json.dumps(plan))
 started=tmp_path/'old_0';started.mkdir()
 rows=[dict(seed=0,trial_wall_s=31),dict(seed=1,trial_wall_s=5)]
 (started/'trials.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 new=optimize_plan(tmp_path)
 assert new[0]==plan[0]
 assert sorted(s for it in new for s in range(it['seed'],it['seed']+it['n']))==list(range(30))
 assert 8<max(it['n'] for it in new)<=24
 assert all(it.get('estimated_slot_s',0)<=210 for it in new)
 assert (started/'trials.jsonl').read_text()==''.join(json.dumps(r)+'\n' for r in rows)
 assert optimize_plan(tmp_path)==new