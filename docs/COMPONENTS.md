# SleepCare CPAP Ecosystem: Subsystems and Components Technical Guide

> DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France  
> Author: Pamit Duggal (Software and AI Engineering Intern)  
> Components: Raspberry Pi Edge, Video Server (VM4), AI Supervisor Server (VM3), Central Backend (VM2)

---

## 1. Raspberry Pi edge node (`CPAP_Raspberry_Pi`)

### Role and runtime environment
The Raspberry Pi 5 runs locally in the patient's home environment, reachable via the local area network or a Tailscale tunnel. It handles the initial triage step:
- It processes nightly CSV uploads from the mobile app in under 6 milliseconds.
- It tests data against 37 clinical rules and decides which coaching clip to request from the Video VM.
- It isolates patient CSV files at the edge so raw sensor rows do not need to be sent across the internet.

Specifications:
- Operating System: Debian 12 (Bookworm), aarch64
- Runtime: Python 3.11/3.12 virtual environment
- Web Framework: FastAPI on Uvicorn (`app:app --host 0.0.0.0 --port 8000`)
- Process Management: Launched via virtualenv or systemd unit

### Key scripts

| Script | Purpose |
| :--- | :--- |
| `app.py` | FastAPI application. Manages client authentication, SlowAPI rate limiting, multipart CSV uploads, RTT timing callbacks, and background telemetry delivery. |
| `edge_detection.py` | Rule engine. Parses the newest night from incoming CSV files, tests the 37 clinical rules, and returns the highest-priority event. |
| `load_library.py` | Reads metadata JSON files on startup, builds an in-memory video lookup table, and handles scenario routing (single clip, virtual sequence, or generative prompt). |
| `sync_catalog.py` | Pulls trigger definitions from the Video VM (`GET /api/triggers/catalog`) and updates local metadata files. |

### Nightly record resolution (`latest_row`)
Mobile apps often upload files containing weeks of therapy history. The triage engine only cares about the most recent session. It finds the latest record using this priority order:
1. `reference_date` column (`YYYY-MM-DD`)
2. `created_at` or `date` columns
3. The last physical row in the CSV file

Older rows remain available for context but do not trigger fresh coaching interventions.

### The 37 clinical rules

The rules fall into two distinct groups:

1. **Standard CPAP metrics (Videos 1 to 27)**:
   - Severe Apnea (residual AHI >= 30) triggers Video 15 (`critical`).
   - High AHI with low usage (AHI >= 15 and use < 3h) triggers Video 13 (`critical`).
   - Major mask leak (>= 40 L/min) triggers Video 14 (`high`).
   - Moderate mask leak (>= 30 L/min) triggers Video 2 or Video 8 depending on usage hours.
   - Low-level mask leak (>= 24 L/min) triggers Video 1 (`medium`).
   - Desaturations on Withings ScanWatch or Masimo Rad-G trigger Videos 16 and 22 (`critical`).
   - Blood pressure jumps and cardiac arrhythmias trigger Videos 18, 19, and 20 (`critical`/`high`).

2. **Multimodal wearable sensors (Videos 28 to 37)**:
   - Video 28: Hexoskin ECG quality drop (< 40 or dropout >= 30%)
   - Video 29: Hexoskin breathing asymmetry (> 25 with high noise)
   - Video 30: Hexoskin disconnected or recording stopped
   - Video 31: MightySat low perfusion index (< 0.5 or low SpO2 confidence)
   - Video 32: MightySat optical blockage or irregular pulse waveform
   - Video 33: MightySat signal indicator < 30 under bright ambient light
   - Video 34: SomnoArt PPG contact issues or baseline drift
   - Video 35: SomnoArt calibration failure or excessive head movement
   - Video 36: SomnoArt optical lens transmission < 60% (cleaning needed)
   - Video 37: Tubing drag causing mask dislodgement

Sensor override rule: Hexoskin takes precedence over ProShirt. If Video 28 triggers, ProShirt Video 25 is suppressed. If Video 29 triggers, ProShirt Video 24 is suppressed. They never fire at the same time.

### Telemetry logging
When `POST /ingest` finishes, the Pi immediately starts a background task sending Phase 1 timestamps to `POST http://159.84.143.151:80/api/telemetry/event-trace`. When the phone player buffers the video, it reports measured latency to `POST /timing/{id}`, and Phase 2 updates the record with real transit timing (`transit_source = "measured_rtt"`).

---

## 2. CPAP Video Server (VM4)

### Role and runtime environment
VM4 hosts media streaming, virtual playlist concatenation, and generative AI integration. It stores 39 Full HD MP4 files and 78 bilingual WebVTT subtitle tracks:
- Operating System: Windows Server 2022 Datacenter
- Runtime: Python 3.12 64-bit
- Service: FastAPI running on port 8080 via Uvicorn
- Startup script: `start_server.bat` (clears port conflicts and launches Uvicorn)

### Core operational scripts

```text
CPAP_Video_Server/
├── video_vm_server.py          # FastAPI streaming service and route handlers
├── deduplication_engine.py     # 3-level prompt cache for generative video
├── assignment_ledger.py        # Persistent JSON ledger tracking patient history
├── build_video_metadata.py     # Profiles MP4 files and compiles WebVTT transcripts
├── sync_remote_nodes.py        # Broadcasts catalog changes to AI and Edge nodes
├── calculate_kpis.py           # Verification script checking stream availability
├── update_master_metadata.py   # Merges individual video JSON files into master index
└── start_server.bat            # Windows startup script with auto-recovery
```

### HTTP 206 byte-range streaming
To let mobile apps seek through videos without downloading entire files first, `video_vm_server.py` parses incoming `Range: bytes=start-end` request headers and streams slices using HTTP 206 Partial Content. In our local network tests, Time-to-First-Byte consistently clocked between 2.1 and 2.8 ms.

### Generative prompt deduplication
Rendering a custom video with Google Veo 3.1 takes 15 to 30 seconds and costs GPU credits. In `deduplication_engine.py`, we intercept requests to `POST /api/vertex-generate` through three sequential checks:
1. **Exact MD5 hash**: Hashes the incoming prompt and looks for it in `generative_cache_index.json` (< 0.2 ms).
2. **Slug matching**: Compares clinical slug tokens against existing MP4 file names (< 0.5 ms).
3. **Semantic keyword matching**: Checks clinical tags and subtitle lines against existing metadata records (< 1.0 ms).

If any check finds a match, the server returns the existing clip immediately, skipping the Vertex AI call.

### Subtitle overlay handling
Earlier in development, native HTML5 text tracks (`video::cue`) were colliding with our custom clinical player interface, producing doubled subtitle text on screen. We fixed this by setting all native track modes to `hidden` in JavaScript, clearing the DOM element cleanly between playlist transitions, and rendering subtitle text exclusively through a single synchronized container (`.video-subtitle-overlay`). Subtitle endpoints also send strict zero-cache HTTP headers so edits appear immediately.

---

## 3. AI Supervisor Server (VM3)

### Role and runtime environment
VM3 runs continuous machine learning surveillance over 41,117 patient histories (over 15.5 million individual therapy records). It identifies patients whose usage patterns show early warning signs of treatment abandonment and calculates the best intervention channel for each individual.

- Host and ports:
  - Port 8000: Web surveillance dashboard and REST API (`http://localhost:8000/dashboard`).
  - Port 8001: Background webhook listener for catalog sync (`POST /api/triggers/sync`).
- Launcher: `run_ai_server.bat` (calls `scripts/clear_ports.py` to prevent zombie socket bindings).

### The 7-layer machine learning pipeline

The pipeline runs inside `M4_FINAL_F2.ipynb` and is automated via `core/pipeline.py`:

```text
+---------------------------------------------------------------------------+
| Layer 0: Online statistical process control (CUSUM and EWMA)              |
| Detects sudden drops in nightly hours (lambda=0.2, h=4.0) or leak surges  |
+-------------------------------------+-------------------------------------+
                                      |
                                      v
+---------------------------------------------------------------------------+
| Layer 1: Phenotype clustering (K-Means and Gaussian Mixture Models)       |
| Groups patients into 4 behavioral groups: regular, erratic, quitter, leak|
+-------------------------------------+-------------------------------------+
                                      |
                                      v
+---------------------------------------------------------------------------+
| Layer 2: Multimodal state transitions                                     |
| Markov transition matrix tracking physiological stability vs degradation  |
+-------------------------------------+-------------------------------------+
                                      |
                                      v
+---------------------------------------------------------------------------+
| Layer 3: Supervised dropout risk classification                           |
| Ensemble of LightGBM, CatBoost, and XGBoost predicting 30-day risk (z_risk)|
+-------------------------------------+-------------------------------------+
                                      |
                                      v
+---------------------------------------------------------------------------+
| Layer 4: Cox proportional hazards survival modeling                       |
| Predicts expected time to therapy abandonment                             |
+-------------------------------------+-------------------------------------+
                                      |
                                      v
+---------------------------------------------------------------------------+
| Layer 5: Causal uplift modeling                                           |
| Estimates whether a patient responds better to video, phone, or a visit   |
+-------------------------------------+-------------------------------------+
                                      |
                                      v
+---------------------------------------------------------------------------+
| Layer 6: Dynamic action dispatching                                       |
| Generates patient action plans and schedules targeted coaching clips      |
+---------------------------------------------------------------------------+
```

### Cohort benchmarks (41,117 patients)
- Compliance rate (>= 4 hours/night over 70% of days): 90.12% (37,054 patients)
- Average nightly CPAP usage: 5.81 hours (standard deviation: 1.94 hours)
- Average residual AHI: 3.82 events per hour
- Active statistical alarms: 5.33% of the cohort (2,192 patients)
- Mean risk score ($z\_risk$): 0.2184 (with 5.8% scored as high risk above 0.70)

---

## 4. Central Clinical Backend (VM2)

### Role and database
VM2 is the central clinical server maintained by our medical team, running Ubuntu Linux at `http://159.84.143.151:80`. It runs PostgreSQL (`DB_Clinical`) and provides the clinical web portal used by sleep physicians and technicians.

### Main integration endpoints
1. `POST /api/videos/{patient_id}/assign`: Called by Video VM4 with `X-Video-Server-Key` to log video prescriptions.
2. `POST /api/telemetry/event-trace`: Called by Pi Edge and Video VM4 with `X-API-Key` to log latency timestamps ($t_0$ to $t_7$) and RTT.
3. `POST /api/data/predictions`: Called by AI Server VM3 with `X-ML-Key` to write risk scores and recommended intervention plans.

Continue to [CODEBASE_MAP.md](CODEBASE_MAP.md) for a file-by-file inventory.
