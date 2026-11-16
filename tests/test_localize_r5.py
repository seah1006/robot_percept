import dataclasses
import numpy as np
import pytest
from perception.interfaces import CameraModel,FrameMeta,Detection
from perception.localize import Localizer
from perception.preview_transform import *

def fixture():
    T=np.diag([1.,-1.,-1.,1.]); T[:3,3]=[0,0,1]
    c=CameraModel('c',((800,0,640),(0,800,360),(0,0,1)),(),tuple(map(tuple,T)),(0,0,1,0),(1280,720),(0,0,1280,720),(77,48),'synthetic')
    f=FrameMeta('f',1,'synthetic',None,1.,False,'c',1280,720,False)
    d=Detection('d','q','can',1.,(600,300,680,400),f)
    return c,d

@pytest.mark.parametrize('point',[(0,0),(639,359),(123.7,54.9)])
def test_preview_roundtrip(point):
    assert np.allclose(original_point_to_preview(preview_point_to_original(point)),point)
@pytest.mark.parametrize('box',[(0,0,640,360),(10.2,30.1,400,300)])
def test_box_ui(box):
    original=preview_box_to_original(box)
    assert np.allclose(original_box_to_preview(original),box)
    ui=tuple(v*1.5+(20 if i%2==0 else 30) for i,v in enumerate(box))
    assert np.allclose(ui_box_to_original(ui,1.5,(20,30)),original)
def test_center_vs_edges():
    assert preview_point_to_original((0,0))==(1278.5,.5)
    assert preview_box_to_original((0,0,1,1))==(1278,0,1280,2)
    K=np.array([[800.,0,640],[0,800,360],[0,0,1]])
    assert scaled_intrinsics(K)[0,2]==319.75

def test_bottom_top_height():
    c,d=fixture(); loc=Localizer(c)
    bottom=loc.localize(d,anchor=(720,360))
    assert np.allclose(bottom.xyz_m,[.1,0,0]); assert bottom.yaw_rad is None
    top=loc.localize(d,anchor=(720,360),anchor_kind='top_center')
    off=loc.localize(d,anchor=(720,360),anchor_kind='top_center',height_correction=False)
    assert np.allclose(top.xyz_m,[.093,0,0]); assert np.allclose(off.xyz_m,[.1,0,0])
    assert top.gt_assist is False
@pytest.mark.parametrize('change,code',[({'calibration_id':'bad'},'CALIBRATION_MISMATCH'),({'width':1000},'CALIBRATION_MISMATCH'),({'mirrored':True},'INVALID_INPUT'),({'overlay_present':True},'INVALID_INPUT')])
def test_reject(change,code):
    c,d=fixture(); d=dataclasses.replace(d,frame=dataclasses.replace(d.frame,**change))
    assert Localizer(c).localize(d).error==code

def test_transform_and_unknown():
    c,d=fixture(); T=np.eye(4); T[:3,3]=[1,2,3]
    assert np.allclose(Localizer(c,T_base_world=T).localize(d,anchor=(640,360)).xyz_m,[1,2,3])
    assert Localizer(c).localize(dataclasses.replace(d,canonical_class='unknown')).error=='INVALID_INPUT'
    assert Localizer(c).localize(d,anchor_kind='top_center').error=='INVALID_INPUT'


def test_distance_gate():
    c,d=fixture()
    assert Localizer(c,max_range_m=.5).localize(d,anchor=(640,360)).error=='INVALID_INPUT'
    assert Localizer(c,min_incidence_deg=89).localize(d,anchor=(1000,360)).error=='INVALID_INPUT'

def test_bbox_midheight_prior():
    c,d=fixture(); loc=Localizer(c)
    on=loc.localize(d); off=loc.localize(d,height_correction=False)
    assert on.method=='table_plane_bbox_midheight'
    assert np.allclose(on.xyz_m,[-.000603125,.012665625,0])
    assert not np.allclose(on.xyz_m,off.xyz_m)
    assert 'bbox_midheight_approximation' in on.quality_flags
