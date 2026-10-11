# DharmaFlow AI — Troubleshooting & Diagnostics Manual

This guide provides concrete solutions and diagnostic commands for common issues encountered when running DharmaFlow AI on Windows 11 with an NVIDIA RTX 4050 GPU (6 GB VRAM).

---

## 1. Quick Diagnostic Commands

Run these first to isolate any system-level issue:

```powershell
# 1. Environment & Dependency Check
python -m app doctor

# 2. GPU, VRAM, and CUDA Diagnostics
python -m app gpu

# 3. Verify PyTorch sees CUDA & GPU
python -c "import torch; print('CUDA Available:', torch.cuda.is_available(), 'Device:', torch.cuda.get_device_name(0))"

# 4. Verify FFmpeg has libx264, libass (subtitles), and AAC
ffmpeg -version

# 5. Run the offline zero-dependency demo
python -m app demo
```

---

## 2. GPU & VRAM (RTX 4050 6 GB) Issues

### Issue A: CUDA Out of Memory (OOM) during Image Generation
**Symptoms:** `torch.cuda.OutOfMemoryError: CUDA out of memory` or ComfyUI freezes.
**Root Cause:** Attempting to run large batch sizes, SDXL, or high resolutions exceeding 6 GB VRAM.
**Solutions:**
1. In `config/config.yaml`, verify image dimensions are bounded:
   ```yaml
   visuals:
     comfyui:
       width: 768
       height: 1344   # Safe 9:16 portrait on 6GB VRAM
   ```
2. When launching ComfyUI, always pass low-VRAM arguments:
   ```powershell
   python main.py --lowvram --preview-method auto
   ```
3. Use Stable Diffusion 1.5 checkpoints (`v1-5-pruned-emaonly.safetensors`), not heavy SDXL/Flux models.

### Issue B: PyTorch Reports `CUDA: False`
**Symptoms:** `torch.cuda.is_available()` returns `False` despite having an NVIDIA GPU.
**Solutions:**
1. Check NVIDIA Driver version using `nvidia-smi`. Ensure driver is >= 535.
2. Reinstall PyTorch with CUDA 12.1 wheel:
   ```powershell
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

---

## 3. Video Rendering & FFmpeg Issues

### Issue A: Subtitle Filter Error (`[Parsed_ass_0] Could not find font`)
**Symptoms:** Subtitles fail to render or Sanskrit Devanagari text shows up as boxes/question marks.
**Solutions:**
1. Ensure a Devanagari font is installed on Windows 11:
   - "Noto Sans Devanagari" or "Mangal" or "Nirmala UI"
2. On Windows, FFmpeg filter paths require escaping colons and using forward slashes:
   - Correct syntax: `-vf "ass='C\:/path/to/subtitles.ass'"`
   - DharmaFlow's `app/video/renderer.py` automatically normalizes Windows paths for libass.

### Issue B: FFmpeg Command Exits with Code 1 or Missing Codec
**Symptoms:** `Unrecognized option 'preset'` or `Unknown encoder 'libx264'`
**Solutions:**
1. Check that you are using a full FFmpeg build (Gyan.dev essentials or full build):
   ```powershell
   ffmpeg -encoders | findstr "264"
   ```
2. Ensure FFmpeg is registered in system environment variables `PATH`.

---

## 4. Voiceover & TTS Issues

### Issue A: Edge-TTS Fails with Connection Error
**Symptoms:** `aiohttp.ClientConnectorError` or `WSServerHandshakeError`
**Solutions:**
1. Edge-TTS requires an active internet connection to communicate with Microsoft's neural TTS endpoint.
2. If offline, switch to the local Piper engine or offline demo mode:
   In `config/config.yaml`:
   ```yaml
   tts:
     provider: gtts   # or "piper" with local ONNX model
   ```
3. If running headless without network, use the offline demo flag: `--demo`.

---

## 5. YouTube API & OAuth 2.0 Issues

### Issue A: `client_secret.json not found`
**Symptoms:** `FileNotFoundError: client_secret.json not found at config/client_secret.json`
**Solutions:**
1. Go to Google Cloud Console: https://console.developers.google.com/
2. Enable "YouTube Data API v3".
3. Under "Credentials", create "OAuth client ID" -> Application type: "Desktop app".
4. Download the JSON file and save it as `config/client_secret.json`.
5. Run the authentication command:
   ```powershell
   python -m app youtube-auth
   ```

### Issue B: `HTTP 403 quotaExceeded`
**Symptoms:** `The request cannot be completed because you have exceeded your quota.`
**Root Cause:** Google API default daily quota is 10,000 units. A video upload costs 1,600 units. Attempting more than 6 uploads per day exceeds the default tier.
**Solutions:**
1. DharmaFlow enforces `daily_upload_limit: 1` in `config/config.yaml`.
2. Quotas reset daily at midnight Pacific Time (PST).
3. For commercial scale, submit a YouTube API Quota Increase request via Google Cloud Console.

### Issue C: Upload Stuck as "Private"
**Notice:** Unverified Google API projects are restricted by Google to private uploads only. To allow public uploads via API, submit your project for YouTube API developer verification. Alternatively, upload as private and review/publish manually in YouTube Studio.

---

## 6. Process Recovery, Backups & Cleanup

### Stale Process Lock
If a job was abruptly terminated or the laptop restarted during an active run, a lock file might persist:
```powershell
# Remove stale lock if process is not running
Remove-Item "temp\dharmaflow_daily.lock" -Force -ErrorAction SilentlyContinue
```

### Database Backup
The entire database and state is stored in SQLite:
```powershell
# Create backup
Copy-Item "data\dharmaflow.db" "data\dharmaflow_backup_$(Get-Date -Format 'yyyyMMdd').db"
```
