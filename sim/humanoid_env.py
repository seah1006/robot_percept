"""Unitree G1 (29 DoF + Dex3-1 hands) fixed-pelvis upper-body simulation.

Model: MuJoCo Menagerie unitree_g1/g1_with_hands.xml (derived from Unitree's
official g1_29dof_with_hand_rev_1_0 description).  Changes made here:
  * pelvis is welded to the world (freejoint removed): upper-body imitation only,
    legs are position-held at the stand pose.
  * joint effort limits are re-applied from the official URDF
    (unitreerobotics/unitree_ros g1_29dof_with_hand_rev_1_0.urdf, <limit effort>)
    as actuator force ranges (menagerie uses 50 Nm for waist roll/pitch and ankles,
    the URDF says 35 Nm).
  * contacts are disabled (kinematic imitation display; self-collision is not
    simulated), gravity is compensated like sim.env.SimEnv (qfrc_applied=qfrc_bias).
  * lab-like scene: grey floor, gradient skybox, key/fill lights, optional shadows.
"""
from __future__ import annotations
import re
from pathlib import Path
import numpy as np
import mujoco

ROOT = Path(__file__).resolve().parents[1]
G1_DIR = ROOT / 'assets/mujoco_menagerie/unitree_g1'

# Official URDF limits (effort Nm, velocity rad/s as printed in the URDF).  The URDF
# velocity values (20-37 rad/s) are motor-side maxima; the teleop servo uses the much
# lower TELEOP_VEL caps below for smooth, human-like motion.
URDF_EFFORT = {
    'hip_pitch': 88, 'hip_roll': 139, 'hip_yaw': 88, 'knee': 139, 'ankle_pitch': 35, 'ankle_roll': 35,
    'waist_yaw': 88, 'waist_roll': 35, 'waist_pitch': 35,
    'shoulder_pitch': 25, 'shoulder_roll': 25, 'shoulder_yaw': 25, 'elbow': 25,
    'wrist_roll': 25, 'wrist_pitch': 5, 'wrist_yaw': 5,
    'hand_thumb_0': 2.45, 'hand_thumb_1': 1.4, 'hand_thumb_2': 1.4,
    'hand_middle_0': 1.4, 'hand_middle_1': 1.4, 'hand_index_0': 1.4, 'hand_index_1': 1.4,
}
URDF_VELOCITY = {
    'hip_pitch': 32, 'hip_roll': 20, 'hip_yaw': 32, 'knee': 20, 'ankle_pitch': 30, 'ankle_roll': 30,
    'waist_yaw': 32, 'waist_roll': 30, 'waist_pitch': 30,
    'shoulder_pitch': 37, 'shoulder_roll': 37, 'shoulder_yaw': 37, 'elbow': 37,
    'wrist_roll': 37, 'wrist_pitch': 22, 'wrist_yaw': 22,
    'hand_thumb_0': 3.14, 'hand_thumb_1': 12, 'hand_thumb_2': 12,
    'hand_middle_0': 12, 'hand_middle_1': 12, 'hand_index_0': 12, 'hand_index_1': 12,
}
# Teleop caps (rad/s, rad/s^2): well below the URDF maxima.
TELEOP_VEL = {'arm': 3.0, 'wrist': 4.0, 'waist': 1.2, 'hand': 3.0}
TELEOP_ACC = {'arm': 25.0, 'wrist': 30.0, 'waist': 8.0, 'hand': 30.0}

ARM = ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow', 'wrist_roll', 'wrist_pitch', 'wrist_yaw')
HAND = ('thumb_0', 'thumb_1', 'thumb_2', 'index_0', 'index_1', 'middle_0', 'middle_1')
WAIST = ('waist_yaw', 'waist_roll', 'waist_pitch')
LABELS = {
    'shoulder_pitch': '어깨 피치', 'shoulder_roll': '어깨 롤', 'shoulder_yaw': '어깨 요', 'elbow': '팔꿈치',
    'wrist_roll': '손목 롤', 'wrist_pitch': '손목 피치', 'wrist_yaw': '손목 요',
    'waist_yaw': '허리 요', 'waist_roll': '허리 롤', 'waist_pitch': '허리 피치',
    'thumb_0': '엄지 회전', 'thumb_1': '엄지 1', 'thumb_2': '엄지 2', 'index_0': '검지 1', 'index_1': '검지 2',
    'middle_0': '중지 1', 'middle_1': '중지 2',
}
SHORT = {'shoulder_pitch': 'SP', 'shoulder_roll': 'SR', 'shoulder_yaw': 'SY', 'elbow': 'EL',
         'wrist_roll': 'WR', 'wrist_pitch': 'WP', 'wrist_yaw': 'WY', 'waist_yaw': 'TY', 'waist_roll': 'TR', 'waist_pitch': 'TP'}
# Fingertip colours (RGB 0-1) shared with the webcam overlay: thumb, index, middle(+ring/pinky).
TIP_COLORS = {'thumb': (1.0, .42, .42), 'index': (1.0, .80, .25), 'middle': (.30, .85, .45)}
# Rest posture: arms relaxed beside the body, forearm slightly forward.
REST = {'shoulder_pitch': .15, 'shoulder_roll': .18, 'shoulder_yaw': 0., 'elbow': .95,
        'wrist_roll': 0., 'wrist_pitch': 0., 'wrist_yaw': 0.}


def _effort_key(joint):
    j = joint.replace('left_', '').replace('right_', '').replace('_joint', '')
    return j


LOWPOLY_DIR = ROOT / 'assets/g1_lowpoly'   # tools/g1_lowpoly.py output (630k -> 112k triangles)


def build_g1_xml(width=640, height=480, shadows=False, lowpoly=True):
    src = (G1_DIR / 'g1_with_hands.xml').read_text()
    meshdir = LOWPOLY_DIR if lowpoly and (LOWPOLY_DIR / 'torso_link_rev_1_0.STL').exists() else G1_DIR / 'assets'
    src = src.replace('meshdir="assets"', f'meshdir="{meshdir}"')
    src = src.replace('<freejoint name="floating_base_joint"/>', '')
    src = re.sub(r'\s*<keyframe>.*?</keyframe>', '', src, flags=re.S)
    # Remove the model's own light; lighting is defined below.
    src = re.sub(r'<light [^>]*/>', '', src, count=1)
    sites = []
    for side in ('left', 'right'):
        sites.append((f'{side}_elbow_link', f'{side}_elbow_site', '0 0 0'))
        sites.append((f'{side}_wrist_pitch_link', f'{side}_wrist_site', '0 0 0'))
        sites.append((f'{side}_wrist_yaw_link', f'{side}_palm_site', '0.08 0 0'))
        for f, link, pos in (('thumb', 'thumb_2', '0 -0.045 0' if side == 'left' else '0 0.045 0'),
                             ('index', 'index_1', '0.042 0 0'), ('middle', 'middle_1', '0.042 0 0')):
            sites.append((f'{side}_hand_{link}_link', f'{side}_{f}_tip', pos))
    for body, name, pos in sites:
        src = re.sub(rf'(<body name="{body}"[^>]*>)', rf'\1<site name="{name}" pos="{pos}" size="0.006" group="5"/>', src, count=1)
    extra = f'''
  <visual>
    <headlight diffuse=".35 .35 .35" ambient=".25 .25 .27" specular=".05 .05 .05"/>
    <quality shadowsize="{2048 if shadows else 0}" offsamples="4"/>
    <global offwidth="{max(1280, width)}" offheight="{max(960, height)}"/>
    <map znear=".02" zfar="40"/>
  </visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1=".93 .94 .96" rgb2=".62 .66 .72" width="256" height="1536"/>
    <texture type="2d" name="lab_floor" builtin="checker" mark="edge" rgb1=".56 .58 .60" rgb2=".52 .54 .56" markrgb=".42 .44 .47" width="512" height="512"/>
    <material name="lab_floor" texture="lab_floor" texuniform="true" texrepeat="2 2" reflectance="0"/>
    <material name="lab_mat" rgba=".18 .30 .45 1" specular=".1"/>
    <material name="target_wrist" rgba="0.2 0.85 0.6 1"/>
    <material name="target_elbow" rgba="0.3 0.6 1 1"/>
  </asset>
  <worldbody>
    <light name="key" pos="2.2 1.6 3.2" dir="-.55 -.4 -.73" directional="true" diffuse=".55 .55 .53" specular=".2 .2 .2" castshadow="{'true' if shadows else 'false'}"/>
    <light name="fill" pos="-1.5 -2 2.5" dir=".4 .55 -.73" directional="true" diffuse=".22 .23 .26" specular="0 0 0" castshadow="false"/>
    <geom name="floor" type="plane" size="3 3 .5" material="lab_floor" contype="0" conaffinity="0"/>
    <geom name="mat" type="box" size=".45 .45 .004" pos="0 0 .004" material="lab_mat" contype="0" conaffinity="0"/>
    <camera name="front" pos="1.75 0 1.05" xyaxes="0 1 0 -0.11 0 1" fovy="45"/>
    <camera name="side" pos="1.4 1.6 1.2" xyaxes="-0.75 0.66 0 -0.2 -0.23 0.95" fovy="45"/>
'''
    for side in ('left', 'right'):
        extra += f'    <body name="{side}_wrist_target" mocap="true" pos="0 0 -1"><geom type="sphere" size=".022" material="target_wrist" contype="0" conaffinity="0" group="1"/></body>\n'
        extra += f'    <body name="{side}_elbow_target" mocap="true" pos="0 0 -1"><geom type="sphere" size=".016" material="target_elbow" contype="0" conaffinity="0" group="1"/></body>\n'
    extra += '  </worldbody>\n'
    src = src.replace('<worldbody>', extra.split('<worldbody>')[0] + '<worldbody>' + extra.split('<worldbody>')[1].replace('  </worldbody>\n', ''), 1)
    return src


class JointSetpoint:
    """Online acceleration-continuous joint reference (bounded jerk, SI units).

    Goals may jump at 50 Hz; reference position/velocity/acceleration persist
    across updates and are integrated at the physics timestep. Limits apply to
    the reference, not a guarantee on the position actuator's actual response.
    """
    def __init__(self, position, vmax, amax, scale=.8, lower=None, upper=None):
        self.position = np.asarray(position, float).copy()
        self.goal = self.position.copy()
        self.velocity = np.zeros_like(self.position)
        self.acceleration = np.zeros_like(self.position)
        self.vmax = np.asarray(vmax, float) * scale
        self.amax = np.asarray(amax, float) * scale
        self.jmax = self.amax * 10.
        self.lower = np.full_like(self.position,-np.inf) if lower is None else np.asarray(lower,float)
        self.upper = np.full_like(self.position,np.inf) if upper is None else np.asarray(upper,float)

    def _stop_distance(self, velocity, acceleration):
        # Maximum braking: ramp acceleration to -amax, then hold until stopped.
        v=np.maximum(velocity,0.); a=acceleration; J=self.jmax; A=self.amax
        ramp=np.maximum((a+A)/J,0.)
        zero=(a+np.sqrt(np.maximum(a*a+2*J*v,0.)))/J
        t=np.minimum(ramp,zero)
        distance=v*t+.5*a*t*t-J*t*t*t/6
        remaining=np.maximum(v+a*t-.5*J*t*t,0.)
        return np.maximum(distance+remaining*remaining/(2*A),0.)

    def advance(self, dt):
        error = self.goal - self.position
        # Conservative stopping speed, then jerk-limited acceleration tracking.
        speed = np.minimum(self.vmax, np.sqrt(self.amax * np.abs(error)))
        desired_v = np.sign(error) * speed
        desired_a = np.clip((desired_v - self.velocity) / .08, -self.amax, self.amax)
        jerk = np.clip((desired_a-self.acceleration)/dt, -self.jmax, self.jmax)
        upper_distance=self.upper-self.position
        lower_distance=self.position-self.lower
        upper_stop=self._stop_distance(self.velocity,self.acceleration)
        lower_stop=self._stop_distance(-self.velocity,-self.acceleration)
        # Anticipate one physics step and avoid MuJoCo's hidden ctrl-range clamp.
        margin=np.abs(self.velocity)*dt + .5*self.amax*dt*dt + 1e-4
        near_upper=(self.velocity>0)&(upper_distance<=upper_stop+margin)
        near_lower=(self.velocity<0)&(lower_distance<=lower_stop+margin)
        jerk=np.where(near_upper,np.maximum(-self.jmax,(-self.amax-self.acceleration)/dt),jerk)
        jerk=np.where(near_lower,np.minimum(self.jmax,(self.amax-self.acceleration)/dt),jerk)
        self.position += self.velocity*dt + .5*self.acceleration*dt**2 + jerk*dt**3/6
        self.velocity += self.acceleration*dt + .5*jerk*dt**2
        self.acceleration += jerk*dt
        return self.position


class HumanoidEnv:
    def __init__(self, width=640, height=480, shadows=False, cam='front', lowpoly=True, setpoint_scale=.6):
        self.width, self.height, self.cam = int(width), int(height), cam
        self.model = mujoco.MjModel.from_xml_string(build_g1_xml(width, height, shadows, lowpoly))
        m = self.model
        m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
        self.data = mujoco.MjData(m)
        self.joint_names = [m.joint(i).name for i in range(m.njnt)]
        self.qadr = {n: int(m.joint(n).qposadr[0]) for n in self.joint_names}
        self.dadr = {n: int(m.joint(n).dofadr[0]) for n in self.joint_names}
        self.act = {m.actuator(i).name: i for i in range(m.nu)}
        # Official effort limits -> actuator force range.
        for n in self.joint_names:
            e = URDF_EFFORT.get(_effort_key(n))
            if e is not None and n in self.act:
                a = self.act[n]
                m.actuator_forcerange[a] = (-e, e); m.actuator_forcelimited[a] = 1
                m.jnt_actfrcrange[m.joint(n).id] = (-e, e)
        self.groups = {
            'left_arm': [f'left_{j}_joint' for j in ARM], 'right_arm': [f'right_{j}_joint' for j in ARM],
            'waist': [f'{j}_joint' for j in WAIST],
            'left_hand': [f'left_hand_{j}_joint' for j in HAND], 'right_hand': [f'right_hand_{j}_joint' for j in HAND],
        }
        self.mocap = {n: int(m.body_mocapid[m.body(n).id]) for n in ('left_wrist_target', 'right_wrist_target', 'left_elbow_target', 'right_elbow_target')}
        self._renderer = None
        self._scene_opt = mujoco.MjvOption()
        self.setpoint_scale = None if setpoint_scale is None else .6
        self.setpoint = None
        self.collision_avoidance = False
        self.collision_model = None
        self.collision_monitor = None
        self.collision_reference_monitor = None
        self.collision_status = {}
        self.collision_plan = None
        self.reset()
        # Mode startup, before the first JPEG/servo: allocate all three MjData.
        # Public OFF state remains None and OFF physics/control is untouched.
        from .humanoid_collision import CapsuleModel,CollisionPathMonitor,MESH_RADII
        self._collision_resources=(CapsuleModel(self.model,MESH_RADII),
            CollisionPathMonitor(self.model,radii=MESH_RADII),CollisionPathMonitor(self.model,radii=MESH_RADII))
        for resource in self._collision_resources:
            geometry=resource.geometry if hasattr(resource,'geometry') else resource
            geometry.forward(self.data.qpos);geometry.distances(True,.12)
        import pickle
        self._collision_payload=pickle.dumps((self.model,MESH_RADII,self.data.qpos.copy()),protocol=5)


    def rest_q(self):
        q = {}
        for side, s in (('left', 1), ('right', -1)):
            for j, v in REST.items():
                q[f'{side}_{j}_joint'] = v * (s if j in ('shoulder_roll', 'shoulder_yaw', 'wrist_roll', 'wrist_yaw') else 1)
        return q

    def reset(self):
        mujoco.mj_resetData(self.model, self.data)
        for n, v in self.rest_q().items():
            self.data.qpos[self.qadr[n]] = v
        self.data.ctrl[:] = 0
        for n in self.joint_names:
            if n in self.act:
                self.data.ctrl[self.act[n]] = self.data.qpos[self.qadr[n]]
        mujoco.mj_forward(self.model, self.data)
        vmax = np.zeros(self.model.nu); amax = vmax.copy()
        for name, aid in self.act.items():
            kind = 'hand' if '_hand_' in name else 'waist' if name.startswith('waist') else 'wrist' if 'wrist' in name else 'arm'
            vmax[aid] = TELEOP_VEL[kind]; amax[aid] = TELEOP_ACC[kind]
        self._reference_vmax, self._reference_amax = vmax, amax
        self._fast_goal = self.data.ctrl.copy()
        self.safety_brake = self.setpoint_scale is not None
        self._brake_transition = None
        self._reference_offset = np.zeros(self.model.nu)
        self.brake_catchup_s = None
        self.setpoint = None if not self.safety_brake else JointSetpoint(self.data.ctrl, vmax, amax, .6, self.model.actuator_ctrlrange[:,0], self.model.actuator_ctrlrange[:,1])
        if getattr(self,'collision_avoidance',False):
            self.collision_avoidance=False
            self.set_collision_avoidance(True)

    def set_collision_avoidance(self,enabled):
        enabled=bool(enabled)
        if enabled==self.collision_avoidance:
            if enabled:self.refresh_collision_planner()
            return
        previous=getattr(self,'collision_planner',None)
        if previous is not None:previous.close()
        self.collision_planner=None
        self.collision_avoidance=enabled
        if enabled:
            from .humanoid_collision import CapsuleModel,CollisionPathMonitor,MESH_RADII,AsyncWaypointPlanner
            self.collision_model,self.collision_monitor,self.collision_reference_monitor=self._collision_resources
            for monitor in (self.collision_monitor,self.collision_reference_monitor):
                monitor.anchor=None;monitor.last=None;monitor.variation[:]=0.;monitor.gaps=None
                monitor.min_actual=float('inf');monitor.uncertified=0;monitor.penetrating=0;monitor.exact_checks=0
                monitor.geometry.previous_normals.clear()
            self.collision_model.previous_normals.clear()
            self.collision_planner=AsyncWaypointPlanner(self.model,MESH_RADII,initial_q=self.data.qpos,serialized_model=self._collision_payload)
        self.collision_braking=False
        self._collision_stop_goal=None
        self.collision_resume_goal=None;self.collision_released_at=-1e6;self.collision_constraints=[]
        self.collision_plan=None;self._collision_prev_reference_a=None;self._collision_prev_update_t=None;self._collision_guard_counts={'margin':0,'path':0,'jerk':0,'lag':0}
        self.collision_status={'enabled':enabled,'experimental':True,'physical_stop_certified':False,'collision_state':'clear','planner_ready':False,'planner_prepare_ms':None}

    def refresh_collision_planner(self):
        if self.collision_avoidance and self.collision_planner is not None:
            self.collision_status.update(self.collision_planner.diagnostics())

    def request_collision_brake(self,reason):
        """Latch a jerk-limited stop goal without resetting reference p/v/a."""
        if not self.collision_avoidance or self.collision_braking:return
        if self.setpoint is None:self.set_safety_brake(True)
        self.collision_braking=True
        self.collision_status['collision_state']='holding'
        self._collision_stop_goal=self.setpoint.position.copy()
        self.setpoint.goal[:]=self._collision_stop_goal
        self.collision_status['brake']={'reason':reason,'sim_time':float(self.data.time),'measured_certified':False}

    def update_collision_brake(self):
        """Predict closing motion and gate release on a validated proxy route.

        The finite-sample route and empirical stopping model are not physical
        safety certification. They only govern the opt-in capsule experiment.
        """
        if not self.collision_avoidance:return
        g=self.collision_model;g.forward(self.data.qpos)
        aids=np.array([self.act[name] for name in g.names])
        actual_v=self.data.qvel[g.dofs]
        reference_v=actual_v if self.setpoint is None else self.setpoint.velocity[aids]
        reference_q=self.data.ctrl[aids] if self.setpoint is None else self.setpoint.position[aids]+self._reference_offset[aids]
        can_release=True;risk=None;nearest=1.;improving=False
        rows=g.distances(True,.12);self.collision_constraints=rows
        critical_gap=min(row['distance'] for row in rows)
        resume_goal=getattr(self,'collision_resume_goal',None)
        plan=getattr(self,'collision_plan',None) or {}
        path_min=float(plan.get('path_min',-1.))
        if resume_goal is None or not plan.get('accepted') or path_min<.003:can_release=False
        reference_a=np.zeros_like(reference_v) if self.setpoint is None else self.setpoint.acceleration[aids]
        now=float(self.data.time)
        previous_a=getattr(self,'_collision_prev_reference_a',None);previous_t=getattr(self,'_collision_prev_update_t',None)
        if previous_a is None or previous_t is None or now<=previous_t:reference_j=np.zeros_like(reference_a)
        else:reference_j=(reference_a-previous_a)/max(now-previous_t,1e-6)
        self._collision_prev_reference_a=reference_a.copy();self._collision_prev_update_t=now
        for row in rows:
            if 'gradient' not in row:continue
            normal_velocity=-float(row['gradient']@actual_v)
            closing=max(0.,normal_velocity)
            reference_closing=max(0.,-float(row['gradient']@reference_v))
            accel_closing=max(0.,-float(row['gradient']@reference_a))
            jerk_closing=max(0.,-float(row['gradient']@reference_j))
            lag=max(0.,-float(row['gradient']@(reference_q-self.data.qpos[g.qadr])))
            horizon=.06
            predicted=max(closing,reference_closing)+accel_closing*horizon+.5*jerk_closing*horizon*horizon
            required=.002+predicted*horizon+predicted**2/(2*.25)+min(lag,.01)
            guard_required=.008
            route_floor=min(row['distance'],path_min)
            if required>.012:self._collision_guard_counts['margin']+=1
            if accel_closing>0 or jerk_closing>0:self._collision_guard_counts['jerk']+=1
            if lag>1e-4:self._collision_guard_counts['lag']+=1
            nearest=min(nearest,row['distance'])
            if resume_goal is not None and row['distance']<=critical_gap+.002:
                directional=float(row['gradient']@(resume_goal[g.qadr]-self.data.qpos[g.qadr]))
                if directional > 1e-4:improving=True
                elif route_floor<guard_required:can_release=False
            if row['distance']<=.002 or (normal_velocity>1e-4 and route_floor<guard_required):can_release=False
            # Match the release noise threshold, preventing immediate re-latch
            # on settled micron-scale PD closing motion (guard distance unchanged).
            if closing>1e-4 and route_floor<guard_required:
                self._collision_guard_counts['path']+=1
                risk={'pair':row['pair'],'distance':row['distance'],'closing_speed':closing,'reference_closing_speed':reference_closing,'reference_accel_closing':accel_closing,'required_margin':required,'guard_required':guard_required,'tracking_normal':lag,'planned_path_min':path_min,'margin_method':'planned-route-plus-reference-accel-jerk-tracking-lag','effective_deceleration':.25,'latency_s':horizon}
                break
        if self.collision_braking:
            # Do not cancel an in-flight stop. Re-arm only after settling and
            # separating/stationary clearance > static(3mm)+hysteresis(2mm).
            settled=float(np.max(np.abs(actual_v)))<.02
            held_s=float(self.data.time)-float((self.collision_status.get('brake') or {}).get('sim_time',-1e6))
            if held_s>=.08 and can_release and settled and (improving or path_min>=required):
                self.collision_braking=False;self._collision_stop_goal=None
                self.collision_released_at=float(self.data.time)
                self.collision_status['collision_state']='clear'
                self.collision_status['release']={'sim_time':float(self.data.time),'clearance':nearest,'hysteresis':.002,'goal_direction':'increasing-or-validated-route','planned_path_min':path_min}
            return
        self.collision_status['guard_counts']=dict(self._collision_guard_counts)
        if risk is not None:self.request_collision_brake(risk)

    def set_safety_brake(self, enabled):
        """Keep physical q/qd and ctrl continuous. OFF catch-up is rate bounded.

        ON seeds measured q/qd with a constant reference-coordinate offset.
        Physical q/qd are never reset or clipped. Acceleration validation pending.
        """
        enabled=bool(enabled)
        if enabled==self.safety_brake:return
        old_control=self.data.ctrl.copy();self.safety_brake=enabled
        self.setpoint_scale=.6 if enabled else None
        if enabled:
            position=old_control.copy();velocity=np.zeros_like(position)
            for name,aid in self.act.items():
                position[aid]=self.data.qpos[self.qadr[name]]
                velocity[aid]=self.data.qvel[self.dadr[name]]
            offset=old_control-position;self._reference_offset=offset
            self.setpoint=JointSetpoint(position,self._reference_vmax,self._reference_amax,.6,
                self.model.actuator_ctrlrange[:,0]-offset,self.model.actuator_ctrlrange[:,1]-offset)
            self.setpoint.velocity[:]=velocity;self.setpoint.goal[:]=self._fast_goal-offset
            self._brake_transition=None
        else:
            if self.setpoint is not None:
                self.setpoint.vmax[:]=self._reference_vmax*.75
                self.setpoint.amax[:]=self._reference_amax*.6
                self.setpoint.jmax[:]=self.setpoint.amax*10.
            self._brake_transition=(self.data.time,False,self._reference_offset.copy())
        self.brake_catchup_s=None

    def set_targets(self, qdict):
        lim = self.model.actuator_ctrlrange
        for n, v in qdict.items():
            a = self.act[n]
            target = float(np.clip(v, lim[a, 0], lim[a, 1]))
            self._fast_goal[a] = target
            if self.setpoint is None: self.data.ctrl[a] = target
            elif not getattr(self,'collision_braking',False): self.setpoint.goal[a] = target-self._reference_offset[a]

    def step(self, n=1):
        d = self.data
        for _ in range(n):
            if self.setpoint is not None:
                reference=self.setpoint.advance(self.model.opt.timestep)+self._reference_offset
                d.ctrl[:]=reference
                if self._brake_transition is not None:
                    t0,_,_=self._brake_transition
                    if np.max(np.abs(reference-self._fast_goal))<5e-5 and np.max(np.abs(self.setpoint.velocity))<.01:
                        self.brake_catchup_s=float(d.time+self.model.opt.timestep-t0)
                        self._brake_transition=None;self.setpoint=None
                        self._reference_offset[:]=0.
            if self.collision_avoidance:
                qref=d.qpos.copy()
                for name in self.collision_model.names:qref[self.qadr[name]]=d.ctrl[self.act[name]]
                self.collision_status['reference']=self.collision_reference_monitor.inspect(qref)
            d.qfrc_applied[:] = d.qfrc_bias
            mujoco.mj_step(self.model, d)
            if self.collision_avoidance:self.collision_status['actual']=self.collision_monitor.inspect(d.qpos)

    def q(self, names):
        return np.array([self.data.qpos[self.qadr[n]] for n in names])

    def qd(self, names):
        return np.array([self.data.qvel[self.dadr[n]] for n in names])

    def tau(self, names):
        return np.array([self.data.actuator_force[self.act[n]] for n in names])

    def set_mocap(self, name, pos):
        self.data.mocap_pos[self.mocap[name]] = pos if pos is not None else (0, 0, -1)

    def camera_K(self, cam=None):
        cid = self.model.camera(cam or self.cam).id
        f = .5 * self.height / np.tan(np.deg2rad(self.model.cam_fovy[cid]) * .5)
        return np.array([[f, 0, (self.width - 1) / 2], [0, f, (self.height - 1) / 2], [0, 0, 1]])

    def T_world_cam(self, cam=None):
        cid = self.model.camera(cam or self.cam).id
        T = np.eye(4); T[:3, :3] = self.data.cam_xmat[cid].reshape(3, 3) @ np.diag([1., -1., -1.]); T[:3, 3] = self.data.cam_xpos[cid]
        return T

    def render(self, cam=None):
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=self.height, width=self.width)
        self._renderer.update_scene(self.data, camera=cam or self.cam, scene_option=self._scene_opt)
        return self._renderer.render()

    def close(self):
        planner=getattr(self,'collision_planner',None)
        if planner is not None:planner.close();self.collision_planner=None
        if self._renderer is not None:
            self._renderer.close(); self._renderer = None
