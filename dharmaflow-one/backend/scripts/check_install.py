"""Fast import and binary checks, with no downloads or paid requests."""
import importlib
import shutil
import sys

def main():
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('Use Python 3.12 for this desktop release.')
    for binary in ('ffmpeg', 'ffprobe', 'git', 'ollama'):
        if not shutil.which(binary):
            raise RuntimeError(f'Missing command: {binary}')
    for module in ('backend.main', 'torch', 'torchvision', 'torchaudio', 'diffusers',
                   'transformers', 'accelerate', 'mediapipe', 'qwen_tts', 'cv2',
                   'librosa', 'einops', 'python_speech_features'):
        importlib.import_module(module)
    print('Application imports and required commands passed.')

if __name__ == '__main__':
    main()
