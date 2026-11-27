"""CPU regression checks for round 3 selection and matched statistics."""
from itertools import islice
import numpy as np
from m2a.data.eval_f3 import METHODS, paired
from m2a.data.recorder import mirror_action, mirror_state
from m2a.data.round3 import TASKS, dev_cases


def test_dev_has_twenty_right_arm_cases_per_part():
    for part in TASKS:
        cases = list(islice(dev_cases(part),20))
        assert len({c[0]['seed'] for c in cases}) == 20
        for spec,oid,arm,digest,pid in cases:
            assert 10000 <= spec['seed'] <= 10199 and spec['split'] == 'dev'
            assert arm=='right' and pid==part and len(digest)>7
            assert len(spec['objects']) in (1,2,3)
            assert next(o for o in spec['objects'] if o['oid']==oid)['part_id']==pid
            assert any(part in parts for parts in spec['expected']['goal']['trays'].values())


def test_paired_excludes_incomplete_triples_and_uses_same_scene():
    rows=[dict(method=m, seed=10000+i,scene_digest=str(i),ok=m!='ACT',reason_code='GRASP_SLIP')
          for m in METHODS for i in range(4)]
    rows.append(dict(method='IK',seed=10020,scene_digest='x',ok=False,reason_code='IK_FAIL'))
    out=paired(list(reversed(rows)),100)
    assert out['n']==4 and out['methods']['ACT']['success']==0
    assert out['paired']['ACT-IK']['bootstrap95']==[-1.,-1.]
    assert out['paired']['SmolVLA-IK']['conclusion']=='차이 입증 안 됨'


def test_mirror_action_and_state_roundtrip_vectorized():
    rng=np.random.default_rng(41)
    action=rng.normal(size=(5,7)); states=rng.normal(size=(5,15)).astype(np.float32)
    q=states[:,3:7]; q/=np.linalg.norm(q,axis=1,keepdims=True)
    q*=np.sign(q[np.arange(len(q)),np.abs(q).argmax(axis=1)])[:,None]
    np.testing.assert_allclose(mirror_action(mirror_action(action)),action)
    np.testing.assert_allclose(mirror_state(mirror_state(states)),states)
