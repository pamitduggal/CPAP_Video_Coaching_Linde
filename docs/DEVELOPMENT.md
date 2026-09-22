# SleepCare CPAP Ecosystem: Developer Onboarding and Testing Guide

> DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France  
> Author: Pamit Duggal (Software and AI Engineering Intern)  
> Scope: Local development, test execution, adding coaching videos, and troubleshooting

---

## 1. Local environment setup

To run tests or develop features on a single workstation:

### Python environment
Make sure you have Python 3.11 or 3.12 installed:
```bash
python --version
```

Create a top-level virtual environment:
```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux or macOS:
source .venv/bin/activate
```

Install the dependencies:
```bash
pip install fastapi uvicorn requests pandas numpy scipy scikit-learn lightgbm catboost xgboost lifelines opencv-python slowapi python-multipart python-dotenv jupyter
```

---

## 2. Running the test suites

We wrote regression tests for each tier to catch broken imports, route changes, or model regressions before committing code.

### 2.1 Video Server tests
On the Video Server VM or local checkout:
```powershell
cd CPAP_Video_Server
python calculate_kpis.py
```
This script tests that all 39 video files exist and can be read, confirms that all 78 WebVTT subtitle tracks match their corresponding video durations, and tests HTTP 206 byte-range streaming.

Expected output:
```text
================================================================================
  ALL TESTS COMPLETED (0 FAILURES):
    - Static Assets and APIs : 10/10 PASSED
    - Video Streams (MP4)    : 39/39 PASSED (HTTP 206 Byte-Range Seek)
    - Subtitles (WebVTT)     : 78/78 PASSED (100% Bilingual Parity EN/FR)
    - Action/Sim Buttons     : 7/7 PASSED (Scenario 1, 2, 3, Sync, Rebuild, Reset)
================================================================================
```

### 2.2 AI Server test suite (`CPAP_AI_Server/tests/`)
From PowerShell:
```powershell
cd CPAP_AI_Server

# 1. Tests the 39 catalog items, boolean evaluation, and <1ms fast path
python tests/test_technical_briefing.py

# 2. Tests the web dashboard HTML, SVG gauges, and telemetry cards
python tests/test_server_dashboard.py

# 3. Verifies REST route availability and status codes
python tests/verify_server_routes.py

# 4. Tests Scenario 2 virtual playlist ordering and duration calculations
python tests/test_playlist.py

# 5. Tests persistent tracker deduplication and recovery after restart
python tests/test_tracker.py

# 6. Tests the 14 multimodal wearable anomaly triggers
python tests/test_triggers.py

# 7. End-to-end integration test (tracker, pipeline, and FastAPI)
python tests/test_full_system.py
```

### 2.3 Raspberry Pi edge test suite (`test_csv/`)
On the Raspberry Pi:
```bash
cd ~/Desktop/CPAP_Raspberry_Pi

# 1. Whole suite test: Feeds sample CSV fixtures through /ingest and /timing
python3 test_csv/verify.py

# 2. Wearables test: Tests 27 edge cases for Videos 28 to 37 against the Video VM
.venv/bin/python test_csv/test_wearables.py
```

---

## 3. How to add a new clinical coaching video

Follow these steps whenever clinical partners produce a new coaching clip:

### Step 1: Add media files
1. Pick the next sequential integer ID (for example, `40`).
2. Put the 1080p MP4 file in `CPAP_Video_Server/existing_videos/` or `new_videos/`:
   `40_Nasal_Pillow_Sizing_Guide.mp4`
3. Put the matching bilingual subtitles in `existing_subtitles/` or `new_subtitles/`:
   `40_Nasal_Pillow_Sizing_Guide.en.vtt`
   `40_Nasal_Pillow_Sizing_Guide.fr.vtt`

### Step 2: Extract video cues and metadata
Run the automated metadata profiler:
```powershell
cd CPAP_Video_Server
python build_video_metadata.py
```
This reads the video with OpenCV to record duration, resolution, and frame rate, parses the narration cues from the WebVTT files, sets up composability links (`can_precede`, `can_follow`), and creates `metadata/video_40.json`.

### Step 3: Update catalog and sync nodes
```powershell
python update_master_metadata.py
python sync_remote_nodes.py
```
This rebuilds `metadata/master_video_metadata.json` and pushes the updated catalog out to the AI Server and the Pi.

### Step 4: Verify streaming
```bash
curl -I http://159.84.143.246:8080/videos/40_Nasal_Pillow_Sizing_Guide.mp4
curl -I http://159.84.143.246:8080/subtitles/40_Nasal_Pillow_Sizing_Guide.en.vtt
```

---

## 4. How to modify an anomaly trigger rule

To adjust thresholds or boolean logic for any clinical trigger:

1. **Update the edge engine (`CPAP_Raspberry_Pi/edge_detection.py`)**:
   Locate the rule or edit the `WEARABLE_LOGIC` dictionary. For example, to adjust the SomnoArt sleeve washing trigger from 60% to 65%:
   ```python
   fires36 = lt(SomnoArt_Lens_Transmission, 65) or isTrue(Maintenance_Due)
   ```
2. **Update the AI Server rule engine (`CPAP_AI_Server/core/video_engine.py`)**:
   Adjust the evaluation branch in `evaluate_wearable_anomalies()`.
3. **Update the catalog definition (`CPAP_Video_Server/metadata/video_36.json`)**:
   Edit the condition string in `video_36.json`, re-run `python update_master_metadata.py`, and run `python sync_remote_nodes.py`.
4. **Run regression tests**:
   Run `test_csv/test_wearables.py` on the Pi and `python tests/test_triggers.py` on the AI Server.

---

## 5. Retraining the machine learning models

The 7-layer pipeline is defined in `CPAP_AI_Server/M4_FINAL_F2.ipynb`.

### The runtime interceptor (`core/interceptor.py`)
When executing the pipeline, `sitecustomize.py` hooks `pandas.read_csv`. When a notebook cell calls `pd.read_csv("Usage3.csv")`:
1. It first queries live data from the Central Backend API (`http://159.84.143.151/api/data/cpap-usage`).
2. If offline, it falls back to local data in `data/Usage3.csv`.
3. Output files (`patient_action_plan.csv`, `features_merged.csv`) write directly into `artifacts/`.

### Running the pipeline from the command line
```powershell
cd CPAP_AI_Server
python api_data_loader.py --run-pipeline
```
Or via HTTP POST:
```bash
curl -X POST http://localhost:8000/api/pipeline/run \
  -H "X-API-KEY: <YOUR_AI_SERVER_API_KEY>"
```

---

## 6. Common issues and troubleshooting

### 1. `[WinError 10048] Only one usage of each socket address is normally permitted`
- Cause: A previous Python process crashed or was closed abruptly without releasing port 8000, 8001, or 8080.
- Fix:
  ```powershell
  # Free port 8080:
  Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  
  # Free ports 8000 and 8001:
  python scripts/clear_ports.py
  ```

### 2. Browser shows double subtitles
- Cause: Both the native browser cue renderer (`video::cue`) and our custom overlay are active at the same time.
- Fix: In `dashboard.js`, ensure `track.mode = 'hidden'` runs on all text tracks, and do a hard reload in the browser (`Ctrl + F5`).

### 3. Remote dashboard access returns HTTP 403 Forbidden
- Cause: The operations console blocks requests originating outside localhost.
- Fix: Create an SSH port forwarding tunnel:
  ```bash
  ssh -L 8080:localhost:8080 user@159.84.143.246
  ```
  Then navigate to `http://localhost:8080/dashboard` in your local browser.

### 4. Edge Pi misses pressure anomalies on phone CSV uploads
- Cause: The mobile app exports the column as lowercase `pressure90`, but `edge_detection.py` searches for `Presure90` or `pressure`.
- Fix: Add `pressure90` to the column resolution tuple in `edge_detection.py`.

Refer back to [HANDOVER_REPORT.md](HANDOVER_REPORT.md) for master summaries and immediate roadmaps.
