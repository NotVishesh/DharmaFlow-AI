import cv2
import numpy as np
from backend.services.face_geometry import crop_transform,blend_mouth

def landmarks():
 p=np.tile([150.,170.],(478,1)).astype(np.float32)
 for i,xy in {33:(100,100),263:(200,100),234:(80,150),454:(220,150),4:(150,160),152:(150,240),61:(125,205),291:(175,205),13:(150,202),14:(150,208)}.items():p[i]=xy
 return p

def test_rotated_face_has_horizontal_eyes_and_consistent_mouth():
 p=landmarks();base,aligned=crop_transform(p)
 rotate=cv2.getRotationMatrix2D((150,160),19,1)
 turned=cv2.transform(p[None],rotate)[0]
 _,aligned_rotated=crop_transform(turned)
 assert abs(aligned_rotated[33,1]-aligned_rotated[263,1])<1e-4
 assert np.allclose(aligned[[13,14]],aligned_rotated[[13,14]],atol=.001)

def test_mouth_blend_preserves_eyes_and_background():
 frame=np.full((320,320,3),70,np.uint8)
 matrix,aligned=crop_transform(landmarks())
 generated=np.full((256,256,3),160,np.uint8)
 output,mask=blend_mouth(frame,generated,matrix,aligned)
 assert np.array_equal(output[:110],frame[:110])
 assert np.array_equal(output[:,:60],frame[:,:60])
 assert output[205,150].mean()>100
 assert mask.max()<=1.00001
