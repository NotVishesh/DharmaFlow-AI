"""Small-batch MuseTalk worker: one visible face, bounded frame memory."""
import os
os.environ['OMP_NUM_THREADS']='1'
import json, sys, math
from pathlib import Path
import cv2
import numpy as np
import torch
from filelock import FileLock
from backend.config import settings


def face_box(frame, detector):
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    faces=detector.detectMultiScale(gray,1.1,5,minSize=(max(60,frame.shape[1]//10),)*2)
    if len(faces)!=1:
        raise ValueError(f'Lip-sync needs exactly one clear frontal face; detected {len(faces)}. Use a close-up or supply a face box.')
    x,y,w,h=map(int,faces[0])
    return [x,y,x+w,min(frame.shape[0],y+h+int(h*.03))]


def main(job):
    vendor=Path(job['vendor']);sys.path.insert(0,str(vendor))
    from musetalk.models.vae import VAE
    from musetalk.models.unet import UNet,PositionalEncoding
    from musetalk.utils.audio_processor import AudioProcessor
    from transformers import WhisperModel
    if not torch.cuda.is_available(): raise RuntimeError('MuseTalk requires a CUDA GPU in this integration')
    torch.set_num_threads(1);torch.manual_seed(42)
    device=torch.device('cuda');dtype=torch.float16
    root=Path(job['models']);fps=30;nframes=job['frames']
    print('Encoding speech features',flush=True)
    processor=AudioProcessor(str(root/'whisper'))
    whisper=WhisperModel.from_pretrained(str(root/'whisper'),torch_dtype=dtype,local_files_only=True).to(device).eval()
    features,length=processor.get_audio_feature(job['audio'])
    with torch.inference_mode():
        chunks=processor.get_whisper_chunk(features,device,dtype,whisper,length,fps=fps).cpu()
    del whisper,processor;torch.cuda.empty_cache()
    print('Loading MuseTalk 1.5 (batch size 1)',flush=True)
    vae=VAE(str(root/'vae'),use_float16=True)
    unet=UNet(str(root/'musetalk/musetalkV15/musetalk.json'),str(root/'musetalk/musetalkV15/unet.pth'),use_float16=True,device=device)
    unet.model.eval();vae.vae.eval()
    pe=PositionalEncoding().to(device=device,dtype=dtype)
    image=cv2.imread(job['source']) if job['portrait'] else None
    capture=None if image is not None else cv2.VideoCapture(job['source'])
    from backend.services.face_geometry import FaceAligner,blend_mouth
    aligner=FaceAligner(root/'face_landmarker.task')
    writer=None;previous_box=None;cached_latents=None
    changes=[];previous_mouth=None
    try:
        for i in range(nframes):
            if image is not None: frame=image.copy()
            else:
                ok,frame=capture.read()
                if not ok: raise ValueError('Source video ended before the speech; looping is disabled')
            if writer is None:
                height,width=frame.shape[:2]
                writer=cv2.VideoWriter(job['silent_output'],cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
                if not writer.isOpened(): raise RuntimeError('Cannot open lip-sync video writer')
            crop,matrix,aligned_points=aligner.align(frame,i,fps)
            original_points=cv2.transform(aligned_points[None],cv2.invertAffineTransform(matrix))[0]
            box=[int(original_points[:,0].min()),int(original_points[:,1].min()),int(original_points[:,0].max()),int(original_points[:,1].max())]
            with torch.inference_mode():
                if cached_latents is None or image is None:
                    # Use posterior means, avoiding fresh random face noise every frame.
                    masked=vae.preprocess_img(crop,half_mask=True).to(dtype)
                    reference=vae.preprocess_img(crop,half_mask=False).to(dtype)
                    latent=torch.cat([vae.vae.encode(masked).latent_dist.mean,vae.vae.encode(reference).latent_dist.mean],dim=1)*vae.scaling_factor
                    if image is not None: cached_latents=latent
                else: latent=cached_latents
                audio_index=max(0,min(i+job.get('audio_offset_frames',0),len(chunks)-1))
                audio=pe(chunks[audio_index:audio_index+1].to(device=device,dtype=dtype))
                predicted=unet.model(latent.to(dtype),torch.tensor([0],device=device),encoder_hidden_states=audio).sample
                generated=vae.decode_latents(predicted)[0]
            frame,mask=blend_mouth(frame,generated,matrix,aligned_points)
            mouth=generated[mask>.5].astype(np.float32)
            current=float(mouth.mean())
            if previous_mouth is not None: changes.append(abs(current-previous_mouth))
            previous_mouth=current
            writer.write(frame);previous_box=box
            if i%30==0: print(f'Lip-sync frame {i+1}/{nframes}',flush=True)
    finally:
        if writer: writer.release()
        if capture: capture.release()
        aligner.close()
    report={'model':'MuseTalk 1.5','frames':nframes,'fps':fps,'face_box':list(map(int,previous_box)),
        'mouth_mean_intensity_change':sum(changes)/max(1,len(changes)),
        'audio_offset_frames':job.get('audio_offset_frames',0),
        'alignment':'tracked landmarks with rotation correction', 'blend':'local mouth feathering',
        'lip_sync':'generated_not_independently_scored','portrait_animation':job['portrait']}
    Path(job['report']).write_text(json.dumps(report,indent=2))
    print('Lip-sync frames completed',flush=True)

if __name__=='__main__':
    job=json.loads(Path(sys.argv[1]).read_text())
    with FileLock(str(settings.TEMP_DIR/'local-video-worker.lock'),timeout=0):
        main(job)
