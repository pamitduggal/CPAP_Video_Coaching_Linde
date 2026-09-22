# SleepCare CPAP: Just-in-Time Clinical Coaching and Multimodal AI Telemonitoring

> A collaborative research project between DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France.  
> Obstructive Sleep Apnea (OSA) telemonitoring system combining edge anomaly triage, 7-layer machine learning risk stratification, and dynamic 1080p video delivery.

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Video Standard](https://img.shields.io/badge/Video-1080p%20Full%20HD%20(39%20Clips)-E11D48.svg)](#)
[![Subtitles Parity](https://img.shields.io/badge/Subtitles-100%25%20Bilingual%20(78%20Tracks%20EN%2FFR)-10B981.svg)](#)
[![CMS Compliance](https://img.shields.io/badge/CMS%20Compliance-90.12%25-success)](#)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20Research-blue.svg)](#)

---

## Overview

SleepCare monitors Continuous Positive Airway Pressure (CPAP) therapy in real time. We built it to solve a stubborn clinical problem: patients abandon CPAP when simple mechanical issues go unaddressed for weeks. The system captures nightly CPAP usage, mask leak, and residual apnea data alongside wearable telemetry (pulse oximetry, blood pressure, ECG), spots problems on an edge node, and serves targeted educational videos before the patient gives up on treatment.

We validated this setup on longitudinal data from 41,117 patients in France and demonstrated live closed-loop intervention delivery at our consortium demonstration in Berlin.

![SleepCare Architecture](docs/images/sleepcare_architecture.jpg)

---

## Repository organization

```text
CPAP new/
├── CPAP_Raspberry_Pi/        # Edge node service running on Raspberry Pi 5
│   ├── app.py                # FastAPI edge service (:8000), ingest and RTT measurement
│   ├── edge_detection.py     # 37 deterministic clinical triage rules
│   ├── load_library.py       # Startup video indexer and scenario selector
│   └── .env.example          # Environment variable template for edge node
│
├── CPAP_Video_Server/        # Media streaming and generative video node (VM4)
│   ├── video_vm_server.py    # FastAPI service (:8080) with HTTP 206 byte-range seeking
│   ├── deduplication_engine.py# 3-level in-memory pre-generation deduplication shield
│   ├── assignment_ledger.py  # Thread-safe persistent assignment ledger
│   ├── dashboard/            # Clinician operations interface and subtitle overlay
│   ├── existing_videos/      # 37 curated 1080p coaching videos
│   ├── new_videos/           # 2 AI-generated 1080p coaching videos (Veo 3.1)
│   ├── existing_subtitles/   # 74 bilingual WebVTT subtitle files (EN and FR)
│   ├── new_subtitles/        # 4 bilingual WebVTT subtitle files (EN and FR)
│   └── .env.example          # Environment variable template for Video VM
│
├── CPAP_AI_Server/           # 7-layer machine learning supervisor and analytics (VM3)
│   ├── core/                 # Modular AI supervisor package (server, pipeline, engine)
│   ├── M4_FINAL_F2.ipynb     # 7-layer ML pipeline notebook (Layers 0 through 6)
│   ├── artifacts/            # Model output tables and persistent video tracker
│   ├── scripts/              # Port cleaner and KPI benchmark calculation scripts
│   ├── tests/                # Automated regression test suite
│   └── .env.example          # Environment variable template for AI supervisor
│
├── docs/                     # Technical documentation and intern handover suite
│   ├── HANDOVER_REPORT.md    # Master handover report for incoming engineers
│   ├── ARCHITECTURE.md       # Multi-node system topology and latency trace
│   ├── COMPONENTS.md         # Detailed breakdown of each architectural tier
│   ├── CODEBASE_MAP.md       # File-by-file directory index
│   ├── API.md                # REST API reference and request examples
│   ├── ROUTES.md             # Complete endpoint catalog and status codes
│   ├── STATE.md              # State persistence, atomic swap ledgers, and caching
│   ├── DEPLOYMENT.md         # Production runbooks and service configuration
│   └── DEVELOPMENT.md        # Local workflows, test execution, and video addition guide
│
└── .gitignore                # Security filter blocking secrets and raw patient data
```

---

## Quick start

### 1. Configure environment files

All production secrets and private tokens have been removed from the repository. Copy each template and populate your local credentials:

```bash
# Edge Node:
cp CPAP_Raspberry_Pi/.env.example CPAP_Raspberry_Pi/.env

# Video Server:
cp CPAP_Video_Server/.env.example CPAP_Video_Server/.env

# AI Server:
cp CPAP_AI_Server/.env.example CPAP_AI_Server/.env
```

Set your API keys (`SERVER_API_KEY`, `BACKEND_API_KEY`, `GOOGLE_VERTEX_API_KEY`) in each `.env` file before starting the services.

### 2. Launching services

#### Raspberry Pi edge node (Port 8000)
```bash
cd CPAP_Raspberry_Pi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

#### CPAP video server (Port 8080)
```powershell
cd CPAP_Video_Server
.\start_server.bat
```
The operations dashboard runs at `http://localhost:8080/`.

#### CPAP AI supervisor server (Ports 8000 and 8001)
```powershell
cd CPAP_AI_Server
.\run_ai_server.bat
```
The AI surveillance dashboard runs at `http://localhost:8000/dashboard`.

---

## Security and data privacy

- **Clean credentials**: All production bearer tokens, internal passwords, and cloud API keys have been stripped and replaced with environment variables.
- **Git rules**: The root `.gitignore` blocks `.env` files, log files, and patient CSV data from ever entering version control.
- **Healthcare privacy**: Patient identifiers are pseudonymous (`AtHomePatientId`). The architecture follows European GDPR and French HDS (Hébergeur de Données de Santé) guidelines for medical telemetry.

---

## Technical documentation index

Detailed technical specifications live in the `docs/` folder:

- [Handover report](docs/HANDOVER_REPORT.md): Context, architectural trade-offs, and open tasks for incoming team members.
- [Architecture](docs/ARCHITECTURE.md): Multi-node topology and end-to-end latency budget from phone upload to video playback.
- [Components](docs/COMPONENTS.md): Low-level breakdown of the edge engine, video server, AI pipeline, and central backend.
- [Codebase map](docs/CODEBASE_MAP.md): Directory and file inventory.
- [API specification](docs/API.md): Request and response schemas for all endpoints.
- [Route index](docs/ROUTES.md): Reference table of HTTP routes, auth requirements, and error codes.
- [State and storage](docs/STATE.md): How the platform manages cache files, atomic ledger updates, and session state.
- [Deployment](docs/DEPLOYMENT.md): Production setup, Windows batch files, and systemd units.
- [Development and testing](docs/DEVELOPMENT.md): Local testing procedures and how to add new clinical videos.

---

DISP Laboratory (Lyon) and Linde HomeCare France.
