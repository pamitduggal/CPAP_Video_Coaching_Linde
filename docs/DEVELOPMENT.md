# SleepCare CPAP Ecosystem — Developer Onboarding & Testing Playbook

> **DISP Laboratory (Lyon) & Linde HomeCare France**  
> *Author: Pamit Duggal (Software & AI Engineering Intern)*  
> *Scope: Developer Workflows, Test Suites, Extending Rules, Retraining Models & Debugging*

---

## 1. Local Developer Environment Setup

To run and test the complete ecosystem on a single development machine (Windows, Linux, or macOS):

### 1.1 Python Version & Virtual Environment
Ensure **Python 3.12 (64-bit)** is installed:
```bash
python --version  # Must output Python 3.11+ or 3.12+
```

Create a root development virtual environment:
```bash
cd "c:\Users\pduggal\Downloads\CPAP new"
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

Install the combined development requirements:
```bash
pip install fastapi uvicorn requests pandas numpy scipy scikit-learn lightgbm catboost xgboost lifelines opencv-python slowapi python-multipart python-dotenv jupyter
```

---

## 2. Running Automated Test Suites

The ecosystem features a comprehensive automated testing suite guaranteeing that zero regressions occur across API contracts, media streams, and machine learning models:

### 2.1 Video Server Automated Test Suite (134 Checkpoints)
Verifies 10 static endpoints, 39 MP4 HTTP 206 streams, 78 WebVTT bilingual subtitles, and 7 action simulation buttons:
```powershell
cd C:\CPAP_Video_Server
python calculate_kpis.py
```
To run full dashboard and playback validation:
```powershell
python "C:\Users\Administrateur\.gemini\antigravity-ide\brain\ca990276-ea95-4c83-94c0-4900ef050b09\scratch\test_all_dashboard_elements.py"
```

**Expected Passing Summary**:
```text
================================================================================
  ALL TESTS COMPLETED (0 FAILURES):
    - Static Assets & APIs : 10/10 PASSED
    - Video Streams (MP4)  : 39/39 PASSED (HTTP 206 Byte-Range Seek)
    - Subtitles (WebVTT)   : 78/78 PASSED (100% Bilingual Parity EN/FR)
    - Action/Sim Buttons   : 7/7 PASSED (Scenario 1, 2, 3, Sync, Rebuild, Reset)
================================================================================
```

### 2.2 AI Server Automated Test Suite (`CPAP_AI_Server/tests/`)
Run each specialized test script from PowerShell:

```powershell
cd C:\CPAP_AI_Server

# 1. Verify Technical Briefing (39 items, boolean logic, <1ms fast path)
& "C:\Program Files\Python312\python.exe" tests/test_technical_briefing.py

# 2. Verify Server & Web Dashboard (HTML, SVG speedometer gauges, telemetry)
& "C:\Program Files\Python312\python.exe" tests/test_server_dashboard.py

# 3. Verify Server REST Routes & Ring Buffer Logging
& "C:\Program Files\Python312\python.exe" tests/verify_server_routes.py

# 4. Verify Scenario 2 Virtual-Stitched Playlist Priority Sequencing
& "C:\Program Files\Python312\python.exe" tests/test_playlist.py

# 5. Verify Persistent Anti-Duplicate Tracker & Restart Recovery
& "C:\Program Files\Python312\python.exe" tests/test_tracker.py

# 6. Verify 14 Multimodal Wearable Biomarker Anomaly Triggers
& "C:\Program Files\Python312\python.exe" tests/test_triggers.py

# 7. Verify End-to-End System Integration (Tracker, Pipeline, FastAPI)
& "C:\Program Files\Python312\python.exe" tests/test_full_system.py
```

### 2.3 Raspberry Pi Edge Verification (`test_csv/`)
On the Raspberry Pi 5:
```bash
cd ~/Desktop/CPAP_Edge_copy

# 1. Whole Suite Verification: Runs all CSV fixtures through /ingest & /timing
python3 test_csv/verify.py

# 2. Wearables End-to-End Test: Tests 27 cases for Videos 28-37 against live Video VM
.venv/bin/python test_csv/test_wearables.py
```

---

## 3. How to Add a New Clinical Video (Step-by-Step Guide)

Follow this standardized protocol whenever a new clinical coaching video is produced:

### Step 1: Assign ID and Store Media Assets
1. Assign the next sequential integer ID (e.g. `40`).
2. Place the Full HD (1080p, 30fps, H.264/AAC) video file in `CPAP_Video_Server/existing_videos/` or `new_videos/`:
   - e.g.: `40_Nasal_Pillow_Sizing_Guide.mp4`.
3. Create matching WebVTT bilingual subtitle files:
   - `40_Nasal_Pillow_Sizing_Guide.en.vtt`
   - `40_Nasal_Pillow_Sizing_Guide.fr.vtt`
   Store them in `existing_subtitles/` or `new_subtitles/`.

### Step 2: Auto-Profile Video Metadata & Cues
Run the automated video metadata builder:
```powershell
cd C:\CPAP_Video_Server
python build_video_metadata.py
```
This automatically:
- Extracts resolution, duration, FPS, and audio channels using OpenCV.
- Parses cue lines and narration transcripts from `.en.vtt` and `.fr.vtt`.
- Assigns directed composability links (`can_precede`, `can_follow`).
- Writes `metadata/video_40.json`.

### Step 3: Recompile Master Catalog & Synchronize Nodes
```powershell
python update_master_metadata.py
python sync_remote_nodes.py
```
This updates `metadata/master_video_metadata.json`, regenerates `distributed_trigger_catalog.json`, and broadcasts webhooks to the AI Server and Pi Edge.

### Step 4: Verify Streaming & Subtitles
```bash
curl -I http://159.84.143.246:8080/videos/40_Nasal_Pillow_Sizing_Guide.mp4
curl -I http://159.84.143.246:8080/subtitles/40_Nasal_Pillow_Sizing_Guide.en.vtt
```

---

## 4. How to Modify a Biomarker Anomaly Trigger Rule

To modify thresholds or boolean logic for any clinical trigger:

1. **Update Edge Triage Engine (`CPAP_Raspberry_Pi/edge_detection.py`)**:
   - Locate the rule function or update `WEARABLE_LOGIC` table.
   - Example: To alter SomnoArt Sleeve Washing (Video 36) threshold from 60% to 65%:
     ```python
     fires36 = lt(SomnoArt_Lens_Transmission, 65) or isTrue(Maintenance_Due)
     ```
2. **Update AI Server Video Engine (`CPAP_AI_Server/core/video_engine.py`)**:
   - Update the corresponding evaluation branch in `evaluate_wearable_anomalies()`.
3. **Synchronize Distributed Catalog (`CPAP_Video_Server/metadata/video_36.json`)**:
   - Edit the condition string in `video_36.json`.
   - Re-run `python update_master_metadata.py`.
   - Broadcast to cluster: `python sync_remote_nodes.py`.
4. **Run Regression Tests**:
   - Execute `test_csv/test_wearables.py` on Pi.
   - Execute `tests/test_triggers.py` on AI Server.

---

## 5. How to Retrain the 7-Layer Machine Learning Models

The analytical pipeline is defined in [`CPAP_AI_Server/M4_FINAL_F2.ipynb`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/M4_FINAL_F2.ipynb).

### 5.1 The Runtime Interceptor (`core/interceptor.py`)
During execution, `sitecustomize.py` injects `smart_read_csv` into the Python runtime. When `pd.read_csv("Usage3.csv")` is called:
1. It first attempts to stream live data from the Central Backend API (`http://159.84.143.151/api/data/cpap-usage`).
2. If offline, it falls back seamlessly to local files in `data/Usage3.csv`.
3. Output CSVs (`patient_action_plan.csv`, `features_merged.csv`) are automatically routed to `artifacts/`.

### 5.2 Executing Headless Pipeline Runs
To execute the pipeline headlessly via command line:
```powershell
cd C:\CPAP_AI_Server
& "C:\Program Files\Python312\python.exe" api_data_loader.py --run-pipeline
```
Or via HTTP POST request:
```bash
curl -X POST http://localhost:8000/api/pipeline/run \
  -H "X-API-KEY: <YOUR_AI_SERVER_API_KEY>"
```

---

## 6. Troubleshooting Playbook: Common Issues & Instant Fixes

### 1. `[WinError 10048] Only one usage of each socket address is normally permitted`
- **Cause**: An earlier Python/Uvicorn process crashed or was left running in the background, holding port 8000, 8001, or 8080.
- **Instant Fix**:
  ```powershell
  # For Port 8080:
  Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  # For Port 8000 & 8001:
  & "C:\Program Files\Python312\python.exe" scripts/clear_ports.py
  ```

### 2. Browser Shows Stale Subtitles or Double Cues
- **Cause**: Browser native cue renderer (`video::cue`) is active alongside custom overlay, or aggressive browser caching.
- **Instant Fix**:
  - The server emits `Cache-Control: no-cache, no-store, must-revalidate`.
  - In `dashboard.js`, ensure `track.mode = 'hidden'` is executed on all loaded tracks.
  - Perform a hard refresh in the browser (`Ctrl + F5` or `Ctrl + Shift + R`).

### 3. Remote Dashboard Access Returns HTTP 403 Forbidden
- **Cause**: Defense-in-depth security restriction locking management dashboards and SSE logs to `localhost` (`127.0.0.1`, `::1`).
- **Instant Fix**: Establish an SSH port forwarding tunnel:
  ```bash
  ssh -L 8080:localhost:8080 user@159.84.143.246
  ```
  Then navigate to `http://localhost:8080/dashboard`.

### 4. Edge Pi Fails to Detect Pressure Anomaly on Real Phone CSV
- **Cause**: Mobile app exports column as `pressure90` (lowercase), whereas `edge_detection.py` searches for `Presure90` or `pressure`.
- **Instant Fix**: Add `pressure90` to the column resolution tuple inside `edge_detection.py`.

---

*You have completed the technical documentation suite! Refer back to [HANDOVER_REPORT.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/HANDOVER_REPORT.md) for master summaries and immediate roadmaps.*
