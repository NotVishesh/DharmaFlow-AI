"""Landmark-aligned crops and local mouth compositing for moving faces."""
import math
import cv2
import numpy as np


def crop_transform(points):
    """Make eyes horizontal and place nose/chin consistently with MuseTalk crops."""
    left,right=points[33],points[263]
    angle=math.degrees(math.atan2(*(right-left)[::-1]))
    rotation=cv2.getRotationMatrix2D(tuple(points[4].astype(float)),angle,1.0)
    rotated=cv2.transform(points[None].astype(np.float32),rotation)[0]
    x1=min(rotated[234,0],rotated[454,0]);x2=max(rotated[234,0],rotated[454,0])
    nose=rotated[4,1];chin=rotated[152,1]
    lower=chin-nose
    if x2-x1<25 or lower<15: raise ValueError('Face is too small or too turned for reliable lip-sync')
    y1=nose-lower;y2=chin+lower*.04
    margin=(x2-x1)*.04;x1-=margin;x2+=margin
    scale=np.array([[256/(x2-x1),0,-x1*256/(x2-x1)],[0,256/(y2-y1),-y1*256/(y2-y1)],[0,0,1]],np.float32)
    matrix=(scale @ np.vstack([rotation,[0,0,1]]))[:2].astype(np.float32)
    aligned=cv2.transform(points[None].astype(np.float32),matrix)[0]
    return matrix,aligned


def blend_mouth(frame,generated,matrix,points):
    crop=cv2.warpAffine(frame,matrix,(256,256),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101)
    center=(points[13]+points[14])/2
    width=np.linalg.norm(points[61]-points[291])
    # Mouth-sized patch, not a replacement of the entire lower face.
    axes=(int(max(34,width*.85)),int(max(30,width*.42)))
    mask=np.zeros((256,256),np.float32)
    cv2.ellipse(mask,tuple(np.rint(center).astype(int)),axes,0,0,360,1,-1)
    mask=cv2.GaussianBlur(mask,(19,19),0)
    # Match nearby skin tone to reduce seams; retain actual generated articulation.
    ring=(cv2.dilate(mask,np.ones((19,19),np.uint8))>.1)&(mask<.05)
    delta=np.zeros(3) if not ring.any() else np.clip(crop[ring].mean(0)-generated[ring].mean(0),-25,25)
    corrected=np.clip(generated.astype(np.float32)+delta,0,255)
    inverse=cv2.invertAffineTransform(matrix)
    size=(frame.shape[1],frame.shape[0])
    patch=cv2.warpAffine(corrected,inverse,size,flags=cv2.INTER_CUBIC)
    alpha=cv2.warpAffine(mask,inverse,size,flags=cv2.INTER_LINEAR)[...,None]
    result=np.clip(frame.astype(np.float32)*(1-alpha)+patch*alpha,0,255).astype(np.uint8)
    return result,mask


class FaceAligner:
    def __init__(self,model_path):
        import mediapipe as mp
        self.mp=mp
        options=mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=2,
            min_face_detection_confidence=.5,min_face_presence_confidence=.5,min_tracking_confidence=.5)
        self.model=mp.tasks.vision.FaceLandmarker.create_from_options(options)
    def align(self,frame,index,fps=30):
        image=self.mp.Image(image_format=self.mp.ImageFormat.SRGB,data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
        detected=self.model.detect_for_video(image,round(index*1000/fps))
        if len(detected.face_landmarks)!=1:
            raise ValueError(f'Need one tracked face; found {len(detected.face_landmarks)} in frame {index}')
        points=np.array([(p.x*frame.shape[1],p.y*frame.shape[0]) for p in detected.face_landmarks[0]],np.float32)
        matrix,aligned=crop_transform(points)
        crop=cv2.warpAffine(frame,matrix,(256,256),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101)
        return crop,matrix,aligned
    def close(self): self.model.close()
