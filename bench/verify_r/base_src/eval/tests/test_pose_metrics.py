import math, unittest
import numpy as np
from eval.pose_metrics import add_mm,adds_mm,auc,rotation_error_deg,translation_error_mm
class PoseMetricsTest(unittest.TestCase):
 def setUp(self): self.v=np.array([[0,0,0],[.1,0,0],[0,.2,0],[0,0,.3]],float); self.I=np.eye(4)
 def test_identity(self):
  self.assertAlmostEqual(translation_error_mm(self.I,self.I),0); self.assertAlmostEqual(rotation_error_deg(self.I,self.I),0); self.assertAlmostEqual(add_mm(self.I,self.I,self.v),0); self.assertAlmostEqual(adds_mm(self.I,self.I,self.v),0)
 def test_translation(self):
  p=self.I.copy(); p[:3,3]=[.01,-.02,.02]; self.assertAlmostEqual(translation_error_mm(p,self.I),30,places=8); self.assertAlmostEqual(add_mm(p,self.I,self.v),30,places=8)
 def test_rotation_geodesic(self):
  p=self.I.copy(); a=math.pi/2; p[:3,:3]=[[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]]; self.assertAlmostEqual(rotation_error_deg(p,self.I),90,places=8)
 def test_adds_symmetry(self):
  v=np.array([[-.1,0,0],[.1,0,0]],float); p=self.I.copy(); p[:3,:3]=np.diag([-1,-1,1]); self.assertGreater(add_mm(p,self.I,v),100); self.assertAlmostEqual(adds_mm(p,self.I,v),0,places=8)
 def test_auc(self): self.assertAlmostEqual(auc([0,50,100,200]),.375)
if __name__=="__main__": unittest.main()
