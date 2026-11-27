import numpy as np
from scipy.spatial.transform import Rotation as R
from m2a.data.ee_target import ACTION_ENCODING, ACTION_NAMES, apply_target, recover_targets
from m2a.data.recorder import features


def test_recover_targets_uses_left_composition_and_measured_state():
    s=np.zeros((2,15));s[:,:3]=[[.1,-.2,.3],[.2,-.3,.4]]
    s[:,3:7]=R.from_rotvec([[.2,.4,-.3],[-1.,.2,.3]]).as_quat(scalar_first=True)
    d=np.array([[.01,.02,.03,.6,-.2,.4,.8],[.02,.01,.04,-.3,.2,.6,1.]])
    dst=recover_targets(s,d)
    np.testing.assert_allclose(dst[:,:3],s[:,:3]+d[:,:3],atol=3e-8)
    np.testing.assert_allclose(R.from_rotvec(dst[:,3:6]).as_matrix(),
        R.from_rotvec(d[:,3:6]).as_matrix()@R.from_quat(s[:,3:7],scalar_first=True).as_matrix(),atol=1e-7)
    np.testing.assert_allclose(dst[:,6],d[:,6])


def test_same_absolute_goal_across_different_servo_states():
    class Env:
        def ee_pose(self,arm): return self.p,self.r.as_quat(scalar_first=True)
        def apply_ee_delta(self,arm,dp,dr,grip01,dt):
            assert arm=='right' and dt==.1 and grip01==1.
            return self.p+dp,(R.from_rotvec(dr)*self.r).as_matrix()
    env=Env();target=np.array([.1,-.4,.2,.9,-.8,2.8,1.]);
    for mult in (-1,1):
        env.p=np.array([1,0,2])*mult;env.r=R.from_rotvec(np.array([.7,.2,-.4])*mult)
        p,r=apply_target(env,'right',target)
        np.testing.assert_allclose(p,target[:3]);np.testing.assert_allclose(r,R.from_rotvec(target[3:6]).as_matrix())
    assert features(ACTION_ENCODING)['action']['names']==ACTION_NAMES
    assert features(ACTION_ENCODING)['grasp_mode']['dtype']=='string'
