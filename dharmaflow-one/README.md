# DharmaFlow One — motion-video edition

The maintained application is in this folder. The parent `app/` directory is the older application.

## Start on Windows

From this directory:

```powershell
..\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-video.txt
ollama pull llama3.2:3b
npm install
npm run build
npm start
```

Ollama must be running. The Electron app starts the Python API and opens the compiled frontend. For browser development, run `..\.venv\Scripts\python.exe -m uvicorn backend.main:app` and `npm run dev` in separate terminals.

In Setup, click **Download Local Video Model**. Downloads resume and model weight SHA-256 hashes are checked before readiness. This is a large download (approximately 27 GiB); leave at least 12 GiB additional working space for disk offloading and temporary files. The download does not install Python dependencies. A missing dependency is shown separately. A fresh install also needs CUDA-enabled PyTorch compatible with the GPU; preserve the existing CUDA installation on this machine.

## Actual generation

The default `VIDEO_PROVIDER=local` uses Wan 2.1 T2V 1.3B to synthesize moving frames at 480 × 832, 16 fps. VAE tiling reduces GPU memory pressure; optional sequential CPU offload lowers it further. The text encoder has a 4 GiB GPU budget with remaining layers streamed from disk through bounded owned buffers, and is unloaded before the video transformer loads. Inference runs in a separate worker process, so native failures can be reported without crashing the desktop backend. On the current RTX 4050 6 GB / 16 GB RAM machine this is memory constrained and can be very slow or run out of RAM. A real four-second fox-action sample completed on this machine on October 28: 30 inference steps took 15 minutes, plus model loading, frame decoding and export. It contains generated subject motion and spoken narration; its final stream timing offset measured 0 ms. The original model's unoptimized GPU requirement exceeds 6 GB.

Final delivery is 1080 × 1920, 30 fps, H.264 CRF 18 and AAC. Scaling does **not** create native 1080p detail, and frame-rate conversion does not create new model motion. The API option generates at native 720p. Neither provider can guarantee artistic quality; review every export.

Ollama writes a short narration and action-based shot prompts. The approved narration is checked for word preservation. Speech uses Qwen when available, then the Windows offline voice, then installed network speech providers. Production does not substitute canned scripts, test tones, images, stock footage, or cards.

Narration is measured first with 300 ms breathing room, rounded to a video frame. Longer scenes generate multiple shots; independently generated shots may have visual continuity differences. Clips must have multiple frames and detectable frame changes. Frozen or short clips fail rather than loop. This detector is a freeze heuristic, not a semantic motion or beauty classifier.

## Optional paid API fallback

Copy `backend/.env.example` to `backend/.env` if no configuration exists. Preserve any existing settings. Set:

```dotenv
VIDEO_PROVIDER=local_then_fal
FAL_KEY=your_private_fal_key
```

Restart the backend. This explicitly enables sending visual prompts to fal after a local failure, with charges on your fal account. `VIDEO_PROVIDER=fal` bypasses local inference. `VIDEO_PROVIDER=local` never submits paid generation requests. Keys stay on the backend and are not returned by the status API. Queued jobs are saved next to their shot files to avoid submitting the same request twice when called again with the same parameters. No API key is bundled.

## Audio checks and limits

Each scene and the final export must have audio and video stream starts/ends within 50 ms. The final join rebuilds a continuous timeline to avoid accumulating AAC encoder padding. `quality_report.json` beside each export records measurements, source resolution, provider, and test-mode status. `/api/projects/{id}/quality` exposes it to the preview screen.

This is narration over footage. It does not generate or verify character lip-sync, lyric timing, speech intelligibility, or music beat alignment. No truncated, static subtitle overlays are added. The preview is the final human review gate before upload.

## Tests

```powershell
..\.venv\Scripts\python.exe -m pytest backend/tests -q
npx tsc --noEmit -p frontend/tsconfig.json
npm run build
npm run test:e2e
node scripts/smoke-electron.cjs
```

Backend tests use isolated temporary databases/media, synthetic moving patterns and tones. They test actual FFmpeg encoding and decoded audio at scene boundaries. The Electron smoke test uses the real frontend/API/FFmpeg pipeline with synthetic providers and verifies decoded playback. Browser tests use mocked API responses; they validate UI behavior, not real AI inference or YouTube publication. `DHARMAFLOW_MOCK_AI=1` is test-only and visibly labeled.

Sources: [Wan model](https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B-Diffusers), [Diffusers Wan documentation](https://huggingface.co/docs/diffusers/api/pipelines/wan), [fal Wan 2.2 API](https://fal.ai/models/fal-ai/wan/v2.2-a14b/text-to-video/api).


## Windows manual browser launch (including reload)

From the workspace root, start these in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --app-dir .\dharmaflow-one --host 127.0.0.1 --port 8000 --reload
npm --prefix .\dharmaflow-one run dev
```

Open http://127.0.0.1:5173. Stop the existing backend with Ctrl+C before restarting it; do not start another backend on the same port.

The October 28 fix replaces asyncio subprocess transports with a thread-backed process runner. This supports Windows SelectorEventLoop (used by some manual/reload server launches) as well as ProactorEventLoop. FFprobe, FFmpeg, speech conversion and the video worker all use it. Timeouts/cancellation terminate the Windows interpreter process tree, not just the virtualenv launcher. After updating, restart the backend and click **Retry after fixing setup** on the failed project.

`VIDEO_OFFLOAD=resident` keeps the video transformer resident during each shot for better speed. The large text encoder still uses bounded CPU/GPU memory plus disk offload. Use `VIDEO_OFFLOAD=sequential` for lower peak GPU usage if resident mode runs out of VRAM.

## Connected films up to two minutes

New projects default to **1 minute / 12 scenes**. The duration selector also offers 15 seconds, 30 seconds and 2 minutes. The local writer creates one short narration line per five-second story beat. The storyboard adds shared character appearance, setting, palette and lighting to every shot, plus a different scene action. Review mode lets you edit each narration line and visual prompt before rendering. Keep one line per scene in script review.

The pipeline synthesizes speech, reserves each scene's share of the target duration, generates enough new moving footage, and joins all scenes into one narrated export. Speech that needs more time extends the film rather than being truncated. Duration is a target/minimum, not a promise of exactly 60 seconds. Separately generated shots can vary in character appearance; text continuity is not reference-image identity locking.

Based on the four-second local benchmark, a minute can take several hours on this laptop. Completed scenes survive retries. The full minute-long AI render has not been benchmarked; the live 12-scene planning pass and automated timeline checks have been verified. See `ONE_MINUTE_STORYBOARD.md` for the generated example. Restart the backend and reload the frontend to use the new duration control. Existing projects remain intact; an additive startup migration gives older projects a 15-second legacy target.

## Resume a failed CLI film

From this directory, run:

```powershell
..\.venv\Scripts\python.exe -u -m backend.scripts.generate_film --resume PROJECT_UUID --offload sequential
```

Add `--check` to inspect saved progress without rendering. Resume requires FAILED status and reuses existing scene assets. The CLI defaults to sequential offload to reduce peak GPU memory. Do not start another renderer for the same project simultaneously.

Local inference now separates text encoding and diffusion into independent worker processes; the encoder process exits before diffusion loads. Native access violations and out-of-memory exits get one bounded retry per stage in a fresh worker with sequential offload. Each attempt retains its own log. Successfully validated new shots have matching completion receipts so partial scenes can reuse them on retry. Older completed scenes remain reusable through the project database. These mitigations do not guarantee against driver, hardware or native-library failures.

## Windows offloaded-weight access violation

The reproduced encoder crash stack entered `accelerate.utils.offload.OffloadedWeightsLoader.__getitem__`, `safetensors.get_tensor`, and `torch.storage.__getitem__`. Workers now install a local compatibility reader for that offload path. It reads one tensor at a time into an owned byte buffer and checks offsets and lengths before constructing a tensor, avoiding the failing memory-mapped storage slice. Installed packages and model weights are unchanged.

Worker processes also serialize access to shared offload files using a file lock, constrain native CPU threads, and record fatal exception stacks. Successful prompt embeddings are written atomically and retained with a prompt/model fingerprint; matching retries skip encoding. Changed prompts invalidate the cache. These are specific recovery and compatibility measures, not a guarantee against every possible hardware or driver error.

## Speaking characters (optional lip-sync)

Enable **Character speaks (lip-sync)** before creating a project, or add `--lip-sync` to the generation CLI. This runs local MuseTalk 1.5 after moving-video generation and before final muxing, with one frame per inference batch to fit the 6 GB GPU. Speak in first person and use one unobstructed frontal face per shot; avoid crowds, profile views, fast head turns, masks or hands across the mouth. The integration rejects missing/multiple detected faces rather than silently choosing a speaker. Scene mouth animation is cached for matching source video and audio.

Install on another machine from this directory:

```powershell
..\.venv\Scripts\python.exe -m pip install -r backend/requirements-video.txt -r backend/requirements-lipsync.txt
..\.venv\Scripts\python.exe -m backend.scripts.install_lipsync
```

Then generate a speaking character:

```powershell
..\.venv\Scripts\python.exe -u -m backend.scripts.generate_film --seconds 15 --lip-sync --prompt "A friendly character in a frontal close-up tells the viewer a short playful story in first person. Only one visible face, minimal head movement."
```

The Krishna sample is `backend/media/krishna-lipsync-test/krishna-speaking.mp4`: a 5.8-second talking portrait, not a full-body action scene. Its Hindi voice uses the online gTTS fallback; local Qwen speech in the normal pipeline does not guarantee Hindi support. A user-supplied WAV may be passed to `animate_speech` for precise language/voice choice. MuseTalk edits a 256×256 face crop, so high-resolution exports do not imply native high-resolution lips. Blend quality and visual speech alignment require review. Reports say `generated_not_independently_scored`; stream timing is measured separately.

Source: [official MuseTalk](https://github.com/TMElyralab/MuseTalk), MIT license, pinned source revision `0a89dec45a0192b824e3cf4daf96c239440c5ed8`. The integration uses its VAE, UNet and speech-feature modules with MediaPipe tracked face landmarks, eye-line rotation correction, deterministic face latents and a feathered mouth-only blend, instead of the upstream DWPose/face-parser stack. Large profile turns, occlusion and face deformation can still fail tracking. Model downloads are recorded in `backend/models/lipsync/manifest.json`.

## Moving Krishna test, revised lip alignment

The previous portrait-only example is not the acceptance standard for moving characters. The revised test first generates actual head/arm/fabric motion with Wan, then applies landmark-aligned mouth animation to those frames. Test line: “मैया, थोड़ा सा माखन दे दो ना!” (Mother, please give me a little butter!).

```powershell
..\.venv\Scripts\python.exe -u -m backend.scripts.render_krishna_motion
..\.venv\Scripts\python.exe -u -m backend.scripts.render_krishna_lipsync
```

The second command requires the first to have completed. It does not substitute the old still portrait. Local model generation can take many minutes even for this short clip. Install the updated requirements-lipsync.txt and rerun install_lipsync to fetch the MediaPipe landmark model on a fresh setup.

An optional independent SyncNet diagnostic estimates audio/visual lag, separate from stream duration checks:

```powershell
..\.venv\Scripts\python.exe -m backend.scripts.install_syncnet
..\.venv\Scripts\python.exe -m backend.scripts.evaluate_lipsync PATH_TO_VIDEO
```

SyncNet is a diagnostic, not proof of perfect articulation: short dialogue and stylized child faces may be outside its training distribution. Do not automatically treat its offset or confidence as a universal pass/fail threshold. Manual timing correction is available with render_krishna_lipsync --offset N (30 fps audio-feature frames); evaluate the adjusted output again.
