set -euo pipefail
cd "$(dirname "$0")/../.."
source ~/miniforge3/etc/profile.d/conda.sh
conda activate robot_percept
python -m pytest tests/m2a -q | tee m2a/notes/wsb_pytest.txt
flock -w 900 /tmp/rp_measure.lock timeout 300s env PYTHONHASHSEED=0 python - <<'PY'
import csv
import platform
from importlib.metadata import version
from runpy import run_path
from statistics import median, mean, quantiles
from collections import Counter
D = run_path('tests/m2a/test_b_plan.py')
fixtures = {case: D['fixture'](case) for case in D['CASES']}
for s,g,l in fixtures.values():
    assert D['plan'](s,g,l)['ok']
rows = []
for rep in range(30):
    for case,(s,g,l) in fixtures.items():
        res = D['plan'](s,g,l)
        assert D['verify'](s,g,res,l)['ok'], res
        names = Counter(a[0] for a in res['actions'])
        rows.append((rep+1,case,res['plan_ms'],len(res['actions']),names['handover'],names['put-aside']))
with open('m2a/notes/wsb_plan_ms.csv','w',newline='') as f:
    writer = csv.writer(f, lineterminator='\n')
    writer.writerow(('repeat','case','plan_ms','actions','handovers','put_asides'))
    writer.writerows(rows)
print(platform.python_version(), version('pyperplan'), platform.platform())
for case in ('all', *fixtures):
    picked = [r for r in rows if case == 'all' or r[1] == case]
    v = [r[2] for r in picked]
    qual = sorted(set(r[3:] for r in picked))
    print(case, len(v), *(f'{x:.3f}' for x in (min(v), median(v), mean(v), quantiles(v,n=100,method='inclusive')[94],max(v))), qual)
PY
git status --short -uall
