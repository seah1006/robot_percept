"""Opt-in capsule collision prototype. Not connected to the production servo.

reference radii reproduce V-S proxy geometry; mesh_audit reports uncovered mesh
vertices rather than claiming these radii conservatively enclose the robot.
Faces/fingers/environment and adjacent same-arm links are outside this proxy.
"""
from dataclasses import dataclass
import numpy as np
import mujoco

DEFAULT_ENABLED = False
REFERENCE_RADII = {'torso': .09, 'upper': .045, 'fore': .045, 'hand': .05}
MESH_RADII = {'torso': .118, 'upper': .053, 'fore': .045, 'hand': .057}
PAIRS = [('torso',f'{s}_{p}') for s in ('left','right') for p in ('fore','hand')] + [(f'left_{a}',f'right_{b}') for a in ('upper','fore','hand') for b in ('upper','fore','hand')]

def closest_segments(p0,p1,q0,q1):
    """Closest points and parameters; handles points, parallel and collinear segments."""
    p0,p1,q0,q1=(np.asarray(v,float) for v in (p0,p1,q0,q1))
    if any(v.shape!=(3,) or not np.isfinite(v).all() for v in (p0,p1,q0,q1)):raise ValueError('finite xyz endpoints required')
    d1,d2,r=p1-p0,q1-q0,p0-q0;a=float(d1@d1);e=float(d2@d2);f=float(d2@r)
    if a<1e-12 and e<1e-12:s=t=0.
    elif a<1e-12:s=0.;t=float(np.clip(f/e,0,1))
    else:
        c=float(d1@r)
        if e<1e-12:t=0.;s=float(np.clip(-c/a,0,1))
        else:
            b=float(d1@d2);den=a*e-b*b
            s=float(np.clip((b*f-c*e)/den,0,1)) if den>1e-12 else 0.
            t=(b*s+f)/e
            if t<0:t=0.;s=float(np.clip(-c/a,0,1))
            elif t>1:t=1.;s=float(np.clip((b-c)/a,0,1))
    return p0+s*d1,q0+t*d2,s,t

def closest_segments_batch(p0,p1,q0,q1):
    """Vectorized closed-form closest segment points (N,3)."""
    d1=p1-p0;d2=q1-q0;r=p0-q0
    dot=lambda a,b:np.einsum('ij,ij->i',a,b)
    a=dot(d1,d1);e=dot(d2,d2);b=dot(d1,d2);c=dot(d1,r);f=dot(d2,r)
    den=a*e-b*b;safe_a=np.maximum(a,1e-12);safe_e=np.maximum(e,1e-12)
    s=np.clip(np.divide(b*f-c*e,den,out=np.zeros_like(a),where=den>1e-12),0,1)
    t=(b*s+f)/safe_e
    s=np.where(t<0,np.clip(-c/safe_a,0,1),np.where(t>1,np.clip((b-c)/safe_a,0,1),s));t=np.clip(t,0,1)
    s=np.where(e<1e-12,np.clip(-c/safe_a,0,1),s);t=np.where(e<1e-12,0,t)
    s=np.where(a<1e-12,0,s);t=np.where(a<1e-12,np.clip(f/safe_e,0,1),t)
    return p0+s[:,None]*d1,q0+t[:,None]*d2,s,t

def braking_margin(clearance,closing_speed,deceleration=2.,reaction_s=.02,base=.005):
    """Cartesian proxy stopping margin, not a validated physical deceleration bound."""
    speed=max(0.,float(closing_speed));required=base+speed*reaction_s+speed*speed/(2*max(deceleration,1e-6))
    return dict(required=required,available=float(clearance),brake=bool(clearance<required),stop_s=speed/max(deceleration,1e-6))

@dataclass
class Capsule:
    a: np.ndarray
    b: np.ndarray
    radius: float

class CapsuleModel:
    def __init__(self,model,radii=None):
        self.m=model;self.d=mujoco.MjData(model);self.radii=dict(REFERENCE_RADII if radii is None else radii)
        self.bid={n:model.body(n).id for n in ['pelvis']+[f'{s}_{n}' for s in ('left','right') for n in ('shoulder_roll_link','elbow_link','wrist_pitch_link','wrist_yaw_link')]}
        self.names=[f'{s}_{n}_joint' for s in ('left','right') for n in ('shoulder_pitch','shoulder_roll','shoulder_yaw','elbow','wrist_roll','wrist_pitch','wrist_yaw')]+['waist_yaw_joint','waist_roll_joint','waist_pitch_joint']
        joints=[model.joint(n).id for n in self.names];self.qadr=model.jnt_qposadr[joints];self.dofs=model.jnt_dofadr[joints]
        self.lo=model.jnt_range[joints,0];self.hi=model.jnt_range[joints,1];self.previous_normals={}
        self._jp=np.zeros((3,model.nv));self.fk_calls=0
        self._cap_names=['torso']+[f'{s}_{p}' for s in ('left','right') for p in ('upper','fore','hand')]
        cap_index={name:i for i,name in enumerate(self._cap_names)}
        self._pair_left=np.array([cap_index[a] for a,_ in PAIRS]);self._pair_right=np.array([cap_index[b] for _,b in PAIRS])
    def forward(self,qpos):
        self.fk_calls+=1
        qpos=np.asarray(qpos,float)
        if qpos.shape!=(self.m.nq,) or not np.isfinite(qpos).all():raise ValueError('finite full qpos required')
        self.d.qpos[:]=qpos;mujoco.mj_kinematics(self.m,self.d);mujoco.mj_comPos(self.m,self.d)
        d=self.d;self.anchors={};self._jac_cache={}
        anchor=lambda body,off=(0.,0.,0.):[(self.bid[body],np.array(off),1.)]
        self.anchors['torso']=(anchor('pelvis'),[(self.bid[f'{s}_shoulder_roll_link'],np.zeros(3),.5) for s in ('left','right')])
        for s in ('left','right'):
            S=anchor(f'{s}_shoulder_roll_link');E=anchor(f'{s}_elbow_link');W=anchor(f'{s}_wrist_pitch_link');H=anchor(f'{s}_wrist_yaw_link',(.09,0,0))
            self.anchors[s+'_upper']=(S,E);self.anchors[s+'_fore']=(E,W);self.anchors[s+'_hand']=(W,H)
        self.caps={}
        for n,(a,b) in self.anchors.items():self.caps[n]=Capsule(self.point(a),self.point(b),self.radii[n.split('_')[-1]])
        ordered=[self.caps[n] for n in self._cap_names]
        self._cap_a=np.array([c.a for c in ordered]);self._cap_b=np.array([c.b for c in ordered]);self._cap_r=np.array([c.radius for c in ordered])
        return self.caps
    def point(self,anchor):
        return sum(w*(self.d.xpos[b]+self.d.xmat[b].reshape(3,3)@p) for b,p,w in anchor)
    def jacobian(self,anchor):
        key=tuple((b,tuple(p),w) for b,p,w in anchor)
        if key in self._jac_cache:return self._jac_cache[key]
        J=np.zeros((3,len(self.dofs)))
        for b,p,w in anchor:
            point=self.d.xpos[b]+self.d.xmat[b].reshape(3,3)@p
            mujoco.mj_jac(self.m,self.d,self._jp,None,point,b);J+=w*self._jp[:,self.dofs]
        self._jac_cache[key]=J
        return J
    def distances(self,with_grad=False,active_distance=float("inf")):
        out=[]
        arrays=[self._cap_a[self._pair_left],self._cap_b[self._pair_left],self._cap_a[self._pair_right],self._cap_b[self._pair_right]]
        total_radius=self._cap_r[self._pair_left]+self._cap_r[self._pair_right]
        low_a=np.minimum(arrays[0],arrays[1]);hi_a=np.maximum(arrays[0],arrays[1]);low_b=np.minimum(arrays[2],arrays[3]);hi_b=np.maximum(arrays[2],arrays[3])
        separation=np.maximum(np.maximum(low_a-hi_b,low_b-hi_a),0.)
        lower=np.linalg.norm(separation,axis=1)-total_radius
        mask=lower<active_distance if with_grad else np.ones(len(PAIRS),dtype=bool)
        points=np.zeros_like(arrays[0]);others=points.copy();ss=np.zeros(len(PAIRS));tt=ss.copy()
        points[mask],others[mask],ss[mask],tt[mask]=closest_segments_batch(*(a[mask] for a in arrays))
        for index,(left,right) in enumerate(PAIRS):
            a,b=self.caps[left],self.caps[right];p,q,s,t=points[index],others[index],ss[index],tt[index];v=p-q;length=float(np.linalg.norm(v)) if mask[index] else lower[index]+total_radius[index];key=(left,right)
            normal=v/length if mask[index] and length>1e-9 else self.previous_normals.get(key,np.array([0.,1.,0.]))
            self.previous_normals[key]=normal
            row=dict(pair=key,distance=length-a.radius-b.radius,normal=normal)
            if with_grad and row["distance"]<active_distance:
                la,lb=self.anchors[left];ra,rb=self.anchors[right]
                row['gradient']=normal@((1-s)*self.jacobian(la)+s*self.jacobian(lb)-(1-t)*self.jacobian(ra)-t*self.jacobian(rb))
            out.append(row)
        return out
    def minimum_distance(self,qpos):
        """Exact proxy minimum for planner samples, retaining normal history."""
        self.forward(qpos)
        p,q,_,_=closest_segments_batch(self._cap_a[self._pair_left],self._cap_b[self._pair_left],self._cap_a[self._pair_right],self._cap_b[self._pair_right])
        delta=p-q;length=np.linalg.norm(delta,axis=1)
        for i,key in enumerate(PAIRS):
            if length[i]>1e-9:self.previous_normals[key]=delta[i]/length[i]
        return float(np.min(length-self._cap_r[self._pair_left]-self._cap_r[self._pair_right]))
    def minimum(self,qpos):
        self.forward(qpos);return min(self.distances(),key=lambda r:r['distance'])
    def project(self,qpos,margin=.005,iterations=5,max_step=.12,enabled=DEFAULT_ENABLED):
        """Coupled arm/waist position projection; no physical/path safety guarantee."""
        q=np.array(qpos,copy=True);active=0
        if not enabled:
            gap=self.minimum(q)['distance']
            return q,dict(distance=gap,active=0,accepted=bool(gap>=margin),enabled=False)
        for _ in range(iterations):
            self.forward(q);rows=self.distances(True,margin);dq=np.zeros(len(self.dofs));active=0
            for r in rows:
                if r['distance']<margin:
                    g=r['gradient'];dq+=g*((margin-r['distance'])/(g@g+1e-9));active+=1
            if not active:
                gap=min(r['distance'] for r in rows)
                return q,dict(distance=gap,active=0,accepted=bool(gap>=margin),broadphase=True)
            dq*=min(1.,max_step/max(float(np.max(np.abs(dq))),1e-12));q[self.qadr]=np.clip(q[self.qadr]+dq,self.lo+1e-4,self.hi-1e-4)
        gap=self.minimum(q)['distance'];return q,dict(distance=gap,active=active,accepted=bool(gap>=margin))
    def approach_safe(self,start,target,margin=.01):
        """Maximal sampled straight-path progress, not a global closest IK pose."""
        if self.minimum(start)['distance']<margin:return np.array(start,copy=True),dict(distance=self.minimum(start)['distance'],active=0,accepted=False,progress_fraction=0.)
        lo=0.;hi=1.
        for fraction in np.linspace(.125,1.,8):
            q=start+(target-start)*fraction
            if self.minimum(q)['distance']<margin:hi=float(fraction);break
            lo=float(fraction)
        if lo<1:
            for _ in range(6):
                mid=(lo+hi)*.5
                if self.minimum(start+(target-start)*mid)['distance']>=margin:lo=mid
                else:hi=mid
        q=start+(target-start)*lo;gap=self.minimum(q)['distance']
        return q,dict(distance=gap,active=0,accepted=bool(lo>1e-5 and gap>=margin),progress_fraction=lo,partial=True)

    def plan_safe_waypoint(self,start,target,margin=.003,waypoint_margin=.012,steps=48):
        """Return the next waypoint on a finite-sample collision-free route.

        This is a capsule-proxy planner, not continuous or physical safety
        certification. Unlike ``approach_safe``, it may go around a colliding
        straight segment by projecting its worst sample away from the obstacle.
        """
        start=np.asarray(start,float);target=np.asarray(target,float)
        endpoint,_=self.project(target,margin=margin,iterations=12,max_step=.16,enabled=True)
        endpoint_modified=bool(np.max(np.abs(endpoint[self.qadr]-target[self.qadr]))>1e-5)
        def segment(a,b,n=steps):
            gaps=[self.minimum_distance(a+(b-a)*(k/n)) for k in range(n+1)]
            return gaps,float(min(gaps)),int(np.argmin(gaps))
        samples,direct_min,worst=segment(start,endpoint)
        final_normals=dict(self.previous_normals)
        start_gap=self.minimum_distance(start);endpoint_gap=self.minimum_distance(endpoint)
        self.previous_normals=final_normals
        # Rest targets project to exactly 10mm. Requiring a further 2mm gain
        # makes 8~10mm command starts permanently infeasible after a brake.
        # Keep the endpoint margin and reject any path below its entry gap.
        escaping=(start_gap<margin and endpoint_gap>=margin-1e-8
                  and endpoint_gap>start_gap+1e-6
                  and min(samples)>=start_gap-1e-6 and min(np.diff(samples))>=-2e-4)
        if direct_min>=margin or escaping:
            return endpoint,dict(accepted=True,route='escape_direct' if escaping else 'direct',path_min=direct_min,distance=endpoint_gap,start_gap=start_gap,samples=steps,endpoint_modified=endpoint_modified)
        bad=start+(endpoint-start)*(worst/steps)
        for clearance in (waypoint_margin,.02,.03):
            waypoint,diag=self.project(bad,margin=clearance,iterations=20,max_step=.2,enabled=True)
            if not diag.get('accepted'):continue
            _,first_min,_=segment(start,waypoint);_,second_min,_=segment(waypoint,endpoint)
            if min(first_min,second_min)>=margin:
                return waypoint,dict(accepted=True,route='projected_waypoint',path_min=min(first_min,second_min),first_min=first_min,second_min=second_min,distance=self.minimum(waypoint)['distance'],waypoint_margin=clearance,endpoint_modified=endpoint_modified)
        partial,diag=self.approach_safe(start,endpoint,margin=margin)
        diag.update(route='partial_fallback',path_min=self.sampled_path(start,partial,steps),endpoint_modified=endpoint_modified)
        return partial,diag

    def sampled_path(self,start,end,steps=4):
        """Finite samples ONLY. Integration must add a continuous-motion bound."""
        return min(self.minimum(start+(end-start)*(k/steps))['distance'] for k in range(steps+1))
    def mesh_audit(self,qpos):
        """Radial extent of selected G1 visual mesh vertices at this configuration.

        Finger meshes and pelvis shell are excluded from palm/torso audits.
        A radius here is a surrogate, not a full swept mesh enclosure.
        """
        self.forward(qpos);m=self.m;d=self.d;groups={'torso':['torso_link']}
        for s in ('left','right'):
            groups[s+'_upper']=[s+'_shoulder_roll_link',s+'_shoulder_yaw_link'];groups[s+'_fore']=[s+'_elbow_link',s+'_wrist_roll_link',s+'_wrist_pitch_link'];groups[s+'_hand']=[s+'_wrist_yaw_link']
        out={}
        for name,bodies in groups.items():
            ids={m.body(b).id for b in bodies};caps=self.caps[name];v=[];union_gaps=[]
            for g in range(m.ngeom):
                if m.geom_bodyid[g] not in ids or m.geom_group[g]!=2 or m.geom_type[g]!=mujoco.mjtGeom.mjGEOM_MESH:continue
                mid=m.geom_dataid[g]
                if name=='torso' and 'head' in m.mesh(mid).name:continue
                verts=m.mesh_vert[m.mesh_vertadr[mid]:m.mesh_vertadr[mid]+m.mesh_vertnum[mid]]
                world=verts@d.geom_xmat[g].reshape(3,3).T+d.geom_xpos[g]
                axis=caps.b-caps.a;u=np.clip((world-caps.a)@axis/max(axis@axis,1e-12),0,1);v.extend(np.linalg.norm(world-(caps.a+u[:,None]*axis),axis=1).tolist())
                signed=[]
                for proxy in self.caps.values():
                    ab=proxy.b-proxy.a;param=np.clip((world-proxy.a)@ab/max(ab@ab,1e-12),0,1)
                    signed.append(np.linalg.norm(world-(proxy.a+param[:,None]*ab),axis=1)-proxy.radius)
                union_gaps.extend(np.min(np.array(signed),axis=0).tolist())
            if v:out[name]=dict(radius_mm=caps.radius*1000,mesh_radial_p95_mm=float(np.percentile(v,95)*1000),mesh_radial_max_mm=max(v)*1000,uncovered_vertices=sum(x>caps.radius for x in v),vertices=len(v),union_uncovered_vertices=sum(x>0 for x in union_gaps),union_max_outside_mm=max(0.,max(union_gaps))*1000)
        return out
    def mesh_envelope_radii(self,qpos,padding=.005):
        """Rest-configuration envelope proposal only; moving-joint fit needs audit.

        Larger radii can make rest already infeasible. Do not silently shrink
        them to pass a collision gate; refine the capsule decomposition instead.
        """
        audit=self.mesh_audit(qpos);radii=dict(self.radii)
        for name,row in audit.items():
            kind=name.split('_')[-1]
            radii[kind]=max(radii[kind],row['mesh_radial_max_mm']/1000+padding)
        return radii
class CollisionPathMonitor:
    """Conservative motion-bound monitor, NOT an emergency stopping controller.

    Accumulated absolute joint variation (not net displacement) gives a bound
    on all intermediate segment motions. Nonpositive bounds are reported as
    uncertified and force a fresh FK, never silently called continuously safe.
    """
    def __init__(self,model,refresh_margin=.002,radii=None,adaptive_refresh=True):
        self.adaptive_refresh=adaptive_refresh;self.geometry=CapsuleModel(model,radii);self.margin=refresh_margin;self.anchor=None;self.last=None;self.variation=np.zeros(len(self.geometry.qadr));self.gaps=None;self.coefficients=None
        self.min_actual=float('inf');self.uncertified=0;self.penetrating=0;self.exact_checks=0
    def _anchor_coefficients(self,anchor):
        m=self.geometry.m;out=np.zeros(len(self.geometry.dofs));lookup={int(m.jnt_bodyid[m.joint(n).id]):i for i,n in enumerate(self.geometry.names)}
        for body,offset,weight in anchor:
            radius=float(np.linalg.norm(offset));b=body
            while b>0:
                if b in lookup:out[lookup[b]]+=weight*(radius+float(np.linalg.norm(m.jnt_pos[m.joint(self.geometry.names[lookup[b]]).id])))
                radius+=float(np.linalg.norm(m.body_pos[b]));b=int(m.body_parentid[b])
        return out
    def inspect(self,qpos):
        q=np.asarray(qpos);g=self.geometry
        delta=np.zeros(len(g.qadr)) if self.last is None else np.abs(q[g.qadr]-self.last[g.qadr])
        self.variation+=delta
        self.last=q.copy();bound=None if self.gaps is None else self.gaps-self.coefficients@self.variation
        certified=bool(bound is not None and np.min(bound)>=0)
        step_motion=0. if self.coefficients is None else float(np.max(self.coefficients@delta))
        refresh_threshold=self.margin+(2*step_motion if self.adaptive_refresh else 0.)
        if bound is None or np.min(bound)<refresh_threshold:
            if bound is not None and not certified:self.uncertified+=1
            g.forward(q);rows=g.distances();self.gaps=np.array([r['distance'] for r in rows]);self.variation[:]=0.;self.anchor=q.copy();self.exact_checks+=1
            if self.coefficients is None:
                c={n:np.maximum(self._anchor_coefficients(a),self._anchor_coefficients(b)) for n,(a,b) in g.anchors.items()}
                self.coefficients=np.array([c[a]+c[b] for a,b in PAIRS])
            distance=float(np.min(self.gaps));self.min_actual=min(self.min_actual,distance)
            if distance<0:self.penetrating+=1
        else:distance=float(np.min(bound))
        return dict(clearance_lower_bound=distance,continuous_interval_certified=certified,uncertified_intervals=self.uncertified,penetration_checks=self.penetrating,exact_checks=self.exact_checks,step_motion_bound=step_motion,refresh_threshold=refresh_threshold)

def _waypoint_process(connection,model,radii,initial_q):
    import time
    t0=time.monotonic()
    geometry=CapsuleModel(model,radii)
    geometry.plan_safe_waypoint(initial_q,initial_q,margin=.003)
    connection.send({'planner_ready':True,'child_warmup_ms':(time.monotonic()-t0)*1000})
    try:
        while True:
            request=connection.recv()
            if request is None:break
            sequence,start,target,submitted=request;t0=time.monotonic()
            try:
                waypoint,diag=geometry.plan_safe_waypoint(start,target,margin=.010)
                diag=dict(diag,planner_ms=(time.monotonic()-t0)*1000,submitted_at=submitted,
                          completed_at=time.monotonic(),sequence=sequence)
                connection.send((start,target,waypoint,diag))
            except Exception as exc:
                connection.send((start,target,start,dict(accepted=False,error=type(exc).__name__,
                                completed_at=time.monotonic(),sequence=sequence)))
    except (EOFError,BrokenPipeError):pass
    finally:connection.close()


class AsyncWaypointPlanner:
    """10Hz one-in-flight planner process, no shared GIL or MjData.

    Servo retains latest request locally and polls at most one result. Pipe
    capacity cannot accumulate stale requests. No planner locks in servo.
    """
    def __init__(self,model,radii=None,period=.1,initial_q=None,serialized_model=None):
        import socket,subprocess,sys,os,pickle
        from multiprocessing.connection import Connection
        import time
        self.created_at=time.monotonic();self.ready=False;self.prepare_ms=None;self.child_warmup_ms=None
        self.period=period;self._result=None;self.submitted=0;self.completed=0
        self._busy=False;self._closed=False;self._sent_at=-1e6
        left,right=socket.socketpair()
        self._connection=Connection(left.detach())
        child=Connection(right.detach());self._process=None
        import threading
        self._started=False
        def launch():
            try:
                self._process=subprocess.Popen([sys.executable,'-m','sim.humanoid_collision',
                    '--planner-fd',str(child.fileno()),str(os.getpid())],pass_fds=(child.fileno(),),
                    stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
                if self._closed:
                    self._process.terminate();self._process.wait(timeout=1.)
                    self._process.stdin.close();return
                if serialized_model is None:
                    pickle.dump((model,radii,np.array(model.qpos0 if initial_q is None else initial_q,copy=True)),self._process.stdin,protocol=5)
                else:self._process.stdin.write(serialized_model)
                self._process.stdin.close();self._started=True
            except (BrokenPipeError,OSError):self._closed=True
            finally:child.close()
        self._starter=threading.Thread(target=launch,name='planner-start',daemon=True)
        self._starter.start()

    def submit(self,start,target):
        import time
        self.submitted+=1
        self._pending=(self.submitted,np.array(start,copy=True),np.array(target,copy=True),time.monotonic())
        self.latest()

    def latest(self):
        import time
        if self._closed:return self._result
        try:
            if self._connection.poll():
                message=self._connection.recv()
                if isinstance(message,dict) and message.get('planner_ready'):
                    self.ready=True;self.prepare_ms=(time.monotonic()-self.created_at)*1000
                    self.child_warmup_ms=message['child_warmup_ms']
                else:self._result=message;self.completed+=1;self._busy=False
            # Keep the latest request even before child startup. A stationary
            # collision latch may only poll, not retarget, after the first tick.
            now=time.monotonic()
            pending=getattr(self,'_pending',None)
            if self._started and self.ready and not self._busy and pending is not None and now-self._sent_at>=self.period and self._process.poll() is None:
                self._connection.send(pending);self._pending=None
                self._sent_at=now;self._busy=True
        except (EOFError,BrokenPipeError,OSError):self._closed=True
        return self._result

    def diagnostics(self):
        self.latest()
        return dict(planner_ready=bool(self.ready and not self._closed and self._process is not None and self._process.poll() is None),
                    planner_prepare_ms=self.prepare_ms,planner_child_warmup_ms=self.child_warmup_ms)

    def close(self):
        self._closed=True
        self._starter.join(timeout=3.)
        if self._process is not None and self._process.poll() is None:
            # Lifecycle cleanup only, never called by a normal servo tick.
            import subprocess
            self._process.terminate()
            try:self._process.wait(timeout=1.)
            except subprocess.TimeoutExpired:self._process.kill();self._process.wait(timeout=1.)
        self._connection.close();self._closed=True


if __name__=='__main__':
    import sys,os,time,threading,pickle
    from multiprocessing.connection import Connection
    if len(sys.argv)==4 and sys.argv[1]=='--planner-fd':
        parent=int(sys.argv[3])
        def watch_parent():
            while os.getppid()==parent:time.sleep(.1)
            os._exit(0)
        threading.Thread(target=watch_parent,name='planner-parent-watch',daemon=True).start()
        model,radii,initial_q=pickle.load(sys.stdin.buffer)
        _waypoint_process(Connection(int(sys.argv[2])),model,radii,initial_q)
