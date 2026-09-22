# CPAP Just-in-Time Video Coaching — Video Server (VM4)

FastAPI enterprise media streaming and generative AI video orchestration engine.  
Developed in partnership between **DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon)** and **Linde HomeCare France**.

---

## 1. Architectural Mission: Media Streaming & GenAI Orchestration

The Video Server (VM4) hosts the entire clinical video library and executes high-speed media delivery:
- Serves **39 Full HD (1080p, 30fps) MP4 coaching videos** with HTTP 206 Partial Content byte-range seeking (< 5ms TTFB).
- Delivers **78 bilingual WebVTT subtitle tracks** (100% English & French parity).
- Implements **Scenario 1 (Single Clip)** and **Scenario 2 (Virtual Stitched Playlist Sequences)** with zero-re-encoding seamless client playback (`fade_1_5s`).
- Protects cloud APIs with an in-memory **3-Level Pre-Gen Deduplication Shield** (MD5 prompt hash, slug match, semantic similarity) reducing redundant Google Cloud Veo 3.1 calls to < 1ms reuse.
- Records patient prescriptions in an atomic, thread-safe `AssignmentLedger` and synchronizes with the Central Clinical Backend (VM2).
- Hosts the interactive Clinical Web Dashboard at `http://localhost:8080/`.

---

## 2. Directory Structure

```text
CPAP_Video_Server/
├── video_vm_server.py            # Primary FastAPI Uvicorn streaming server (:8080)
├── deduplication_engine.py       # 3-Level Pre-Gen Deduplication Shield (<1ms reuse)
├── assignment_ledger.py          # Atomic thread-safe persistent assignment ledger
├── build_video_metadata.py       # OpenCV metadata extractor & WebVTT compiler
├── calculate_kpis.py             # Live KPI benchmark engine & ASCII report builder
├── sync_remote_nodes.py          # Multi-node webhook broadcast engine
├── update_master_metadata.py     # Master registry aggregator
├── start_server.bat              # Universal Windows launcher with auto-recovery
├── dashboard/                    # Interactive Clinical Web Dashboard console
├── existing_videos/              # 37 Curated 1080p MP4 coaching videos (1–37)
├── new_videos/                   # 2 Generative AI 1080p MP4 videos (38–39)
├── existing_subtitles/           # 74 Bilingual WebVTT subtitle files (EN & FR)
├── new_subtitles/                # 4 Bilingual WebVTT subtitle files (EN & FR)
├── metadata/                     # 39 JSON metadata records + master catalogs
└── .env.example                  # Environment variables template
```

---

## 3. Quick Start

### Step 1: Environment Setup
```bash
cp .env.example .env
# Edit .env and supply SERVER_API_KEY, VIDEO_SERVER_KEY, BACKEND_API_KEY, GOOGLE_VERTEX_API_KEY
```

### Step 2: Launch Service
```powershell
.\start_server.bat
```
*The service will launch on port 8080. Access the Clinical Operations Console at `http://localhost:8080/`.*

Verify service status:
```bash
curl -s http://localhost:8080/health
```

---

## 4. Single Source of Truth Documentation

To prevent duplicate instructions, all exhaustive technical specifications have been consolidated into the centralized `docs/` manual:

| Topic | Reference Document |
| :--- | :--- |
| **System Architecture & Data Flows** | [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) |
| **Component Breakdown & Streaming Engine** | [docs/COMPONENTS.md](../docs/COMPONENTS.md) |
| **Complete Codebase Directory Map** | [docs/CODEBASE_MAP.md](../docs/CODEBASE_MAP.md) |
| **REST API Contracts & Orchestration Schemas** | [docs/API.md](../docs/API.md) |
| **Route Catalog & Streaming Endpoints** | [docs/ROUTES.md](../docs/ROUTES.md) |
| **State Persistence, Ledgers & Prompt Caching** | [docs/STATE.md](../docs/STATE.md) |
| **Production Deployment & Windows Autostart** | [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) |
| **Adding New Videos, Profiling & Veo Prompts** | [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) |
| **Master Handover & Intern Roadmap** | [docs/HANDOVER_REPORT.md](../docs/HANDOVER_REPORT.md) |
| **Video Production Ideas & Prompts (PDF)** | [docs/resources/CPAP_Wearables_Video_Ideas_and_Google_Veo_Prompts.pdf](../docs/resources/CPAP_Wearables_Video_Ideas_and_Google_Veo_Prompts.pdf) |
