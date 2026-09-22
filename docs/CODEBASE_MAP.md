# SleepCare CPAP Ecosystem — Codebase Map & Directory Guide

> **DISP Laboratory (Lyon) & Linde HomeCare France**  
> *Author: Pamit Duggal (Software & AI Engineering Intern)*  
> *Scope: File-by-File Repository Atlas Across All Active Servers*

---

## 1. High-Level Directory Tree

```text
c:\Users\pduggal\Downloads\CPAP new\
├── CPAP_Raspberry_Pi\                # Edge computing node runtime (Raspberry Pi 5)
├── CPAP_Video_Server\                # Media streaming, sequence assembly & GenAI node (VM4)
├── CPAP_AI_Server\                   # 7-layer ML intelligence supervisor & dashboard (VM3)
└── docs\                             # Unified technical handover documentation suite
    ├── images\                       # Architecture schematics
    └── resources\                    # Clinical guides and reference materials
```

---

## 2. Component 1: Raspberry Pi Edge Service (`CPAP_Raspberry_Pi/`)

Located at `c:\Users\pduggal\Downloads\CPAP new\CPAP_Raspberry_Pi\`:

```text
CPAP_Raspberry_Pi/
├── README.md                 # Edge service quickstart & architectural overview
├── app.py                    # Primary FastAPI service & endpoint router (1,100 lines, 50 KB)
├── edge_detection.py         # 37-rule clinical triage engine & date extractor (530 lines, 22 KB)
├── load_library.py           # Video library indexer & Scenario 1/2/3 selector (290 lines, 11 KB)
├── sync_catalog.py           # Catalog synchronization utility with Video VM
└── .env.example              # Environment variables template
```

### Detailed File Catalog

#### 1. [`app.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Raspberry_Pi/app.py) (50,192 bytes)
- **Role**: Core HTTP service entry point for the Raspberry Pi.
- **Key Symbols**:
  - `app = FastAPI(...)`: Service instance configured with CORS middleware and SlowAPI rate limiter.
  - `ingest_telemetry(...)` (`POST /ingest`): Multipart CSV ingestion endpoint.
  - `report_timing(...)` (`POST /timing/{event_id}`): RTT latency feedback endpoint.
  - `push_event_telemetry(...)`: Background daemon task pushing Phase 1 and Phase 2 traces to VM2.
  - `get_patient_coaching(...)` (`GET /patient/{id}/coaching`): Dashboard polling endpoint.
  - `clear_patient_coaching(...)` (`POST /patient/{id}/clear`): Marks coaching watched.
- **Dependencies**: `fastapi`, `uvicorn`, `requests`, `slowapi`, `pandas`, `edge_detection`, `load_library`.

#### 2. [`edge_detection.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Raspberry_Pi/edge_detection.py) (21,987 bytes)
- **Role**: Deterministic anomaly detection engine.
- **Key Symbols**:
  - `latest_row(df)`: Selects newest record based on `reference_date`, `created_at`, or `date`.
  - `detect_event(csv_path_or_df)`: Evaluates all 37 rules, ranks events by severity, applies sensor suppressions (Hexoskin over ProShirt), and returns top event.
  - `WEARABLE_LOGIC`: Canonical dictionary defining boolean AND/OR rules for videos 28–37.
- **Dependencies**: `pandas`, `numpy`.

#### 3. [`load_library.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Raspberry_Pi/load_library.py) (10,904 bytes)
- **Role**: Startup video registry indexer and scenario selector.
- **Key Symbols**:
  - `load_library(root)`: Globs and parses all `metadata/video_*.json` files into an in-memory dictionary.
  - `select_video(event, library)`: Implements scenario routing (Scenario 1 single clip, Scenario 2 virtual stitched dual clip, Scenario 3 GenAI request).
- **Dependencies**: `json`, `pathlib`, `glob`.

---

## 3. Component 2: CPAP Video Server (`CPAP_Video_Server/`)

Located at `c:\Users\pduggal\Downloads\CPAP new\CPAP_Video_Server\`:

```text
CPAP_Video_Server/
├── .env.example                      # Template for network binding, base URLs and secret keys
├── README.md                         # Video Server quickstart & architectural overview
├── video_vm_server.py                # Core FastAPI Uvicorn streaming server (77.5 KB)
├── deduplication_engine.py           # 3-Level Pre-Gen Deduplication Shield (15.3 KB)
├── assignment_ledger.py              # Persistent atomic assignment history ledger (8.8 KB)
├── build_video_metadata.py           # OpenCV metadata extractor & VTT compiler (31.0 KB)
├── calculate_kpis.py                 # Live KPI benchmark engine & ASCII report builder (23.1 KB)
├── sync_remote_nodes.py              # Multi-node webhook broadcast engine (12.2 KB)
├── update_master_metadata.py         # Master registry aggregator (4.9 KB)
├── start_server.bat                  # Universal Windows launcher with auto-recovery (4.0 KB)
│
├── dashboard/                        # Interactive Clinical Web Dashboard
│   ├── index.html                    # Single-page operations console
│   ├── dashboard.css                 # Modern light clinical UI design tokens
│   └── dashboard.js                  # Subtitle DOM overlay & live SSE client
│
├── existing_videos/                  # 37 Curated 1080p MP4 videos (Clips 1 to 37)
├── new_videos/                       # 2 Generative AI 1080p MP4 videos (Clips 38 & 39)
├── existing_subtitles/               # 74 Bilingual WebVTT subtitle files (37 EN + 37 FR)
├── new_subtitles/                    # 4 Bilingual WebVTT subtitle files (2 EN + 2 FR)
├── metadata/                         # 39 JSON metadata records + Master registries
│   ├── assigned_video_history.json   # Persistent assignment ledger
│   ├── distributed_trigger_catalog.json # 39-item distributed trigger matrix
│   ├── generative_cache_index.json   # Level 1 MD5 prompt cache
│   ├── master_video_metadata.json    # Master video registry (39 records)
│   └── video_01.json ... video_39.json # Individual clip records
└── logs/                             # Server operational logs directory
```

### Detailed File Catalog

#### 1. [`video_vm_server.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Video_Server/video_vm_server.py) (77,508 bytes)
- **Role**: Primary media delivery and orchestration service.
- **Key Endpoints**:
  - `GET /videos/{filename}`: HTTP 206 byte-range streaming engine.
  - `GET /subtitles/{filename}`: Zero-cache WebVTT subtitle streamer.
  - `POST /api/orchestrate`: Scenario 1 & 2 dispatcher with assignment ledger check and VM2 push.
  - `POST /api/vertex-generate`: Scenario 3 generative AI synthesis pipeline with 3-Level Deduplication Shield.
  - `GET /api/triggers/catalog`: Canonical distributed trigger catalog provider.
  - `GET /api/logs/stream`: Real-time Server-Sent Events (SSE) log stream for the dashboard.
- **Dependencies**: `fastapi`, `uvicorn`, `requests`, `pydantic`, `deduplication_engine`, `assignment_ledger`.

#### 2. [`deduplication_engine.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Video_Server/deduplication_engine.py) (15,341 bytes)
- **Role**: In-memory singleton protecting Google Cloud Veo 3.1 from redundant synthesis.
- **Key Classes**:
  - `PreGenDeduplicationEngine`: Evaluates Level 1 (MD5), Level 2 (Slug), and Level 3 (Semantic) matches.
  - `get_deduplication_engine()`: Singleton factory checking `st_mtime` to eliminate disk I/O on unchanged files.

#### 3. [`assignment_ledger.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Video_Server/assignment_ledger.py) (8,841 bytes)
- **Role**: Thread-safe persistent ledger tracking patient-to-video assignments.
- **Key Methods**:
  - `is_assigned(patient_id, video_filename)`: $O(1)$ duplicate check.
  - `record_assignment(...)`: Writes assignment using `.tmp` atomic file swap.

#### 4. [`build_video_metadata.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Video_Server/build_video_metadata.py) (31,023 bytes)
- **Role**: Asset profiler. Uses OpenCV `cv2.VideoCapture` to extract video duration, frame rates, and resolution, and parses WebVTT narration transcripts.

---

## 4. Component 3: CPAP AI Supervisor Server (`CPAP_AI_Server/`)

Located at `c:\Users\pduggal\Downloads\CPAP new\CPAP_AI_Server\`:

```text
CPAP_AI_Server/
├── api_data_loader.py                # Backwards-compatible CLI runner & entrypoint (5.5 KB)
├── sitecustomize.py                  # Python runtime hook injecting smart_read_csv (180 B)
├── run_ai_server.bat                 # Universal batch launcher with port auto-clear (4.4 KB)
├── M4_FINAL_F2.ipynb                 # Authoritative 7-layer ML intelligence pipeline (264 KB)
├── distributed_trigger_catalog.json  # Cached 39-item distributed trigger matrix (120 KB)
├── README.md                         # AI Server quickstart & architectural overview
├── .env.example                      # Environment variables template
│
├── core/                             # Modular AI Supervisor package
│   ├── __init__.py                   # Package exports
│   ├── config.py                     # Environment constants, URLs, 73 JobTypeCodes
│   ├── registry.py                   # 39 Clinical videos, ML models, state containers
│   ├── data_fetcher.py               # Streaming HTTP data fetcher with ASCII progress
│   ├── preprocessor.py               # Schema normalizer & missing feature synthesizer
│   ├── interceptor.py                # smart_read_csv & runtime compatibility patches
│   ├── video_engine.py               # Decision trees, VideoAssignmentTracker, dispatchers
│   ├── pipeline.py                   # Notebook subprocess runner & prediction pusher
│   ├── server.py                     # FastAPI server, dual-port listener (:8000/:8001)
│   └── dashboard_view.py             # Single-page HTML dashboard with SVG gauges
│
├── scripts/                          # Operational utilities
│   ├── clear_ports.py                # Pre-flight TCP port scanner & auto-cleanup (:8000/:8001)
│   ├── calculate_kpis.py             # Cohort clinical KPI benchmark engine
│   └── score_weekly_cohort.py        # Weekly cohort scoring dispatcher
│
├── tests/                            # Consolidated automated test suite
│   ├── test_technical_briefing.py    # 39 Items, boolean logic & <1ms fast path
│   ├── test_server_dashboard.py      # HTML dashboard, SVG gauges & telemetry
│   ├── verify_server_routes.py       # REST endpoint route verification
│   ├── test_playlist.py              # Scenario 2 virtual stitched sequencing
│   ├── test_tracker.py               # Persistent deduplication tracker recovery
│   ├── test_triggers.py              # 14 Multimodal wearable anomaly triggers
│   └── test_full_system.py           # End-to-end integration test
│
├── data/                             # Data directory with .gitkeep (sensitive CSVs purged)
├── artifacts/                        # Model artifacts directory (.gitkeep, sanitized tracker template)
│   └── assigned_videos_tracker.json  # Sanitized empty template schema for video tracking
└── reports/                          # Aggregate KPI benchmarks
    └── cpap_kpis_summary.json        # Machine-readable JSON KPI report
```

### Detailed File Catalog

#### 1. [`core/server.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/core/server.py)
- **Role**: Primary application server lifecycle (`lifespan`).
- **Dual Port Architecture**:
  - Initializes FastAPI on Port `8000` (Dashboard, REST API).
  - Spawns background daemon thread hosting an independent Uvicorn server on Port `8001` dedicated to receiving `POST /api/triggers/sync`.

#### 2. [`core/video_engine.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/core/video_engine.py)
- **Role**: Bridge between AI predictions and Video VM.
- **Key Symbols**:
  - `VideoAssignmentTracker`: Thread-safe singleton backing assignments to `artifacts/assigned_videos_tracker.json`.
  - `VideoOrchestrationClient`: Dispatches Scenario 1 single clip and Scenario 2 multi-clip playlists to Video VM4.

#### 3. [`core/interceptor.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/core/interceptor.py)
- **Role**: Runtime virtualization layer. Intercepts `pd.read_csv` via `sitecustomize.py` to stream from central backend REST APIs when available, transparently falling back to local `data/*.csv`. Redirects `to_csv` writes to `artifacts/`.

#### 4. [`scripts/clear_ports.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/scripts/clear_ports.py)
- **Role**: Pre-flight socket inspection. Probes ports `8000` and `8001` with `netstat -ano`, forcefully terminates conflicting PIDs via `taskkill /F`, and verifies socket binding before the server starts.

---

*Proceed to [API.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/API.md) for the complete REST API specification.*
