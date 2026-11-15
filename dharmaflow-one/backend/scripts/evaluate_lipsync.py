"""Independent SyncNet offset diagnostic; not a quality guarantee for stylized faces."""
import argparse,json,sys,subprocess,math
from pathlib import Path
import cv2,numpy as np,torch
from scipy.io import wavfile
from scipy.ndimage import median_filter
import python_speech_features
from backend.config import settings
from backend.services.face_geometry import FaceAligner

def main(video):
 torch.set_num_threads(2)
 root=Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/'vendor/syncnet_python'))
 from SyncNetModel import S
 from SyncNetInstance import calc_pdist
 folder=settings.TEMP_DIR/(Path(video).stem+'-syncnet');folder.mkdir(exist_ok=True)
 clip=folder/'input.mp4';audio=folder/'audio.wav'
 subprocess.run(['ffmpeg','-v','error','-y','-i',video,'-vf','fps=25','-an',str(clip)],check=True)
 subprocess.run(['ffmpeg','-v','error','-y','-i',video,'-vn','-ac','1','-ar','16000',str(audio)],check=True)
 cap=cv2.VideoCapture(str(clip));frames=[];boxes=[]
 aligner=FaceAligner(settings.MODELS_DIR/'lipsync/face_landmarker.task')
 i=0
 try:
  while True:
   ok,frame=cap.read()
   if not ok:break
   image=aligner.mp.Image(image_format=aligner.mp.ImageFormat.SRGB,data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
   r=aligner.model.detect_for_video(image,i*40)
   if len(r.face_landmarks)!=1:raise ValueError('SyncNet diagnostic needs a tracked face in every frame')
   p=np.array([(x.x*frame.shape[1],x.y*frame.shape[0]) for x in r.face_landmarks[0]])
   x1,y1=p.min(0);x2,y2=p.max(0)
   boxes.append([(x1+x2)/2,(y1+y2)/2,max(x2-x1,y2-y1)/2]);frames.append(frame);i+=1
 finally: cap.release();aligner.close()
 boxes=median_filter(np.array(boxes),size=(13,1))
 crops=[]
 for frame,(x,y,s) in zip(frames,boxes):
  pad=int(s*2);padded=cv2.copyMakeBorder(frame,pad,pad,pad,pad,cv2.BORDER_CONSTANT,value=(110,110,110));x+=pad;y+=pad
  crop=padded[int(y-s):int(y+1.8*s),int(x-1.4*s):int(x+1.4*s)]
  crops.append(cv2.resize(crop,(224,224)))
 rate,wave=wavfile.read(str(audio));mfcc=python_speech_features.mfcc(wave,rate).T
 im=torch.from_numpy(np.stack(crops).transpose(3,0,1,2)[None]).float()
 au=torch.from_numpy(mfcc[None,None]).float()
 model=S().eval();model.load_state_dict(torch.load(settings.MODELS_DIR/'lipsync/syncnet_v2.model',map_location='cpu',weights_only=True))
 length=min(len(crops),len(wave)//640)-5
 if length<10: raise ValueError("At least 0.6 seconds of speech/video is required for SyncNet evaluation")
 vf=[];af=[]
 with torch.inference_mode():
  for i in range(0,length,4):
   ids=range(i,min(i+4,length))
   vf.append(model.forward_lip(torch.cat([im[:,:,j:j+5] for j in ids])))
   af.append(model.forward_aud(torch.cat([au[:,:,:,j*4:j*4+20] for j in ids])))
 distances=torch.mean(torch.stack(calc_pdist(torch.cat(vf),torch.cat(af),vshift=10),1),1)
 value,index=distances.min(0);confidence=(distances.median()-value).item();offset=10-index.item()
 report={'estimator':'SyncNet v2','offset_frames_25fps':offset,'estimated_offset_ms':offset*40,
  'confidence':confidence,'minimum_distance':value.item(),'scope':'Diagnostic estimate; stylized face and short speech may be out of distribution. Human review required.'}
 Path(video).with_suffix('.syncnet.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('video');args=parser.parse_args();main(args.video)
