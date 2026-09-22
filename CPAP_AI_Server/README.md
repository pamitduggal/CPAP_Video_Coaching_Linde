# CPAP Just-in-Time Video Coaching: AI Supervisor Server (VM3)

Machine learning analytics service and risk stratification engine.  
DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France.

---

## What this server does

The AI Supervisor runs on VM3. It processes clinical CPAP records and wearable data across 41,117 patients, identifying which individuals are drifting toward abandoning therapy and prescribing timely interventions.

The core pipeline divides the problem into seven practical stages:
- Layer 0 (Statistical Process Control): Uses CUSUM and EWMA control charts to catch sudden drops in nightly hours or sharp spikes in mask leak before the patient's monthly average reflects it.
- Layer 1 (Phenotype Clustering): Groups patients by usage habits and clinical severity.
- Layer 2 (Biomarker State Transitions): Tracks shifts across physiological states captured by wearables (blood oxygen, heart rate, sleep stages).
- Layer 3 (Dropout Prediction): Combines XGBoost, CatBoost, and Random Forest into an ensemble score estimating 30-day abandonment risk ($z\_risk$).
- Layer 4 (Survival Analysis): Fits Cox proportional hazards models to estimate when a struggling patient is most likely to quit.
- Layer 5 (Causal Uplift): Estimates treatment effects (CATE) to see whether a specific patient responds better to video education, a nurse phone call, or an in-person technician visit.
- Layer 6 (Video Assignment): Matches high-risk patients to targeted coaching clips while checking previous assignments so we never show the same video twice.

The service uses two network ports: port 8000 serves the web dashboard and REST API, while port 8001 hosts a background listener that accepts catalog sync updates from the Video VM.

---

## Directory layout

```text
CPAP_AI_Server/
├── core/                             # Server routing, pipeline execution, and video tracker
├── scripts/                          # Port inspection and cohort KPI benchmarking
├── tests/                            # Automated test suite (7 verification scripts)
├── M4_FINAL_F2.ipynb                 # Reference notebook running Layers 0 through 6
├── api_data_loader.py                # Command-line entrypoint for cohort scoring
├── sitecustomize.py                  # Python hook that redirects CSV calls to REST endpoints
├── run_ai_server.bat                 # Batch launcher with automatic port clearing
├── distributed_trigger_catalog.json  # Cached 39-item trigger catalog
├── data/                             # Data folder (.gitkeep present; patient CSVs removed)
├── artifacts/                        # Output folder holding the sanitized tracker template
├── reports/                          # Summary statistics (cpap_kpis_summary.json)
└── .env.example                      # Environment variable template
```

---

## Quick start

### 1. Configure environment
```powershell
copy .env.example .env
```
Provide your `AI_SERVER_API_KEY`, `BACKEND_API_KEY`, and `VIDEO_SERVER_API_KEY`.

### 2. Launch the server
```powershell
.\run_ai_server.bat
```
The script runs `scripts/clear_ports.py` to kill any zombie processes hanging on ports 8000 or 8001, then launches Uvicorn. View the dashboard at `http://localhost:8000/dashboard`.

### 3. Run the test suite
```powershell
python tests/test_technical_briefing.py
python tests/test_server_dashboard.py
python tests/verify_server_routes.py
python tests/test_playlist.py
python tests/test_tracker.py
python tests/test_triggers.py
python tests/test_full_system.py
```

---

## Detailed documentation

For technical details, formulas, and API parameters, see the documents in `docs/`:

| Topic | Document |
| :--- | :--- |
| System architecture and multi-tier flow | [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) |
| Mathematical definitions and Layer 0-6 logic | [docs/COMPONENTS.md](../docs/COMPONENTS.md) |
| Codebase inventory | [docs/CODEBASE_MAP.md](../docs/CODEBASE_MAP.md) |
| REST endpoints and webhook contracts | [docs/API.md](../docs/API.md) |
| Route listing and port split | [docs/ROUTES.md](../docs/ROUTES.md) |
| State persistence and tracker JSON schema | [docs/STATE.md](../docs/STATE.md) |
| Deployment runbook and process management | [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) |
| How to test and retrain models | [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) |
| Intern handover notes | [docs/HANDOVER_REPORT.md](../docs/HANDOVER_REPORT.md) |
