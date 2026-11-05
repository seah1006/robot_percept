"""GT auxiliary static synthetic sweep. Run under rp_measure.lock."""
import json, time
import numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools.humanoid_synth import payload

def run():
    env=HumanoidEnv(); servo=HumanoidServo(env); rows=[]
    try:
        for iters in (8,16,32):
            for wr,we in ((.25,.35),(.1,1.),(.025,1.),(0.,1.)):
                metrics=[]
                for t in (0.,3.,4.,5.5,6.5,7.5,8.5,9.5,10.5,11.5,12.5):
                    p,gt=payload(t)
                    for side in ('left','right'):
                        ik=servo.iks[side]; ik.w_rot=wr;ik.w_elbow=we
                        orig=ik.solve
                        def solve(*a,**kw):kw['iters']=iters;return orig(*a,**kw)
                        ik.solve=solve
                        servo.q_ik[side]=ik.rest.copy()
                        servo._retarget(p)
                        q=servo.q_ik[side]
                        # Static settling: another 8 warm-start calls.
                        for _ in range(8):servo._retarget(p)
                        ik.solve=orig
                        d=ik.fk(env.data.qpos,servo.q_ik[side]);R=d.xmat[servo.torso_body].reshape(3,3)
                        sh=d.xpos[env.model.body(f'{side}_shoulder_roll_link').id]
                        el=d.site_xpos[ik.site['elbow_site']];w=d.site_xpos[ik.site['wrist_site']]
                        angles=[]
                        for v,key in ((el-sh,'u1'),(w-el,'u2')):
                            v=R.T@v;v/=np.linalg.norm(v);u=np.array(gt[side][key]);u/=np.linalg.norm(u)
                            angles.append(float(np.degrees(np.arccos(np.clip(v@u,-1,1)))))
                        metrics.append([*angles,servo.diag[side]['pos_err_mm'],servo.diag[side]['time_ms']])
                a=np.array(metrics);rows.append(dict(iters=iters,w_rot=wr,w_elbow=we,max=a.max(0).round(3).tolist(),p95=np.percentile(a,95,axis=0).round(3).tolist()))
        print(json.dumps(rows,indent=2))
    finally:env.close()
if __name__=='__main__':run()