# MASTER EXECUTION PLAN: DHARMAFLOW ONE

## Architecture & Directory Layout
```text
dharmaflow-one/
├── package.json
├── electron/
│   ├── main.ts
│   └── preload.ts
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── store/
│   │   │   └── useAppStore.ts
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   └── types.ts
│   │   └── components/
│   │       ├── SetupWizard.tsx
│   │       ├── TopNav.tsx
│   │       ├── Step1TopicInput.tsx
│   │       ├── Step2ScriptReview.tsx
│   │       ├── Step3SceneStoryboard.tsx
│   │       └── Step4VideoPublish.tsx
│   └── e2e/
│       └── workflow.spec.ts
└── backend/
    ├── requirements.txt
    ├── main.py
    ├── config.py
    ├── db/
    │   ├── database.py
    │   └── models.py
    ├── schemas/
    │   └── api_schemas.py
    ├── core/
    │   ├── ws_manager.py
    │   ├── hardware.py
    │   ├── downloader.py
    │   └── vram_guard.py
    ├── providers/
    │   ├── base.py
    │   ├── mock_providers.py
    │   └── local_providers.py
    ├── services/
    │   ├── media_engine.py
    │   ├── pipeline.py
    │   └── youtube_service.py
    └── tests/
        ├── conftest.py
        ├── test_hardware_and_vram.py
        ├── test_av_sync_engine.py
        ├── test_pipeline_modes.py
        └── test_youtube_service.py
```

## Execution Phases
- **Phase 1: Foundation & Database Layer**
  - Create directory structure for `dharmaflow-one`.
  - Implement `backend/requirements.txt`, `backend/config.py`.
  - Implement `backend/db/database.py` (SQLAlchemy 2.0 async engine & session factory with SQLite).
  - Implement `backend/db/models.py` (exact models: `HardwareTier`, `ExecutionMode`, `ProjectStatus`, `ModelArtifact`, `YouTubeChannel`, `Project`, `Scene`).
  - Implement `backend/schemas/api_schemas.py` (Pydantic v2 schemas).

- **Phase 2: Core Hardware, VRAM Guard, Downloader & Media Engine**
  - Implement `backend/core/ws_manager.py`.
  - Implement `backend/core/hardware.py` (`detect_hardware_profile()`).
  - Implement `backend/core/vram_guard.py` (Singleton with acquire_model and unload_history).
  - Implement `backend/core/downloader.py` (Resumable HTTP Range download + SHA256).
  - Implement `backend/providers/base.py`, `backend/providers/mock_providers.py`, `backend/providers/local_providers.py`.
  - Implement `backend/services/media_engine.py` (`get_audio_duration_ms`, `mux_scene`, `concat_scenes`).
  - Implement & run test suites:
    - `backend/tests/conftest.py`
    - `backend/tests/test_hardware_and_vram.py`
    - `backend/tests/test_av_sync_engine.py`

- **Phase 3: Pipeline State Machine, YouTube Service & FastAPI Endpoints**
  - Implement `backend/services/pipeline.py` (Deterministic state machine: REVIEW vs TURBO modes).
  - Implement `backend/services/youtube_service.py` (OAuth 2.0 PKCE, multi-channel discovery, resumable upload).
  - Implement `backend/main.py` (FastAPI endpoints, CORS, WebSocket `/ws`, media static mounting).
  - Implement & run test suites:
    - `backend/tests/test_pipeline_modes.py`
    - `backend/tests/test_youtube_service.py`

- **Phase 4: Frontend & Electron Shell**
  - Initialize Electron and React + TypeScript + Vite + Tailwind setup.
  - Implement `electron/main.ts` and `electron/preload.ts`.
  - Implement `frontend/src/api/types.ts` and `frontend/src/api/client.ts`.
  - Implement `frontend/src/store/useAppStore.ts` (Zustand).
  - Implement components: `SetupWizard.tsx`, `TopNav.tsx`, `Step1TopicInput.tsx`, `Step2ScriptReview.tsx`, `Step3SceneStoryboard.tsx`, `Step4VideoPublish.tsx`.
  - Wire App.tsx and index.html.

- **Phase 5: Playwright E2E & Full Verification**
  - Implement `frontend/e2e/workflow.spec.ts`.
  - Run Playwright test suite and full backend test suite to achieve 100% green tests across all suites.
