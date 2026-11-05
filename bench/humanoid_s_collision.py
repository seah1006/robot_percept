"""Synthetic GT auxiliary prototype; no production integration or collision PASS claim."""
import json,types,subprocess,time,math,numpy as np
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_collision import CapsuleModel,closest_segments,closest_segments_batch,braking_margin
from tools import humanoid_synth as hs

def run():
 src=subprocess.check_output(['git','show','1da4b93:sim/humanoid_teleop.py'],text=True);mod=types.ModuleType('sim._collision_baseline');mod.__package__='sim';exec(compile(src,'baseline','exec'),mod.__dict__)
 env=HumanoidEnv(setpoint_scale=None);s=mod.HumanoidServo(env);caps=CapsuleModel(env.model);old=hs.frame;_,_,f,tor=old(0);poses=[];sample=None;nextsample=0.;nextread=1.;sample_dt=24/378
 def frame(t):
  k=.5-.5*math.cos(2*math.pi*(t%12)/12)
  return True,{z:(.4+k,.15-.75*k,.9+.5*k,0,0) for z in ('left','right')},f,tor
 hs.frame=frame
 try:
  audit=caps.mesh_audit(env.data.qpos);envelope=caps.mesh_envelope_radii(env.data.qpos);envelope_rest=CapsuleModel(env.model,envelope).minimum(env.data.qpos)["distance"]
  for i in range(12501):
   t=i*.002
   if t>=nextsample-1e-9:sample,_=hs.payload(t);sample['received_at']=100+t;nextsample+=1/30
   s.tick(sample,{'enabled':True},100+t);env.step()
   if t>=nextread-1e-9 and len(poses)<378:poses.append(env.data.qpos.copy());nextread+=sample_dt
  poses=np.array(poses);base=[caps.minimum(q)['distance'] for q in poses]
  previous=poses[0].copy();safe=[];compute=[];project_ms=[];path_ms=[];held=0;accepted=0;paths=[];xraw=[];xsafe=[];perpair={}
  for target in poses:
   t0=time.perf_counter();q,diag=caps.project(target,enabled=True);t1=time.perf_counter()
   gap=caps.sampled_path(previous,q,4);t2=time.perf_counter();project_ms.append((t1-t0)*1000);path_ms.append((t2-t1)*1000)
   if diag['accepted'] and gap>=.005:previous=q;accepted+=1
   else:held+=1
   paths.append(gap);safe.append(caps.minimum(previous)['distance']);compute.append((time.perf_counter()-t0)*1000)
   caps.forward(target);xraw.append(float(caps.caps['right_hand'].b[0]));caps.forward(previous);xsafe.append(float(caps.caps['right_hand'].b[0]))
   for r in caps.distances():perpair['|'.join(r['pair'])]=min(perpair.get('|'.join(r['pair']),1.),float(r['distance']))
  x=np.array(xraw);y=np.array(xsafe);lag=None
  if np.std(y)>1e-5:
   scores=[np.corrcoef(x[:len(x)-k or None],y[k:])[0,1] for k in range(32)];lag=int(np.nanargmax(scores))*sample_dt*1000
  # One closest-point Jacobian directional derivative cross-check.
  q=poses[50].copy();caps.forward(q);r=min(caps.distances(True),key=lambda z:z['distance']);g=r['gradient'];direction=np.random.default_rng(0).normal(size=len(g));eps=1e-6
  qp=q.copy();qm=q.copy();qp[caps.qadr]+=eps*direction;qm[caps.qadr]-=eps*direction
  def pairgap(qv):caps.forward(qv);return next(z['distance'] for z in caps.distances() if z['pair']==r['pair'])
  numeric=(pairgap(qp)-pairgap(qm))/(2*eps)
  return dict(load=open('/proc/loadavg').read().strip(),n=len(poses),legacy_reference=dict(min_mm=min(base)*1000,below0=int(np.sum(np.array(base)<0)),note='same analytic sweep, 378 UNIFORM simulated-clock observations from t1..25; NOT original HTTP poll timestamps'),mesh_audit=audit,mesh_envelope_proposal=dict(radii=envelope,rest_clearance_mm=envelope_rest*1000,note="rest-pose enclosure only; if rest overlaps, refine multi-capsules, do not shrink radii"),avoidance=dict(min_mm=min(safe)*1000,below0=int(np.sum(np.array(safe)<0)),accepted=accepted,held=held,held_fraction=held/len(poses),project_p95_ms=float(np.percentile(project_ms,95)),path_check_p95_ms=float(np.percentile(path_ms,95)),compute_p50_ms=float(np.percentile(compute,50)),compute_p95_ms=float(np.percentile(compute,95)),position_lag_proxy_ms=lag,palm_x_rms_error_mm=float(np.sqrt(np.mean((x-y)**2))*1000),sampled_path_note='4-subdivision finite candidate-path check only; rejected paths hold last accepted q; NO actual physics/path-continuity certification'),gradient_check=dict(analytic=float(g@direction),numeric=float(numeric),absolute_error=float(abs(g@direction-numeric))),braking_example=braking_margin(.03,.25),perpair_safe_min_mm={k:v*1000 for k,v in perpair.items()},production_enabled=False)
 finally:env.close();hs.frame=old
if __name__=='__main__':print(json.dumps(run(),indent=2),flush=True)
def test_segment_distance_degenerate_parallel_and_intersection():
 for a,b,c,d,expected in [([0,0,0],[0,0,0],[1,0,0],[1,0,0],1.),([0,0,0],[1,0,0],[0,1,0],[1,1,0],1.),([-1,0,0],[1,0,0],[0,-1,0],[0,1,0],0.)]:
  p,q,_,_=closest_segments(a,b,c,d);assert np.isclose(np.linalg.norm(p-q),expected)

def test_braking_margin_includes_reaction_and_stopping_distance():
 d=braking_margin(.03,.25,deceleration=2.,reaction_s=.02,base=.005)
 assert np.isclose(d['required'],.025625) and not d['brake']
 assert braking_margin(.01,.25)['brake']
def test_vectorized_closest_points_match_scalar():
 rng=np.random.default_rng(7);p=[rng.normal(size=(100,3)) for _ in range(4)];p[1][0]=p[0][0];p[3][1]=p[2][1]
 a,b,_,_=closest_segments_batch(*p)
 for i in range(100):
  x,y,_,_=closest_segments(*(v[i] for v in p));assert np.isclose(np.linalg.norm(a[i]-b[i]),np.linalg.norm(x-y),atol=1e-10)