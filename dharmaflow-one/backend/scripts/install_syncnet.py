"""Install the optional independent SyncNet timing diagnostic."""
from pathlib import Path
import subprocess,urllib.request
from backend.config import settings
REVISION='907c0b579c2e2d83f0eae1b2ac9e720cde4e5623'
def main():
 root=Path(__file__).resolve().parents[1]
 repo=root/'vendor/syncnet_python'
 if not repo.exists(): subprocess.run(['git','clone','https://github.com/joonson/syncnet_python.git',str(repo)],check=True)
 subprocess.run(['git','-C',str(repo),'checkout','--detach',REVISION],check=True)
 model=settings.MODELS_DIR/'lipsync/syncnet_v2.model'
 if not model.exists():
  urllib.request.urlretrieve('https://www.robots.ox.ac.uk/~vgg/software/lipsync/data/syncnet_v2.model',model)
 print('SyncNet diagnostic installed; evaluate with python -m backend.scripts.evaluate_lipsync VIDEO_PATH')
if __name__=='__main__':main()
