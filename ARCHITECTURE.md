# DharmaFlow AI — System Architecture & Design Document

## 1. System Overview

DharmaFlow AI is designed as a modular, local-first pipeline for producing vertical devotional short videos (1080x1920 MP4) while ensuring religious authenticity, copyright safety, platform monetization compliance, and predictable resource utilization on modest hardware (NVIDIA RTX 4050 6GB VRAM on Windows 11).

```
+------------------------------------------------------------------------------+
|                             DharmaFlow CLI / API                            |
+------------------------------------------------------------------------------+
                                      |
                                      v
+------------------------+   +------------------------+   +-------------------+
|  Content Planner &     |-->|  Script Generator      |-->|  Originality &    |
|  Topic Backlog         |   |  (Pydantic Validation) |   |  Fingerprint DB   |
+------------------------+   +------------------------+   +-------------------+
                                      |                             |
                                      v                             v
+------------------------+   +------------------------+   +-------------------+
|  Religious Fact-Check  |<--|  Source Registry       |   |  Claim & Evidence |
|  & Verification Status |   |  (Gita, Vedas, Puranas)|   |  Extractor        |
+------------------------+   +------------------------+   +-------------------+
                                      |
                                      v
           +--------------------------+--------------------------+
           |                                                     |
           v                                                     v
+------------------------+                             +--------------------+
| Visual Generation      |                             | Voiceover (TTS)    |
| (ComfyUI / Placeholder)|                             | (EdgeTTS / gTTS)   |
+------------------------+                             +--------------------+
           |                                                     |
           +--------------------------+--------------------------+
                                      |
                                      v
                      +--------------------------------+
                      |   FFmpeg Video Compositor      |
                      |   - 1080x1920 Canvas           |
                      |   - Ken Burns Pan & Zoom       |
                      |   - ASS Devanagari Subtitles   |
                      |   - Loudnorm Audio Normalizer  |
                      +--------------------------------+
                                      |
                                      v
                      +--------------------------------+
                      | Automated Quality Control (QC) |
                      | 10 Automated Blocking Checks   |
                      +--------------------------------+
                                      |
                                      v
                      +--------------------------------+
                      | Human Approval Gate (Web UI)   |
                      | (DRAFT -> VERIFIED -> APPROVED)|
                      +--------------------------------+
                                      |
                                      v
                      +--------------------------------+
                      | Platform Publishing Engine     |
                      | - YouTube Data API v3 (OAuth)  |
                      | - Instagram Graph API          |
                      +--------------------------------+
                                      |
                                      v
                      +--------------------------------+
                      | Analytics & Learning Loop      |
                      | Retention Analysis & Backlog   |
                      +--------------------------------+
```

---

## 2. Core Components & Responsibilities

### 2.1 Core Application Layer
- **`app.core.settings`**: Centralized configuration management using Pydantic Settings, merged hierarchically with `config/config.yaml` and `.env`.
- **`app.core.pipeline`**: Top-level coordinator orchestrating the script -> visuals -> audio -> render -> QC -> persist workflow.
- **`app.core.cost_tracker`**: Resource consumption tracking (VRAM runtime, compute seconds, token counts, external API spend) with hard budget ceilings.
- **`app.core.diagnostics`**: Runtime health check for Python 3.10+, FFmpeg, PyTorch/CUDA, ComfyUI, Ollama, and disk space.

### 2.2 Content Planning & Religious Fact-Checking
- **`app.content.planner`**: Selects topics according to the configured distribution:
  - 30% Scripture Explainers (Bhagavad Gita, Upanishads)
  - 25% Epic Storytelling (Ramayana, Mahabharata)
  - 20% Devotional Reflections
  - 15% Festivals and Cultural Observances
  - 10% Temple and Historical Explainers
- **`app.research.sources`**: Authoritative registry of primary Hindu texts, academic databases (e.g. Gita Supersite IIT Kanpur, Sacred Texts Archive), and almanacs (Drik Panchang).
- **`app.content.source_verifier`**: Validates claims and categorizes statements into:
  - `direct_quotation`
  - `translation`
  - `traditional_interpretation`
  - `historical_claim`
  - `scientific_claim`
  - `original_commentary`
  - `fictionalized_storytelling`
- **`app.content.originality`**: SHA-256 fingerprint database and SequenceMatcher fuzzy similarity scoring preventing duplicate scripts, recycled hooks, or spam metadata.

### 2.3 Media Generation Engine
- **`app.providers.llm`**: Multi-backend LLM abstraction supporting local Ollama (`llama3.2:3b`), OpenAI, Anthropic, Gemini, and deterministic MockLLM.
- **`app.providers.visual`**: Generates 9:16 safe images via ComfyUI (Stable Diffusion 1.5) or Pillow procedural placeholders for zero-GPU/offline environments.
- **`app.providers.tts`**: Synthesizes Hindi, English, and Hinglish speech via Microsoft Edge TTS (`hi-IN-SwaraNeural`), Google TTS, or Piper, with silence fallback.
- **`app.video.renderer`**: Uses FFmpeg to assemble vertical videos:
  - Ken Burns slow zoompan on scenes
  - Audio normalization (`loudnorm=I=-16:TP=-1.5:LRA=11`)
  - Styled ASS subtitles with full Devanagari Unicode support
  - FFprobe stream validation

### 2.4 Quality Control & Human-in-the-Loop Gate
- **`app.quality.checker`**: Enforces 10 automated pre-upload gates:
  1. File existence and non-zero size
  2. FFprobe readability
  3. Video stream orientation (9:16 aspect ratio check)
  4. Audio stream existence and non-silence check
  5. Target duration variance (< 30%)
  6. Scripture verification status check (`VERIFIED` or `APPROVED`)
  7. Flagged unsupported claim check
  8. Script originality check
  9. Metadata length validation
  10. AI-generated disclosure declaration
- **Default Policy**: Manual approval required via Local Web Dashboard. Automated bypass requires explicit configuration in `config.yaml`.

### 2.5 Publishing & Distribution
- **`app.publishing.youtube`**: Official YouTube Data API v3 with OAuth 2.0, token refresh, resumable chunked uploads, and synthetic media disclosure flags.
- **`app.publishing.instagram`**: Official Instagram Content Publishing API for Professional/Creator accounts.
- **Duplicate Upload Prevention**: Prevents republishing already uploaded render jobs.

### 2.6 Persistence Layer
- SQLite database (`data/dharmaflow.db`) with Write-Ahead Logging (WAL) mode enabled for high concurrency between web server and background render worker.

---

## 3. Failure Handling & Recovery Strategies

| Failure Mode | Detection | Automated Recovery Action |
|---|---|---|
| **CUDA Out of Memory (OOM)** | PyTorch / ComfyUI exception | Catch OOM, clear CUDA cache, fallback to CPU or smaller batch size / resolution |
| **Malformed LLM JSON** | `json.JSONDecodeError` / Pydantic `ValidationError` | Up to 3 bounded retries with error feedback prompt |
| **TTS Synthesis Failure** | Non-zero exit code / file size < 1KB | Fallback to secondary TTS provider or silence placeholder with QC warning |
| **FFmpeg Rendering Error** | Non-zero returncode | Clean temporary scene files, record stderr in `RenderJob.error_detail` |
| **YouTube API Quota Exceeded** | HTTP 403 `quotaExceeded` | Mark job as retryable, pause daily publishing until midnight PST |
| **Interrupted Process / Reboot** | Stale lock file in `temp/` | Lock expiration after 1 hour, auto-cleanup on next invocation |

---

## 4. Security & Safety Principles

1. **Zero Secrets in Code**: All API keys, OAuth client secrets, and access tokens are managed via `.env` and `config/client_secret.json`. Both are explicitly ignored in `.gitignore`.
2. **Local Network Binding**: FastAPI binds to `127.0.0.1` by default. Public network exposure is strictly disabled.
3. **Theological Integrity**: Scripts referencing Sanskrit verses must provide verified chapter and verse citations. LLM outputs are never accepted as sole religious authority.
4. **Platform Policy Compliance**: Rejects fear-based hooks, deceptive miracles, and copyright infringements, protecting YouTube channel monetization health.
