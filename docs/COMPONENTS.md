# SleepCare CPAP Ecosystem — Subsystems & Components Deep Dive

> **DISP Laboratory (Lyon) & Linde HomeCare France**  
> *Author: Pamit Duggal (Software & AI Engineering Intern)*  
> *Target Components: Raspberry Pi Edge, Video Server (VM4), AI Supervisor Server (VM3), Central Backend (VM2)*

---

## Component 1: Raspberry Pi 5 Edge Node (`CPAP_Raspberry_Pi`)

### 1.1 Architectural Role & Runtime
The Raspberry Pi 5 edge node is positioned inside the patient's local area network (or bridged via cellular/Tailscale). Its mission is **"Detect, Decide, and Forward"**. It isolates high-frequency raw CSV telemetry at the periphery, executes deterministic anomaly triage in under 6 milliseconds, and forwards only the chosen coaching video payload to the Video VM and latency KPIs to the central clinical database.

- **Operating System**: Debian GNU/Linux 12 (Bookworm) / aarch64
- **Runtime Environment**: Python 3.11/3.12 Virtual Environment (`.venv`)
- **Web Framework**: FastAPI running on Uvicorn (`app:app --host 0.0.0.0 --port 8000`)
- **Process Supervision**: Manually launched or supervised via tmux/systemd
- **Network Ingress**: Tailscale Funnel (`tailscale funnel 8000`) or local WiFi/Ethernet

### 1.2 Internal Module Breakdown

| File | Lines | Purpose & Internal Logic |
| :--- | :---: | :--- |
| [`app.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Raspberry_Pi/app.py) | ~1,100 | Primary HTTP service. Manages authentication, SlowAPI rate limiting, multipart CSV ingest, roundtrip timing calculation, Video VM forwarding, and background telemetry push. |
| [`edge_detection.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Raspberry_Pi/edge_detection.py) | ~530 | Clinical anomaly triage engine. Parses raw CSVs, extracts the newest night, evaluates 37 deterministic rules, and returns the top event with full event context. |
| [`load_library.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Raspberry_Pi/load_library.py) | ~290 | Startup video registry indexer. Loads `metadata/*.json` (37 files), parses subtitles and composability links, and implements `select_video()` across Scenarios 1, 2, and 3. |
| [`sync_catalog.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Raspberry_Pi/sync_catalog.py) | ~250 | Catalog synchronization tool. Queries Video VM (`GET /api/triggers/catalog`), verifies boolean AND/OR rules, and generates `metadata/video_28..37.json`. |

### 1.3 Telemetry Ingestion & Date Resolution (`latest_row()`)
Patient mobile apps upload longitudinal CSVs containing historical therapy rows. The Pi extracts **only the most recent night** using hierarchical date resolution:
1. Column `reference_date` (format: `YYYY-MM-DD`)
2. Fallback: `created_at` or `date`
3. Fallback: Final physical row in the CSV
Older rows are retained as local context and never trigger interventions.

### 1.4 The 37 Clinical Rules & Wearable Trigger Matrix
The Pi evaluates events across two primary tiers:
- **Videos 1–27 (CPAP & Existing Biomarkers)**:
  - Severe Apnea (AHI $\ge 30$) $\to$ Video 15 (`critical`)
  - Biomarker changes with low usage (AHI $\ge 15 \land \text{Use} < 3\text{h}$) $\to$ Video 13 (`critical`)
  - Massive Leak ($\ge 40\text{ L/min}$) $\to$ Video 14 (`high`)
  - Mask leak ($\ge 30\text{ L/min}$) $\to$ Video 2 or Video 8 depending on usage hours
  - Mask leak ($\ge 24\text{ L/min}$) $\to$ Video 1 (`medium`)
  - Low oxygen desaturations on ScanWatch / Rad-G $\to$ Videos 16, 22 (`critical`)
  - Nocturnal arrhythmias & blood pressure spikes $\to$ Videos 18, 19, 20 (`critical`/`high`)
- **Videos 28–37 (Multimodal Wearable Set-up & Care)**:
  - **Video 28** (Hexoskin ECG Quality $< 40 \lor \text{Dropout} \ge 30$)
  - **Video 29** (Hexoskin Thorax/Abdomen Async $> 25 \land \text{Noise} == \text{High}$)
  - **Video 30** (Hexoskin Status $== \text{Disconnected} \lor \text{Recording} == \text{False}$)
  - **Video 31** (MightySat PI $< 0.5 \lor \text{SpO2 Confidence} < 50$)
  - **Video 32** (MightySat Optical Blockage $\lor$ Erratic Pulse Waveform)
  - **Video 33** (MightySat SIQ $< 30 \land \text{Ambient Light} == \text{High}$)
  - **Video 34** (SomnoArt PPG Contact $== \text{Poor} \lor \text{Drift} == \text{High}$)
  - **Video 35** (SomnoArt Calibration Failed $\lor$ Motion Detected)
  - **Video 36** (SomnoArt Lens Transmission $< 60 \lor \text{Maintenance Due}$)
  - **Video 37** (CPAP Tubing Conflict: Mask Dislodges $\ge 2 \land \text{Motion} == \text{High}$)

> [!IMPORTANT]
> **Sensor Suppression Rule**: Hexoskin supersedes ProShirt. When Video 28 fires, ProShirt Video 25 is suppressed. When Video 29 fires, ProShirt Video 24 is suppressed. They never play simultaneously.

### 1.5 Latency Metric Push to Backend
Upon completing `/ingest`, the Pi spawns an asynchronous background task posting Phase 1 metadata to `POST http://159.84.143.151:80/api/telemetry/event-trace`. When the phone reports measured RTT via `/timing/{id}`, Phase 2 writes true transit time and updates `transit_source = "measured_rtt"`.

---

## Component 2: CPAP Video Server (`CPAP_Video_Server` / VM4)

### 2.1 Architectural Role & Runtime
VM4 acts as the high-throughput video delivery hub, dynamic sequence assembler, and generative AI synthesis host. It houses **39 Full HD (1080p) videos** and **78 WebVTT bilingual subtitle files**, exposing sub-5ms byte-range seeking and multi-level deduplication shields.

- **Operating System**: Windows Server 2022 Datacenter
- **Runtime Environment**: Python 3.12 64-bit (`C:\Program Files\Python312\`)
- **Web Framework**: FastAPI running on Uvicorn (`video_vm_server.py`, port `8080`)
- **Process Supervisor**: [`start_server.bat`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Video_Server/start_server.bat) with PowerShell port cleanup and socket auto-recovery

### 2.2 Clean Workspace Structure (10 Core Operational Files)

```text
c:\CPAP_Video_Server\
├── video_vm_server.py          # Core FastAPI ASGI service & streaming engine
├── deduplication_engine.py     # Modular 3-Level Pre-Gen Deduplication Shield
├── assignment_ledger.py        # Persistent JSON assignment ledger & deduplication
├── build_video_metadata.py     # CV2 video metadata extraction & WebVTT compiler
├── sync_remote_nodes.py        # Multi-node webhook broadcast engine
├── calculate_kpis.py           # Real-time KPI benchmark generator
├── update_master_metadata.py   # Master metadata compiler
├── start_server.bat            # Universal Windows launcher with auto-port cleanup
├── .env                        # Network bindings and security credentials
└── README.md                   # Complete architectural manual
```

### 2.3 HTTP 206 Partial Content Streaming Engine
To support instant random seeking and seamless playback on mobile networks, `video_vm_server.py` implements an optimized byte-range streamer:
- Inspects client `Range: bytes=start-end` headers.
- Emits `HTTP 206 Partial Content` with `Content-Range: bytes start-end/total_bytes`.
- Delivers an average Time-to-First-Byte (TTFB) of **2.1 to 2.8 milliseconds**.

### 2.4 Modular 3-Level Pre-Generation Deduplication Shield
Synthesizing 1080p medical coaching videos using Google Cloud Veo 3.1 is resource-intensive and incurs financial cost. Implemented in [`deduplication_engine.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Video_Server/deduplication_engine.py), the shield intercepts calls to `POST /api/vertex-generate`:

```
 Incoming Generation Request
             │
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Level 1: Exact MD5 Hash Lookup (< 0.2ms)              │
 │ MD5(normalized_prompt) in generative_cache_index.json  │
 └───────────────────────────┬────────────────────────────┘
             │ Miss
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Level 2: Dual Directory Slug Match (< 0.5ms)           │
 │ Compares slug tokens against existing/ and new/ files  │
 └───────────────────────────┬────────────────────────────┘
             │ Miss
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Level 3: Deep Metadata Semantic Match (< 1.0ms)        │
 │ Inspects tags, clinical tokens, narration transcripts   │
 └───────────────────────────┬────────────────────────────┘
             │ Miss
             ▼
 Google Veo 3.1 Cloud Synthesis Invoked (10s 1080p Video)
```

### 2.5 Single DOM Overlay Subtitle Engine
To fix dual-rendering bugs where native browser text tracks (`video::cue`) clash with the custom clinical HUD, the Video Server enforces:
1. Native tracks set to `track.mode = 'hidden'`.
2. Clean DOM destruction on clip switch: `parent.replaceChild(newVideo, oldVideo)` eliminates zombie cues.
3. Millisecond-synchronized custom DOM overlay (`.video-subtitle-overlay`).
4. Strict zero-cache headers on all `/subtitles/*` routes.

---

## Component 3: CPAP AI Supervisor Server (`CPAP_AI_Server` / VM3)

### 3.1 Architectural Role & Runtime
VM3 serves as the 24/7 continuous intelligence supervisor. It ingests longitudinal therapy datasets (15.5M+ rows), monitors online biomarker drift, classifies patient non-adherence risk, predicts survival dropout times, and prescribes causal interventions.

- **Host & Ports**: Dual-port runtime:
  - **Port 8000**: Primary REST API & interactive clinical web dashboard (`http://localhost:8000/dashboard`).
  - **Port 8001**: Companion webhook receiver for automated trigger synchronization (`POST /api/triggers/sync`).
- **Launcher**: [`run_ai_server.bat`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/run_ai_server.bat) with pre-flight port clearing via [`scripts/clear_ports.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/scripts/clear_ports.py).

### 3.2 The 7-Layer Machine Learning Pipeline (Layers 0–6)
Executed inside [`M4_FINAL_F2.ipynb`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/M4_FINAL_F2.ipynb) via [`core/pipeline.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/core/pipeline.py):

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Layer 0: Online Surveillance (CUSUM & EWMA)                               │
│ Tracks daily usage drops (lambda=0.2, h=4.0 sigma) & AHI spikes           │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Layer 1: Phenotype Clustering (K-Means & GMM)                             │
│ Discovers 4 patient archetypes: Robust, Variable, Early Dropout, High Leak│
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Layer 2: Multimodal Longitudinal State Transitions                        │
│ Markov state transition matrix modeling biomarker stability vs decay      │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Layer 3: Supervised Non-Adherence Risk (Ensemble)                         │
│ Stacked LightGBM + CatBoost + XGBoost predicting 90-day risk (z_risk)     │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Layer 4: Cox Proportional Hazards Survival Modeling                       │
│ Estimates time-to-dropout & clinical mechanism triplets                   │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Layer 5: Causal Intervention Uplift Engine                                │
│ Meta-learner optimizing Conditional Average Treatment Effect (Delta Use)  │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Layer 6: Dynamic Action Proposal & Survey Orchestrator                    │
│ Generates patient_action_plan.csv, questionnaire triggers, and video plans │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Cohort Performance Benchmarks (41,117 Patients)
- **CMS Compliance Rate ($\ge 4\text{h/night}$)**: **90.12%** ($37,054$ patients)
- **Mean Daily CPAP Usage**: $5.81 \pm 1.94 \text{ hours}$
- **Mean Residual AHI**: $3.82 \text{ events/hour}$
- **Active Online Surveillance Alarms**: $5.33\%$ ($2,192$ patients)
- **Mean Survival Risk Score ($z\_risk$)**: $0.2184$ (High Risk $>0.70$: $5.8\%$)

---

## Component 4: Central Clinical Backend (VM2)

### 4.1 Architectural Role & Database Schema
VM2 is the central clinical repository running on Ubuntu Linux at `http://159.84.143.151:80`. It hosts the PostgreSQL database (`DB_Clinical`) and provides surveillance dashboards for pulmonologists and sleep technicians.

### 4.2 Key Ingestion Contracts
1. **Video Assignments (`POST /api/videos/{patient_id}/assign`)**:
   - Pushed by Video VM4 (`X-Video-Server-Key`).
   - Logs the prescribed coaching clip, sequence transitions, and trigger rationale.
2. **Telemetry Event Traces (`POST /api/telemetry/event-trace`)**:
   - Pushed by Pi Edge & Video VM4 (`X-API-Key`).
   - Records $t_0 \dots t_7$ timestamps, measured RTT, and SLA compliance.
3. **Structured AI Predictions (`POST /api/data/predictions`)**:
   - Pushed by AI Server VM3 (`X-ML-Key`).
   - Stores patient risk tiers ($z\_risk$), survival hazard triplets, and CATE intervention recommendations.

---

*Proceed to [CODEBASE_MAP.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/CODEBASE_MAP.md) for a complete file-by-file directory index.*
