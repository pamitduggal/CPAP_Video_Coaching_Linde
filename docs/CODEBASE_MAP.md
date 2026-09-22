# SleepCare CPAP Ecosystem: Codebase Map and Directory Guide

> DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France  
> Author: Pamit Duggal (Software and AI Engineering Intern)  
> Scope: File inventory and component responsibilities

---

## 1. High-level repository tree

```text
CPAP new/
├── CPAP_Raspberry_Pi/                # Edge computing node runtime (Raspberry Pi 5)
├── CPAP_Video_Server/                # Media delivery, virtual playlist assembly, and GenAI
├── CPAP_AI_Server/                   # 7-layer ML intelligence supervisor and dashboard
└── docs/                             # Technical documentation suite
    ├── images/                       # Architecture diagrams
    └── resources/                    # Clinical reference guides and scripts
```

---

## 2. Raspberry Pi edge service (`CPAP_Raspberry_Pi/`)

Located at `CPAP_Raspberry_Pi/`:

```text
CPAP_Raspberry_Pi/
├── README.md                 # Component quickstart and operational summary
├── app.py                    # FastAPI application, auth, CSV ingest, and timing
├── edge_detection.py         # 37-rule triage engine and date parser
├── load_library.py           # Catalog indexer and scenario selector
├── sync_catalog.py           # Sync utility pulling updates from Video VM
└── .env.example              # Environment variables template
```

### Script details

#### [`app.py`](../CPAP_Raspberry_Pi/app.py)
The primary entrypoint for the edge node.
- Initializes FastAPI with CORS and SlowAPI rate limiting.
- Handles `POST /ingest` for multipart CSV uploads from the mobile app.
- Handles `POST /timing/{event_id}` to calculate roundtrip playback latency.
- Manages background tasks that push Phase 1 and Phase 2 event traces to VM2.
- Serves patient polling endpoints (`GET /patient/{id}/coaching` and `POST /patient/{id}/clear`).

#### [`edge_detection.py`](../CPAP_Raspberry_Pi/edge_detection.py)
Clinical triage logic.
- `latest_row(df)`: Picks the newest therapy night based on `reference_date`, `created_at`, or physical position.
- `detect_event(csv_path_or_df)`: Evaluates all 37 clinical rules, sorts triggered events by clinical severity, suppresses redundant sensor alerts (Hexoskin over ProShirt), and returns the winning event.
- `WEARABLE_LOGIC`: Reference dictionary containing boolean threshold rules for wearable devices (Videos 28 to 37).

#### [`load_library.py`](../CPAP_Raspberry_Pi/load_library.py)
Startup indexing and scenario selection.
- `load_library(root)`: Parses all `metadata/video_*.json` files into an in-memory dictionary.
- `select_video(event, library)`: Implements scenario routing (Scenario 1 single clip, Scenario 2 dual clip, Scenario 3 generative prompt).

---

## 3. CPAP Video Server (`CPAP_Video_Server/`)

Located at `CPAP_Video_Server/`:

```text
CPAP_Video_Server/
├── .env.example                      # Template for ports, base URLs, and API tokens
├── README.md                         # Video server quickstart
├── video_vm_server.py                # FastAPI streaming service (:8080)
├── deduplication_engine.py           # In-memory prompt cache for Google Veo 3.1
├── assignment_ledger.py              # Atomic JSON ledger of patient assignments
├── build_video_metadata.py           # OpenCV metadata extraction and WebVTT cue builder
├── calculate_kpis.py                 # Live verification of stream availability
├── sync_remote_nodes.py              # Multi-node webhook broadcast engine
├── update_master_metadata.py         # Combines single JSON files into master catalog
├── start_server.bat                  # Windows batch launcher with socket clearing
│
├── dashboard/                        # Web UI assets
│   ├── index.html                    # Single-page console
│   ├── dashboard.css                 # Interface styles
│   └── dashboard.js                  # Video player, subtitle overlay, and SSE stream
│
├── existing_videos/                  # 37 curated 1080p MP4 coaching clips (1 to 37)
├── new_videos/                       # 2 AI-generated 1080p MP4 clips (38 and 39)
├── existing_subtitles/               # 74 WebVTT subtitle tracks (EN and FR)
├── new_subtitles/                    # 4 WebVTT subtitle tracks (EN and FR)
├── metadata/                         # Metadata records and catalog indexes
│   ├── assigned_video_history.json   # Local assignment history
│   ├── distributed_trigger_catalog.json # 39-item distributed trigger matrix
│   ├── generative_cache_index.json   # MD5 prompt cache
│   ├── master_video_metadata.json    # Consolidated video registry
│   └── video_01.json ... video_39.json # Per-clip metadata files
└── logs/                             # Log directory (.gitkeep present)
```

### Script details

#### [`video_vm_server.py`](../CPAP_Video_Server/video_vm_server.py)
Media streaming and dispatch service.
- `GET /videos/{filename}`: HTTP 206 byte-range streaming for MP4 video playback.
- `GET /subtitles/{filename}`: Delivers WebVTT subtitle files with zero-cache headers.
- `POST /api/orchestrate`: Dispatches Scenario 1 and 2 requests, checks the assignment ledger, and notifies VM2.
- `POST /api/vertex-generate`: Generates on-demand clips via Google Vertex AI after checking the deduplication cache.
- `GET /api/triggers/catalog`: Provides the canonical trigger matrix to remote nodes.
- `GET /api/logs/stream`: Streams live log lines to the web dashboard via Server-Sent Events (SSE).

#### [`deduplication_engine.py`](../CPAP_Video_Server/deduplication_engine.py)
Singleton cache that intercepts requests before invoking Google Veo 3.1:
- Level 1: Normalized MD5 prompt comparison (< 0.2 ms).
- Level 2: Clinical slug matching across video directories (< 0.5 ms).
- Level 3: Semantic comparison of subtitle transcripts and tags (< 1.0 ms).

#### [`assignment_ledger.py`](../CPAP_Video_Server/assignment_ledger.py)
Thread-safe ledger preventing duplicate video deliveries to the same patient:
- `is_assigned(patient_id, video_filename)`: Fast lookup.
- `record_assignment(...)`: Writes updates via temporary file swap to avoid write corruption.

---

## 4. CPAP AI Supervisor Server (`CPAP_AI_Server/`)

Located at `CPAP_AI_Server/`:

```text
CPAP_AI_Server/
├── api_data_loader.py                # CLI runner for cohort scoring
├── sitecustomize.py                  # Python hook redirecting CSV calls to REST endpoints
├── run_ai_server.bat                 # Windows launcher with port auto-clear
├── M4_FINAL_F2.ipynb                 # Reference notebook running Layers 0 through 6
├── distributed_trigger_catalog.json  # Cached 39-item trigger matrix
├── README.md                         # AI server quickstart
├── .env.example                      # Environment variables template
│
├── core/                             # Core modular package
│   ├── __init__.py                   # Package exports
│   ├── config.py                     # URLs, environment variables, job codes
│   ├── registry.py                   # Data containers for models and video metadata
│   ├── data_fetcher.py               # HTTP data fetcher with progress reporting
│   ├── preprocessor.py               # Feature normalizer and column synthesizer
│   ├── interceptor.py                # File virtualization hooks
│   ├── video_engine.py               # VideoAssignmentTracker and orchestration client
│   ├── pipeline.py                   # Subprocess notebook runner
│   ├── server.py                     # FastAPI application running on ports 8000 and 8001
│   └── dashboard_view.py             # Clinician surveillance dashboard
│
├── scripts/                          # Operational utilities
│   ├── clear_ports.py                # Pre-flight port scanner and process killer
│   ├── calculate_kpis.py             # Cohort metric benchmark engine
│   └── score_weekly_cohort.py        # Weekly cohort batch runner
│
├── tests/                            # Automated test scripts
│   ├── test_technical_briefing.py    # Tests 39 items, boolean rules, and fast path
│   ├── test_server_dashboard.py      # Tests HTML UI, SVG gauges, and endpoints
│   ├── verify_server_routes.py       # Route verification across REST endpoints
│   ├── test_playlist.py              # Tests Scenario 2 virtual playlist ordering
│   ├── test_tracker.py               # Tests tracker recovery across restarts
│   ├── test_triggers.py              # Tests 14 multimodal wearable anomaly triggers
│   └── test_full_system.py           # End-to-end integration test
│
├── data/                             # Data directory with .gitkeep (CSVs purged)
├── artifacts/                        # Model outputs with sanitized tracker template
└── reports/                          # Benchmark summaries (cpap_kpis_summary.json)
```

### Script details

#### [`core/server.py`](../CPAP_AI_Server/core/server.py)
Application entrypoint with dual-port management. Launches FastAPI on port 8000 for the dashboard and API, while starting a background daemon on port 8001 for catalog sync webhooks.

#### [`core/video_engine.py`](../CPAP_AI_Server/core/video_engine.py)
Connects ML predictions to video actions. `VideoAssignmentTracker` records patient assignments atomically to `artifacts/assigned_videos_tracker.json`.

#### [`scripts/clear_ports.py`](../CPAP_AI_Server/scripts/clear_ports.py)
Checks whether ports 8000 and 8001 are in use using `netstat -ano`, terminates the conflicting process using `taskkill /F`, and verifies that the port is open before Uvicorn starts.

---

Continue to [API.md](API.md) for the REST interface details.
