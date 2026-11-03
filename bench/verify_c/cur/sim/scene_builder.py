"""MJCF construction without recentering source geometry or object body frames."""
import re
import xml.etree.ElementTree as ET
import numpy as np
from .objects import ROOT
TABLE_TOP=.30
HOME=np.array([0,0,0,-1.57079,0,1.57079,-.7853])
def look_at(pos,target):
    f=np.asarray(target)-np.asarray(pos); f/=np.linalg.norm(f)
    x=np.cross(f,[0.,0.,1.]); x/=np.linalg.norm(x)
    return ' '.join(map(str,np.r_[x,np.cross(-f,x)]))
def build_scene(specs,width=640,height=480):
    men=ROOT/'assets/mujoco_menagerie/franka_emika_panda'
    src=(men/'panda.xml').read_text().replace('meshdir="assets"',f'meshdir="{men / "assets"}"')
    src=re.sub(r'\s*<keyframe>.*?</keyframe>','',src,flags=re.S)
    root=ET.fromstring(src)
    hand=root.find('.//body[@name="hand"]')
    ET.SubElement(hand,'camera',name='wrist',pos='.06 0 .02',quat='0 1 0 0',fovy='70')
    ET.SubElement(hand,'site',name='tcp',pos='0 0 .1034',size='.003',rgba='0 0 0 0')
    ET.SubElement(root,'statistic',center='.4 0 .4',extent='1.2')
    vis=ET.SubElement(root,'visual')
    ET.SubElement(vis,'headlight',diffuse='.6 .6 .6',ambient='.3 .3 .3',specular='0 0 0')
    ET.SubElement(vis,'map',znear='.01',zfar='50')
    ET.SubElement(vis,'global',offwidth=str(max(1920,width)),offheight=str(max(1080,height)))
    asset=root.find('asset'); world=root.find('worldbody')
    ET.SubElement(asset,'material',name='table_mat',rgba='.55 .4 .25 1')
    ET.SubElement(world,'geom',name='floor',type='plane',size='0 0 .05',rgba='.2 .3 .4 1')
    table=ET.SubElement(world,'body',name='table',pos='.55 0 .15')
    ET.SubElement(table,'geom',name='table_top',type='box',size='.25 .4 .15',material='table_mat')
    for name in ('front','rgbd'):
        ET.SubElement(world,'camera',name=name,pos='1.35 0 .95',xyaxes=look_at([1.35,0.,.95],[.55,0.,.30]),fovy='58')
    for i,s in enumerate(specs):
        p=f'object_{i}'
        ET.SubElement(asset,'mesh',name=p+'_visual',file=s.visual_obj)
        mat={'name':p+'_mat','rgba':' '.join(map(str,s.rgba))}
        if s.texture:
            ET.SubElement(asset,'texture',name=p+'_tex',type='2d',file=s.texture)
            mat.update(texture=p+'_tex',rgba='1 1 1 1')
        ET.SubElement(asset,'material',**mat)
        body=ET.SubElement(world,'body',name=s.name,pos=f'.55 0 {TABLE_TOP-s.bounds[0,2]+.005}')
        ET.SubElement(body,'freejoint',name=s.name+'_free')
        # MuJoCo compensates internal principal-axis mesh alignment on each geom.
        # GT is body xpos/xmat, not the internally transformed mesh/geom frame.
        ET.SubElement(body,'geom',name=p+'_visual_geom',type='mesh',mesh=p+'_visual',material=p+'_mat',contype='0',conaffinity='0',group='2',mass='0')
        for j,path in enumerate(s.collision_objs):
            meshname=f'{p}_collision_{j}'
            ET.SubElement(asset,'mesh',name=meshname,file=path)
            ET.SubElement(body,'geom',name=meshname+'_geom',type='mesh',mesh=meshname,group='3',mass=str(s.mass/len(s.collision_objs)),friction='.8 .01 .001',solref='.004 1')
    # 집기 보조(grasp assist): 양 손가락이 물체에 닿았을 때만 켜지는 weld (기본 비활성)
    eq=root.find('equality')
    if eq is None: eq=ET.SubElement(root,'equality')
    for s in specs:
        ET.SubElement(eq,'weld',name='grasp_'+s.name,body1='hand',body2=s.name,active='false',solref='.01 1')
    return ET.tostring(root,encoding='unicode')
