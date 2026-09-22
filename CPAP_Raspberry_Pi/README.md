# CPAP Just-in-Time Video Coaching — Raspberry Pi Edge Service

FastAPI edge computing service deployed on the patient-side Raspberry Pi 5 node.  
Developed in partnership between **DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon)** and **Linde HomeCare France**.

---

## 1. Architectural Mission: "Detect, Decide, and Forward"

The Raspberry Pi 5 edge node is positioned at the network periphery between the patient's smartphone, the Video VM, and the central clinical database. Its role is strictly deterministic triage and latency measurement:
- Ingests raw nightly patient CSV telemetry via `POST /ingest`.
- Executes 37 clinical triage rules in under 6ms (`edge_detection.py`).
- Routes interventions across Scenario 1 (single clip), Scenario 2 (virtual sequence), or Scenario 3 (generative AI).
- Forwards selected video requests to the Video VM (`POST /api/orchestrate` or `POST /api/vertex-generate`).
- Tracks client roundtrip playback latency via `POST /timing/{id}` and pushes telemetry traces to the central backend.

The Pi does not render or serve heavy MP4 files; all media delivery is delegated to the Video Server.

---

## 2. Directory Structure

```text
CPAP_Raspberry_Pi/
├── app.py                # Core FastAPI service (:8000), authentication & timing
├── edge_detection.py     # 37-rule deterministic clinical anomaly triage engine
├── load_library.py       # Startup video indexer & Scenario 1/2/3 decision trees
├── sync_catalog.py       # Distributed catalog synchronization utility
├── metadata/             # 37 clinical video metadata profiles (video_01..37.json)
├── test_csv/             # Verification CSV fixtures & automated regression scripts
├── phone_csv/            # Ready-to-use CSV files for mobile app manual testing
└── .env.example          # Environment variables template
```

---

## 3. Quick Start

### Step 1: Environment Setup
```bash
cp .env.example .env
# Edit .env and supply your API_KEY, VIDEO_SERVER_API_KEY, and BACKEND_API_KEY
```

### Step 2: Install Dependencies & Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Verify service status:
```bash
curl -s http://localhost:8000/health
```

---

## 4. Single Source of Truth Documentation

To prevent duplicate instructions, all exhaustive technical specifications have been consolidated into the centralized `docs/` manual:

| Topic | Reference Document |
| :--- | :--- |
| **System Architecture & Data Flows** | [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) |
| **Component Mechanics & 37 Rule Logic** | [docs/COMPONENTS.md](../docs/COMPONENTS.md) |
| **Complete Codebase Directory Map** | [docs/CODEBASE_MAP.md](../docs/CODEBASE_MAP.md) |
| **REST API Contracts & Ingestion Schemas** | [docs/API.md](../docs/API.md) |
| **Route Index & HTTP Error Statuses** | [docs/ROUTES.md](../docs/ROUTES.md) |
| **State Persistence & Event Logging** | [docs/STATE.md](../docs/STATE.md) |
| **Production Deployment & Tailscale Funnel** | [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) |
| **Testing, Fixtures & Adding Anomaly Rules** | [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) |
| **Master Handover & Intern Roadmap** | [docs/HANDOVER_REPORT.md](../docs/HANDOVER_REPORT.md) |
