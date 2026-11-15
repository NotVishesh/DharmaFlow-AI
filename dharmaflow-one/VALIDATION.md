# Validation — 27 October 2026

- Backend: **21 tests passed**. Includes actual FFmpeg encoding, audio/video start/end checks, decoded audio across scene joins, still/frozen/short clip rejection, pipeline Review/Turbo, retry reuse, API queue persistence and credential separation, native worker failure handling, hardware/VRAM, downloads and mocked YouTube.
- Browser: **5 Playwright tests passed**. API responses are mocked; these verify interaction behavior, setup blocking and test-mode disclosure.
- TypeScript checks and Electron/frontend production build: passed.
- Electron integration smoke: real desktop + React + FastAPI + FFmpeg, synthetic providers. Three scenes exported, decoded video playback confirmed, measured stream timing offset **0.67 ms**. No YouTube upload performed.
- Uneven-length audio test: two source WAVs at 2.15 s and 3.42 s, with breathing pads and frame alignment, exported 6.2 s video / 6.199 s audio: **1 ms** offset.
- Live Ollama script and storyboard generation: passed with the installed llama3.2:3b model; approved narration words preserved.
- Live local speech: Qwen 0.6B generated spoken narration from cached weights. Windows system speech fallback was also exercised.
- Local video weights: **19 files, 26.94 GiB**, pinned repository revision recorded in backend/models/wan-2.1-1.3b/verified.json. Model weight SHA-256 hashes checked against repository metadata.
- Cloud provider: HTTP contract tested with a fake queue and media server. No live cloud generation was submitted; FAL_KEY is not configured.

Real local video visual acceptance is recorded below. Synthetic tests are not evidence of artistic quality or semantic subject motion. Timing reports do not establish lip-sync.


## 28 October — Windows manual web launch regression

- Backend suite: **25 passed** after replacing all asyncio subprocess transport calls with the shared process runner.
- Explicit `asyncio.SelectorEventLoop` regression exercised actual FFmpeg synthesis, FFprobe measurement, moving-video generation and muxing.
- The reported project's `scene_0.wav` successfully probed on SelectorEventLoop: **4,000 ms** including breathing pad/frame alignment.
- Cancellation test confirmed the interpreter child is gone after cancelling the virtualenv launcher. Timeout and event-loop responsiveness tests also passed.
- Existing backends must restart to load the fix. No event-loop policy override is required.

## 28 October — real local motion-video sample

- Project: `a3c65ad6-600b-4d46-ac4b-bf05e175d0fe`, final state `WAIT_VIDEO_REVIEW`; no mock providers or cloud API used.
- Wan 2.1 1.3B, 30 steps, seed 42, resident transformer, bounded/disk-offloaded text encoder. Both supplied prompt embeddings explicitly moved to CUDA.
- Actual generated source: 480 × 832, 16 fps, 4.0625 seconds. Final narrated export: 1080 × 1920, 30 fps, 4 seconds; upscaled source, not native 1080p.
- Audio/video stream durations both 4 seconds; maximum start/end offset **0 ms**. This checks narration timeline alignment, not lip-sync or semantic event timing.
- Sampled decoded frames at one-second intervals show changing fox poses and a jump down from the log; stable forest composition and warm lighting. This is subject motion, not a still-image zoom. The action differs slightly from the request to leap over the log.
- Inference alone took **15 minutes 10 seconds**, with additional model loading, decoding and muxing time. Local generation is practical for patient testing, not rapid iteration on this laptop.
- Output: `backend/media/a3c65ad6-600b-4d46-ac4b-bf05e175d0fe/final_video.mp4`; measured report alongside it. Generated media remains gitignored.

## Connected one-minute film update

- Backend full suite: **29 passed**; subsequent focused planning/migration suite: **5 passed**, including the newly added migration test and tightened narration length requirement.
- Frontend TypeScript check and production build passed. Browser suite: **6 passed**, including default 60-second selection and duration submission to the API.
- Live Ollama generated **12 scenes / 106 spoken words** for a connected fox story. Approved narration is assigned directly to scenes, with shared visual continuity details repeated in each prompt. Saved as `ONE_MINUTE_STORYBOARD.md`.
- Timeline checks reserve 60 seconds across twelve short beats while retaining longer speech. Existing-database migration tested twice for idempotence and preservation of the old project.
- A full 60-second AI render has not been run. Earlier four-second genuine local generation and multi-scene FFmpeg integration remain the media evidence; the longer local render is expected to take hours.

## Encoder budget regression fix

The 2 GiB CPU/GPU budgets introduced for sequential mode caused Accelerate to map the entire UMT5 encoder to disk and reject dispatch. Restored 3 GiB budgets for the encoder independently of diffusion offload mode. Ran the real scene 9 prompt from project 9bfab2e3-6745-4bb3-94b6-211d6ff7be52 through the encode worker in sequential mode: exit code 0, both embedding tensors saved and finite. No diffusion or full project render was started during this validation. This confirms the disk-offload regression fix, not immunity from native crashes.

## Reproduced native offload-read crash and compatibility fix

- Reproduced scene 9 shot 2 failure with faulthandler enabled. Stack: Accelerate offload `__getitem__` → safetensors `get_tensor` → Torch storage `__getitem__`, Windows access violation. The earlier memory-budget fixes alone did not resolve it.
- Added worker-local owned-buffer reads for offloaded safetensors weights, checked headers/offsets/lengths, bounded to one tensor per read. No installed library or model file modifications. GPU encoder budget 4 GiB, CPU weight budget zero, disk overflow.
- Exact failing prompt encoded successfully **three times in fresh processes**, finite embeddings saved each time, exit code 0.
- Those embeddings passed through sequential diffusion and MP4 export: **17 frames, 480x832, 1.0625 seconds**, exit code 0; all frames decoded by FFmpeg without errors. This was a two-step diagnostic render, not a visual-quality acceptance render.
- Full backend suite **38 passed**, plus subsequent embedding-cache regression **1 passed**. Includes owned BF16/FP16/FP32 buffers, truncated file detection, native crash retry limits and completed-shot reuse.
- The remaining full project render has not been started. No guarantee against unrelated hardware/driver failures is implied.

## Fractional-shot frame-count fix

Repaired Bible project abbf6172-9e8f-49f7-8b1b-50b9fd9feaf6 scene 1 using its two cached generated shots. Fractional per-shot duration trims previously yielded 162 frames (5.4 seconds) for a 163-frame narration timeline. The join now partitions an integer frame budget, trims by end_frame, and uses an explicit 30 fps output clock. Repaired output: 163 frames / 5.433333 seconds; narrated mux offset 0.33 ms. Saved the repaired scene path so resume skips it. No AI generation was started. Regression cases cover odd/even frame totals across two and three shots.

## Local speaking-character integration

- Added optional MuseTalk 1.5 stage, project/API/CLI/UI flag, additive database migration, early setup checks, and matching-source/audio cache. One clear frontal face is required. Source frames are preserved for moving-video projects; no looping on short input.
- Live Krishna talking-portrait test succeeded locally on RTX 4050 6 GB: 174 frames / 5.8 seconds / 30 fps, audio/video stream offset 0 ms. Sampled decoded frames show changing mouth shapes. The face crop is 256×256; visible mouth softness/blending remains. Phoneme-level alignment was not independently scored.
- Portrait generated with built-in ImageGen; Hindi sample speech uses online gTTS after Edge-TTS returned HTTP 403. The sample is portrait mouth animation, not full-body video. Prompt, speech and provenance are in the sample ABOUT.md.
- Backend suite: **45 passed**. Frontend production build and TypeScript check passed. Browser suite: **6 passed**, including the speaking-character flag submission.
- Full moving-video plus lip-sync integration tested with a stub lip-sync provider for pipeline routing; the live model acceptance test used the Krishna portrait. Moving-head tracking across arbitrary generated footage remains unverified.

## Moving Krishna replacement (2026-10-30)

This supersedes the portrait-only acceptance example above. Wan generated 480x832 moving footage; sampled frames show head tilt and a raised-hand gesture. MuseTalk then processed all 97 frames with tracked landmark rotation correction and mouth-only blending. Output: backend/media/krishna-motion-v2/krishna-speaking-offset0.mp4, 3.233 seconds, 30 fps. Stream start/end mismatch: 0.67 ms.

Independent SyncNet v2 diagnostic: estimated offset -40 ms, confidence 1.3216, minimum distance 11.4516. Low confidence on this short stylized face means phoneme alignment is NOT verified; no automatic offset adjustment was applied. Mouth softness remains visible. Previous rejected portrait estimated -120 ms with confidence 4.3871; these different clips cannot establish a reliable improvement in articulation from offset alone.

Backend suite after landmark changes: 47 passed. Focused geometry and blend tests rerun: 2 passed. Actual moving-video worker and CPU SyncNet evaluation both completed successfully. Long/profile/occluded-face sequences remain unverified.
