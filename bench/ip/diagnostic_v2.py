import sys,json,time,numpy as np,cv2
sys.path.insert(0,'/home/user/work/robot_percept')
from web.perception_stub import PerceptionBackend
R='/home/user/work/robot_percept'; F=R+'/bench/verify_p/frames'
names=('mustard','cup_d70_h60mm','box_fillet_50x30x20mm')
meshes=[R+'/downloads/demo_data/mustard0/mesh/textured_simple.obj']+[f'{R}/cad_uploads/converted/{n}/{n}.obj' for n in names[1:]]
def main():
 b=PerceptionBackend('fp'); rows=[]; z=np.load(F+'/s00.npz'); clicks=json.load(open(F+'/clicks.json'))
 for idx,gtmode in [(0,False),(0,False),(0,True),(1,False),(2,False),(2,True),(0,False)]:
  c=next(c for c in clicks if c['scene']==0 and c['obj']==names[idx] and c['kind']=='cap') if idx==0 else next(c for c in clicks if c['scene']==0 and c['obj']==names[idx])
  t=time.perf_counter(); s=b.call('segment',rgb=z['rgb'],depth=z['depth'],K=z['K'],click=(c['x'],c['y']))
  gt=z['seg']==idx; n,l,st,_=cv2.connectedComponentsWithStats(gt.astype(np.uint8)); gt=l==(1+np.argmax(st[1:,4]))
  m=gt if gtmode else s['mask']; q=b.call('register',name=names[idx],mesh=meshes[idx],rgb=z['rgb'],depth=z['depth'],mask=m,K=z['K']); T=np.array(q['pose']); G=z['T_'+names[idx]]
  row=dict(obj=names[idx],gt=gtmode,terr=float(np.linalg.norm(T[:3,3]-G[:3,3])*1000),delta=((T[:3,3]-G[:3,3])*1000).tolist(),pose=T.tolist(),latency=time.perf_counter()-t,reg=q['ms'],iou=float((m&gt).sum()/(m|gt).sum()))
  rows.append(row); print(row,flush=True)
  json.dump(rows,open(R+'/bench/ip/diagnostic_v2.json','w'),indent=2)
 b.close()
if __name__=='__main__': main()