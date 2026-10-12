# DharmaFlow AI — End-to-End Automated Hindu Devotional Shorts Factory

DharmaFlow AI is an automated, local-first production pipeline that creates original Hindu devotional, scriptural, and educational short-form vertical videos (1080×1920 MP4) for YouTube Shorts and Instagram Reels. 

The application is engineered specifically for Windows 11 on consumer hardware (tested on NVIDIA GeForce RTX 4050 6GB VRAM) and operates under a zero-cost local inference architecture with human-in-the-loop review gates and strict scripture attribution safeguards.

---

## Table of Contents
1. [Hardware & System Compatibility](#1-hardware--system-compatibility)
2. [Exact Windows 11 Setup Steps](#2-exact-windows-11-setup-steps)
3. [Python Installation & Virtual Environment](#3-python-installation--virtual-environment)
4. [FFmpeg Installation & Verification](#4-ffmpeg-installation--verification)
5. [GPU Driver & CUDA Diagnostics](#5-gpu-driver--cuda-diagnostics)
6. [ComfyUI Installation & Launch Instructions](#6-comfyui-installation--launch-instructions)
7. [Compatible AI Models & Checkpoints](#7-compatible-ai-models--checkpoints)
8. [Model Licensing & Commercial Use Verification](#8-model-licensing--commercial-use-verification)
9. [Text-to-Speech (TTS) Setup](#9-text-to-speech-tts-setup)
10. [LLM Setup (Local Ollama vs Cloud)](#10-llm-setup-local-ollama-vs-cloud)
11. [Configuration & Environment Variables](#11-configuration--environment-variables)
12. [Database Initialization](#12-database-initialization)
13. [Launching the Local Web Dashboard](#13-launching-the-local-web-dashboard)
14. [Running Your First Offline Test Video](#14-running-your-first-offline-test-video)
15. [Generating Your First Production Video](#15-generating-your-first-production-video)
16. [YouTube OAuth 2.0 Authorization](#16-youtube-oauth-20-authorization)
17. [Testing Private Uploads](#17-testing-private-uploads)
18. [Publishing Approval Workflow](#18-publishing-approval-workflow)
19. [Optional Instagram Reels Publishing](#19-optional-instagram-reels-publishing)
20. [Daily Automation & Windows Task Scheduler](#20-daily-automation--windows-task-scheduler)
21. [Analytics & Performance Learning Loop](#21-analytics--performance-learning-loop)
22. [Troubleshooting & Diagnostics](#22-troubleshooting--diagnostics)
23. [Process Management (Stop, Restart, Upgrade)](#23-process-management-stop-restart-upgrade)
24. [Backup & Disaster Recovery](#24-backup--disaster-recovery)
25. [Operating Costs & Resource Accounting](#25-operating-costs--resource-accounting)
26. [Platform Policy & Theological Safeguards](#26-platform-policy--theological-safeguards)

---

## 1. Hardware & System Compatibility

- **Operating System**: Windows 11 Home or Pro (64-bit).
- **Target GPU**: NVIDIA GeForce RTX 4050 Laptop GPU (6 GB GDDR6 VRAM) or higher.
- **System RAM**: 16 GB minimum (32 GB recommended).
- **Disk Storage**: At least 50 GB free NVMe SSD storage for models, render caches, and video archives.
- **Sequential Execution**: Models execute sequentially (LLM -> TTS -> SD 1.5 -> FFmpeg) to never exceed 6 GB VRAM.

---

## 2. Exact Windows 11 Setup Steps

Open PowerShell as Administrator:
```powershell
# 1. Enable long file paths in Windows
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# 2. Verify git and curl are available
git --version
curl --version
```

---

## 3. Python Installation & Virtual Environment

DharmaFlow AI supports Python 3.11 and 3.12.

```powershell
# In project root:
cd "c:\Users\vishe\Desktop\Skills\DharmaFlow AI"

# Create a virtual environment (optional but recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

---

## 4. FFmpeg Installation & Verification

FFmpeg is essential for video composition, Ken Burns camera animation, Devanagari ASS subtitle burning, and loudness normalization.

1. Download the Gyan.dev essentials build from https://www.gyan.dev/ffmpeg/builds/
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your Windows System `PATH`
4. Verify installation:
```powershell
ffmpeg -version
ffprobe -version
```

---

## 5. GPU Driver & CUDA Diagnostics

Verify PyTorch sees your RTX 4050:
```powershell
python -m app gpu
```
Expected output:
```
GPU: NVIDIA GeForce RTX 4050 Laptop GPU
VRAM Total: 6.0 GB
VRAM Free:  6.0 GB
CUDA Version: 12.1
```

If CUDA shows as unavailable, reinstall PyTorch with CUDA 12.1:
```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

## 6. ComfyUI Installation & Launch Instructions

ComfyUI serves as the default local image generation backend.

1. Clone ComfyUI into a sibling folder:
```powershell
git clone https://github.com/comfyanonymous/ComfyUI.git C:\ComfyUI
cd C:\ComfyUI
pip install -r requirements.txt
```
2. Download Stable Diffusion 1.5 weights (`v1-5-pruned-emaonly.safetensors`) from Hugging Face into `C:\ComfyUI\models\checkpoints\`.
3. Launch ComfyUI with low-VRAM optimizations:
```powershell
python main.py --port 8188 --lowvram --preview-method auto
```
4. Verify server is listening at `http://127.0.0.1:8188`.
5. In `config/config.yaml`, set:
```yaml
visuals:
  provider: comfyui
  comfyui:
    enabled: true
    url: http://127.0.0.1:8188
```

---

## 7. Compatible AI Models & Checkpoints

| Component | Default Free/Local Model | Fallback Provider | Memory Footprint |
|---|---|---|---|
| **Script Generation** | Ollama (`llama3.2:3b`) | MockLLM / OpenAI / Anthropic / Gemini | ~2.5 GB RAM / VRAM |
| **Visual Art** | Stable Diffusion 1.5 (`v1-5-pruned`) | Pillow Procedural Placeholder | ~3.8 GB VRAM |
| **Voice Narration** | Qwen3-TTS (`Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`) | Edge-TTS / gTTS / Piper ONNX | ~1.2 GB VRAM / CPU |
| **Compositing** | FFmpeg H.264 (libx264) | NVENC (`h264_nvenc`) | CPU / Hardware encoder |

---

## 8. Model Licensing & Commercial Use Verification

- **Qwen3-TTS**: Open-source model by Alibaba Qwen released under the Apache 2.0 license. Fully permitted for commercial and non-commercial applications.
- **Stable Diffusion 1.5**: Released under the CreativeML Open RAIL-M license. Commercial use is permitted provided ethical content restrictions are honored.
- **Edge-TTS / gTTS**: Uses standard neural voices. Voices are synthetic and do not imitate real living gurus, protecting personal identity rights.
- **Scripture Texts**: Sanskrit texts (Vedas, Upanishads, Gita, Valmiki Ramayana) are ancient public domain heritage. Translations must cite accredited educational sources.
- **Audio & Music**: DharmaFlow AI renders speech with normalized silence or original licensed background tracks. Commercial bhajans and film music are strictly prohibited.

---

## 9. Text-to-Speech (TTS) Setup

### Primary: Qwen3-TTS (Emotional Open-Source AI Model)
DharmaFlow AI utilizes **Qwen3-TTS** (`qwen-tts`), an open-source expressive speech synthesis model from Alibaba Qwen, to produce natural, reverent, and emotionally resonant devotional narrations.

Key features:
- **Emotional Steerability**: Guided by custom `instruct` prompts (e.g. `"Speak in a calm, serene, deeply emotional, devotional tone with reverence."`).
- **Hardware-Friendly (0.6B Checkpoint)**: Uses `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` (~1.2 GB VRAM / bfloat16), fitting well inside the 6 GB VRAM budget alongside sequential pipeline stages.
- **Zero Ongoing Cost**: Open weights under Apache 2.0 license.
- **Configurable Voices & Styles**: Change speaker (e.g. `Ryan`) and adjust spiritual tones (`instruct`) in `config/config.yaml`.
- **Fault-Tolerant Fallback**: If weights are downloading or offline, DharmaFlow AI seamlessly falls back to high-fidelity Edge-TTS or gTTS without failing the video pipeline.

Configuration in `config/config.yaml`:
```yaml
tts:
  provider: qwen3
  language: hi
  speed: 1.0
  qwen3:
    model_name: "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
    speaker: "Ryan"
    instruct: "Speak in a calm, serene, deeply emotional, devotional tone with reverence."
```

### Fallback 1: Microsoft Edge-TTS (Free Neural Voices)
High-fidelity cloud neural speech for Hindi and English without local GPU memory overhead:
- Hindi: `hi-IN-SwaraNeural` (female) or `hi-IN-MadhurNeural` (male)
- Indian English: `en-IN-NeerjaNeural`

Test speech synthesis via CLI:
```powershell
edge-tts --voice hi-IN-SwaraNeural --text "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन" --write-media test.mp3
```

### Fallback 2: Piper TTS & gTTS
- **Piper**: Fully offline fast local neural TTS with ONNX runtime.
- **gTTS**: Lightweight fallback requiring minimal bandwidth.

---

## 10. LLM Setup (Local Ollama vs Cloud)

### Option A: Local Ollama (Recommended Free)
1. Download Ollama from https://ollama.ai/
2. Pull the lightweight 3B model:
```powershell
ollama run llama3.2:3b
```
3. Set `llm.provider: local` in `config/config.yaml`.

### Option B: Cloud API (OpenAI / Anthropic / Gemini)
Set your API key in `.env`:
```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_key_here
```

---

## 11. Configuration & Environment Variables

Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Key configuration settings in `config/config.yaml`:
- `content.timezone`: `Asia/Kolkata`
- `content.daily_video_limit`: `1`
- `content.require_human_approval`: `true`
- `video.width` / `height`: `1080` / `1920` (9:16 vertical)
- `safe_mode`: `true` (enforces all 10 QC checks)

---

## 12. Database Initialization

DharmaFlow AI uses an embedded SQLite database with Write-Ahead Logging (`data/dharmaflow.db`). Tables are initialized automatically:
```powershell
python -m app doctor
```

---

## 13. Launching the Local Web Dashboard

Start the local server:
```powershell
python -m uvicorn app.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser to: **http://127.0.0.1:8000**
- View KPI Overview
- Generate Scripts in Content Studio
- Inspect Renders in Video Studio
- Approve or Reject Videos
- Track Publishing and System Diagnostics

---

## 14. Running Your First Offline Test Video

To test the entire pipeline with zero credentials, zero internet, and no GPU load:
```powershell
python -m app demo
```
This procedurally generates:
1. Validated Pydantic script with chapter and verse references
2. Procedural 9:16 safe artwork with Sanskrit watermark
3. Synthesized test audio and ASS Devanagari subtitles
4. Full vertical MP4 render verified via FFprobe
5. Persisted record and QC score in SQLite

---

## 15. Generating Your First Production Video

```powershell
python -m app generate --topic "The Meaning of Equanimity in Bhagavad Gita Chapter 2" --category scripture_explainer --language hi --duration 45 --preset standard
```

---

## 16. YouTube OAuth 2.0 Authorization

1. Visit [Google Cloud Console](https://console.developers.google.com/).
2. Create a project and enable **YouTube Data API v3**.
3. Create **OAuth 2.0 Client ID** (Desktop Application).
4. Download the JSON and save as `config/client_secret.json`.
5. Run authorization:
```powershell
python -m app youtube-auth
```
A browser window will open requesting consent. Once granted, tokens are safely saved to `config/youtube_token.json`.

---

## 17. Testing Private Uploads

Upload a rendered video safely as `private`:
```powershell
python -m app upload --video "output\<job_id>\final_video.mp4" --title "Bhagavad Gita Wisdom #Shorts" --privacy private
```

---

## 18. Publishing Approval Workflow

By default, every video follows strict human review:
1. Generation completes -> Status: `PENDING_APPROVAL`
2. Open Dashboard -> **Video Studio** -> Review video and QC checks
3. Click **Approve for Publishing**
4. The publishing engine or daily automation proceeds with upload

---

## 19. Optional Instagram Reels Publishing

1. Add your Meta Graph API credentials to `.env`:
```env
INSTAGRAM_ENABLED=true
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_id
```
2. Verify account connectivity via the dashboard Publishing tab.

---

## 20. Daily Automation & Windows Task Scheduler

Register DharmaFlow AI to run every morning at 06:30 AM IST:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -DailyTime "06:30AM"
```
To remove the task:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\unregister_task.ps1
```

---

## 21. Analytics & Performance Learning Loop

Poll statistics for uploaded videos:
```powershell
python -c "from app.database.session import get_session_factory; from app.analytics.engine import AnalyticsEngine; db = get_session_factory()(); AnalyticsEngine(db).sync_youtube_metrics()"
```
The learning loop analyzes average retention, views, and engagement across content categories and recommends future backlog topics.

---

## 22. Troubleshooting & Diagnostics

Refer to [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed diagnostic steps regarding:
- CUDA Out of Memory (OOM) mitigation
- FFmpeg filter graph path escaping
- Google API Quota limits (10,000 units/day)
- Unverified Google Project public upload restrictions

---

## 23. Process Management (Stop, Restart, Upgrade)

- **Stop Local Server**: Press `Ctrl + C` in the uvicorn terminal.
- **Stale Lock Cleanup**: If interrupted, delete `temp/dharmaflow_daily.lock`.
- **Safe Upgrade**: Run `git pull`, then `pip install -r requirements.txt`, followed by `pytest tests`.

---

## 24. Backup & Disaster Recovery

Backup database and configuration:
```powershell
Copy-Item "data\dharmaflow.db" "data\backup_dharmaflow.db"
Copy-Item "config\config.yaml" "config\backup_config.yaml"
```

---

## 25. Operating Costs & Resource Accounting

- **Local Inference (Ollama + SD 1.5 + EdgeTTS)**: **$0.00 / video**
- **Cloud LLM (Optional Gemini Flash / GPT-4o-mini)**: **< $0.002 / video**
- **Storage Consumption**: ~3 MB per rendered 45-second 1080x1920 MP4 (approx. 1 GB per year for daily publishing).
- **Spending Caps**: Enforced via `MONTHLY_API_SPEND_CAP_USD` (default: $10.00).

---

## 26. Platform Policy & Theological Safeguards

- **No Fabricated Scripture**: Primary verses must be verifiable with chapter and verse citations.
- **Anti-Clickbait Guard**: Pydantic schema validation rejects sensationalist, fear-based, or manipulative hooks.
- **Duplicate Protection**: SHA-256 fingerprint database blocks duplicate narration or recycled metadata.
- **AI Transparency**: Automatically includes required Altered/Synthetic Content disclosures in compliance with YouTube Community Guidelines.
