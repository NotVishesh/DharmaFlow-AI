# DharmaFlow AI — Implementation Plan & Roadmap

## 1. Project Overview & Mission
**DharmaFlow AI** is a production-grade, automated Hindu devotional short-form video generation system designed for YouTube Shorts and Instagram Reels. It creates original Hindi, English, and Hinglish devotional, philosophical, and cultural educational content grounded in authentic Hindu scriptures (Bhagavad Gita, Upanishads, Valmiki Ramayana, Mahabharata, Puranas).

### Hardware & Environment Constraints
- **Target OS**: Windows 11 Home
- **GPU**: NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)
- **Local Acceleration**: PyTorch 2.5.1 + CUDA 12.1 / NVENC FFmpeg
- **VRAM Budgeting**: Sequential model execution, strict 6 GB VRAM limits, CPU fallbacks for compositing, and OOM error handling.

---

## 2. Milestones & Acceptance Criteria

### Milestone 1: Foundation & Architecture (Status: Completed)
- [x] Structured package layout (`app/`, `config/`, `assets/`, `workflows/`, `tests/`)
- [x] Pydantic Settings with YAML hierarchical configuration (`config/config.yaml`)
- [x] SQLite database schema with SQLAlchemy ORM models (WAL mode enabled)
- [x] Structured rotating logging system (`logs/dharmaflow.log`)
- [x] Environment diagnostics (`python -m app doctor` and `python -m app gpu`)
- [x] Secrets separation (`.env.example`, `.gitignore`)

### Milestone 2: Research & Verification Engine (Status: In Progress)
- [x] Trusted source registry (`app/research/sources.py`)
- [x] Strict Pydantic script and claim schemas (`app/content/schemas.py`)
- [ ] Claim extraction and verification service (`app/content/source_verifier.py`)
- [ ] Content planner with category distribution balancing (`app/content/planner.py`)
- [x] Fingerprint-based duplicate detection & originality audit (`app/content/originality.py`)
- [ ] Metadata generation for YouTube and Instagram (`app/content/metadata_generator.py`)

### Milestone 3: AI Generation & Video Pipeline (Status: Completed & Enhancing)
- [x] LLM provider interface (Local Ollama, OpenAI, Anthropic, Gemini, Mock)
- [x] Visual provider interface (Pillow Placeholder, ComfyUI API)
- [x] TTS provider interface (gTTS, EdgeTTS, Piper, Silent fallback)
- [x] FFmpeg vertical video renderer with Ken Burns pan/zoom and ASS Devanagari subtitles
- [x] Automated 10-point Quality Control engine (`app/quality/checker.py`)
- [ ] Provenance manifest generator for cryptographic asset tracking

### Milestone 4: Local Web Dashboard & API (Status: In Progress)
- [x] FastAPI REST API backend (`app/api/app.py`, endpoints for content, jobs, publishing, settings)
- [ ] Responsive single-page local dashboard frontend (`app/dashboard/static/index.html`, `app.js`, `style.css`)
- [ ] Human-in-the-loop approval and rejection workflows
- [ ] Media auditioning and video playback in browser

### Milestone 5: Publishing & Automation (Status: In Progress)
- [x] YouTube Data API v3 uploader with OAuth 2.0 and resumable upload
- [ ] Instagram Graph API publishing provider (`app/publishing/instagram.py`)
- [x] Daily scheduler engine with file lock and daily rate-limiting (`app/scheduler/daily.py`)
- [ ] Windows Task Scheduler automation scripts (`scripts/register_task.ps1`)

### Milestone 6: Analytics, Cost Tracking & Hardening (Status: In Progress)
- [ ] Compute time and token cost accounting engine (`app/core/cost_tracker.py`)
- [ ] Performance learning loop (`app/analytics/learning_loop.py`)
- [x] Unit test suite
- [ ] Integration and end-to-end smoke tests (`tests/e2e/test_offline_demo.py`)
- [ ] Complete operational documentation (`README.md`, `TROUBLESHOOTING.md`, `ARCHITECTURE.md`)
