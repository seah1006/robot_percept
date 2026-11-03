import sys,json,numpy as np,trimesh,time
sys.path.insert(0,'/home/user/work/robot_percept')
from perception.depth_refine import refine_pose
R='/home/user/work/robot_percept'; z=np.load(R+'/bench/verify_p/frames/s00.npz')
for row in json.load(open(R+'/bench/ip/diagnostic_v2.json')):
 n=row['obj']
 if n=='mustard':continue
 mesh=trimesh.load(f'{R}/cad_uploads/converted/{n}/{n}.obj'); T=np.array(row['pose']); idx=1 if n.startswith('cup') else 2
 start=time.perf_counter(); Q=refine_pose(mesh,T,z['depth'],z['seg']==idx,z['K']); G=z['T_'+n]
 print(n,row['gt'],'before',row['terr'],'after',np.linalg.norm(Q[:3,3]-G[:3,3])*1000,'sec',time.perf_counter()-start,flush=True)