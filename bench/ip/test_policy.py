"""CPU-only synthetic checks for GT-free selector edge behavior."""
import numpy as np
from perception.sam_runner import select_candidate

def test_zero_depth_click_uses_neighbor():
    masks=np.zeros((3,40,40),bool)
    masks[0,17:23,17:23]=True
    masks[1,12:28,12:28]=True
    masks[2,:,:]=True
    scores=np.array([.95,.13,.07])
    depth=np.full((40,40),2.,dtype=np.float32)
    depth[12:28,12:28]=1.
    depth[20,20]=0.
    assert select_candidate(masks,scores,(20,20),depth)==1

def test_invalid_depth_without_neighbors_falls_back():
    masks=np.ones((3,30,30),bool)
    scores=np.array([.9,.2,.1]); depth=np.zeros((30,30),dtype=np.float32)
    assert select_candidate(masks,scores,(15,15),depth)==0
