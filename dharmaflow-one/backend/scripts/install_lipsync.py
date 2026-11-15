"""Install the pinned MuseTalk source and required official model files."""
from pathlib import Path
import json,subprocess
from huggingface_hub import snapshot_download,HfApi
from backend.config import settings
REVISION='0a89dec45a0192b824e3cf4daf96c239440c5ed8'
def main():
 root=Path(__file__).resolve().parents[1]
 vendor=root/'vendor/MuseTalk'
 if not vendor.exists():
  subprocess.run(['git','clone','https://github.com/TMElyralab/MuseTalk.git',str(vendor)],check=True)
 subprocess.run(['git','-C',str(vendor),'checkout','--detach',REVISION],check=True)
 modelroot=settings.MODELS_DIR/'lipsync';modelroot.mkdir(parents=True,exist_ok=True)
 import urllib.request
 landmark=modelroot/'face_landmarker.task'
 if not landmark.exists():
  urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',landmark)
 manifest={'source_revision':REVISION,'models':[]}
 for repo,folder,patterns in [
  ('TMElyralab/MuseTalk','musetalk',['musetalkV15/*']),
  ('stabilityai/sd-vae-ft-mse','vae',['config.json','diffusion_pytorch_model.bin']),
  ('openai/whisper-tiny','whisper',['config.json','model.safetensors','preprocessor_config.json'])]:
  revision=HfApi().model_info(repo).sha
  snapshot_download(repo,revision=revision,local_dir=str(modelroot/folder),allow_patterns=patterns,max_workers=2)
  manifest['models'].append({'repo':repo,'revision':revision})
 (modelroot/'manifest.json').write_text(json.dumps(manifest,indent=2))
 print('Lip-sync installed. Use --lip-sync for a new speaking-character project.')
if __name__=='__main__': main()
