import json
from pathlib import Path
import numpy as np,mujoco
from PIL import Image,ImageDraw
from sim.cell_scene_eval import open_evaluation_scene
scene=open_evaluation_scene(1000,640,480);w=scene._world;results={}
try:
 for sample in (4,0):
  if w.renderer is not None:w.renderer.close();w.renderer=None
  w.model.vis.quality.offsamples=sample
  rgb=scene.rgb();w.renderer.enable_segmentation_rendering();opt=mujoco.MjvOption();opt.geomgroup[3]=0;w.renderer.update_scene(w.data,camera='front',scene_option=opt);seg=w.renderer.render().copy();w.renderer.disable_segmentation_rendering()
  overlay=Image.fromarray(rgb);draw=ImageDraw.Draw(overlay);rows=[]
  for item in scene.ground_truth():
   bid=w.model.body(item['instance_id']).id;ids=np.where(w.model.geom_bodyid==bid)[0];mask=np.isin(seg[:,:,0],ids)&(seg[:,:,1]==int(mujoco.mjtObj.mjOBJ_GEOM));y,x=np.where(mask)
   if len(x):
    box=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)];rows.append(dict(instance_id=item['instance_id'],class_id=item['class_id'],box=box,pixels=len(x)));draw.rectangle(box,outline='lime',width=2);draw.text((box[0],box[1]),item['instance_id'],fill='lime')
  results[str(sample)]=rows;overlay.save('bench/g1/gt_msaa_'+str(sample)+'.png')
finally:scene.close()
Path('bench/g1/gt_msaa_check.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
