# CPAP Just-in-Time Video Coaching — AI Supervisor Server (VM3)

Machine learning supervisor and population risk stratification platform.  
Developed in partnership between **DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon)** and **Linde HomeCare France**.

---

## 1. Architectural Mission: 7-Layer Machine Learning Intelligence

The AI Supervisor Server (VM3) analyzes longitudinal CPAP and wearable telemetry across 41,117 patients to detect treatment failure and prescribe personalized interventions:
- **Layer 0 (Online Statistical Process Control)**: Real-time CUSUM and EWMA alarms detecting drift in usage, residual AHI, and mask leaks.
- **Layer 1 (Phenotypic Subtyping)**: Unsupervised clustering isolating distinct therapy adherence behaviors.
- **Layer 2 (State Transition Markov Models)**: Multimodal wearable biomarker state drift tracking.
- **Layer 3 (Stacked Supervised Dropout Classification)**: XGBoost + CatBoost + Random Forest predicting 30-day therapy abandonment ($z\_risk$).
- **Layer 4 (Survival Analysis)**: Cox proportional hazards modeling patient dropout velocity over 90 days.
- **Layer 5 (Causal Uplift Modeling)**: Conditional Average Treatment Effect (CATE) determining optimal coaching interventions.
- **Layer 6 (Dynamic Decision Orchestration)**: Multi-objective video coaching selection with persistent deduplication.
- **Dual-Port Service Architecture**: Port 8000 serves the interactive clinician dashboard and REST API; Port 8001 hosts a background daemon listening for distributed catalog sync webhooks.

---

## 2. Directory Structure

```text
CPAP_AI_Server/
├── core/                             # Modular AI Supervisor package (server, pipeline, engine)
├── scripts/                          # Port scanner (clear_ports.py) & KPI benchmark calculators
├── tests/                            # Consolidated 7-script automated test suite
├── M4_FINAL_F2.ipynb                 # Authoritative 7-layer ML intelligence pipeline
├── api_data_loader.py                # Backwards-compatible CLI runner & entrypoint
├── sitecustomize.py                  # Runtime virtualization hook for automated data streaming
├── run_ai_server.bat                 # Universal Windows batch launcher with port conflict clearing
├── distributed_trigger_catalog.json  # Cached 39-item distributed trigger matrix
├── data/                             # Data directory with .gitkeep (sensitive CSVs purged)
├── artifacts/                        # Model artifacts & sanitized tracker template
├── reports/                          # Aggregate KPI benchmarks (cpap_kpis_summary.json)
└── .env.example                      # Environment variables template
```

---

## 3. Quick Start

### Step 1: Environment Setup
```bash
cp .env.example .env
# Edit .env and supply AI_SERVER_API_KEY, BACKEND_API_KEY, VIDEO_SERVER_API_KEY
```

### Step 2: Launch Service
```powershell
.\run_ai_server.bat
```
*The service scans ports 8000 and 8001, clears stale sockets, and starts both listeners. Access the AI Surveillance Dashboard at `http://localhost:8000/dashboard`.*

### Step 3: Run Automated Regression Tests
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

## 4. Single Source of Truth Documentation

To prevent duplicate instructions, all exhaustive technical specifications have been consolidated into the centralized `docs/` manual:

| Topic | Reference Document |
| :--- | :--- |
| **System Architecture & 7-Layer Pipeline** | [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) |
| **Component Mechanics & Mathematical Formulas** | [docs/COMPONENTS.md](../docs/COMPONENTS.md) |
| **Complete Codebase Directory Map** | [docs/CODEBASE_MAP.md](../docs/CODEBASE_MAP.md) |
| **REST API Contracts & Webhook Schemas** | [docs/API.md](../docs/API.md) |
| **Route Catalog & Dual-Port Endpoints** | [docs/ROUTES.md](../docs/ROUTES.md) |
| **State Persistence, Anti-Duplicate Tracker** | [docs/STATE.md](../docs/STATE.md) |
| **Production Deployment & Windows Batch Scripts** | [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) |
| **Testing, Validation & Modifying AI Rules** | [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) |
| **Master Handover & Intern Roadmap** | [docs/HANDOVER_REPORT.md](../docs/HANDOVER_REPORT.md) |
