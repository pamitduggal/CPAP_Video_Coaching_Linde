# SleepCare CPAP Ecosystem — Technical Handover Report

> **DISP Laboratory (Lyon) & Linde HomeCare France**  
> *Project: Just-in-Time Clinical Video Coaching & Multimodal AI Telemonitoring for CPAP Therapy*  
> **Author**: Pamit Duggal (Software & AI Engineering Intern)  
> **Date**: September 2026  
> **Target Audience**: Incoming Software & AI Engineering Intern, Research Engineers, Clinical System Administrators

---

## 1. Executive Summary & Welcome

Welcome to the **SleepCare CPAP** ecosystem! This repository contains the complete production-grade source code, machine learning pipelines, microservices, and edge runtime powering the **SleepCare Just-in-Time Video Coaching & AI Supervisor** platform. 

The system provides autonomous 24/7 telemonitoring and closed-loop audiovisual clinical interventions for Obstructive Sleep Apnea (OSA) patients receiving Continuous Positive Airway Pressure (CPAP) therapy. It bridges the gap between raw medical device telemetry (CPAP machines and 5 wearable biomarker sensors) and patient compliance by detecting anomalies in near-real-time and prescribing dynamic, bilingual, 1080p coaching videos directly to patient mobile apps and clinician surveillance portals.

The architecture was successfully validated in end-to-end trials and showcased at the live clinical stakeholder demonstration in **Berlin**, demonstrating sub-second delivery over simulated 5G Quality on Demand (QoD) networks and achieving a **90.12% CMS therapy compliance rate** across a cohort of **41,117 patients**.

![SleepCare Architecture](images/sleepcare_architecture.jpg)

---

## 2. Documentation Master Index

This handover package is structured into modular, comprehensive reference manuals located in this `docs/` directory:

| Document | Purpose & Scope |
| :--- | :--- |
| **[ARCHITECTURE.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/ARCHITECTURE.md)** | Full system topology, end-to-end telemetry lifecycle ($t_0 \dots t_7$), cross-node communication protocols, Mermaid sequence diagrams, and 5G QoD network models. |
| **[COMPONENTS.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/COMPONENTS.md)** | Deep dive into the 4 architectural pillars: Raspberry Pi 5 Edge Node, CPAP Video Server (VM4), AI Supervisor Server (VM3), and Central Clinical Backend (VM2). |
| **[CODEBASE_MAP.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/CODEBASE_MAP.md)** | File-by-file directory breakdown of all 3 server repositories, explaining the purpose of every script, configuration, data file, and asset. |
| **[API.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/API.md)** | Unified REST API manual covering edge ingestion, video streaming, catalog sync, AI pipeline triggering, and authentication headers. |
| **[ROUTES.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/ROUTES.md)** | Exhaustive endpoint index detailing every route, HTTP method, payload schema, query parameter, and HTTP status code. |
| **[STATE.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/STATE.md)** | In-depth breakdown of state persistence: JSON ledgers, 3-level deduplication caches, trigger catalogs, SQLite/PostgreSQL schemas, and thread-safety locks. |
| **[DEPLOYMENT.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/DEPLOYMENT.md)** | Step-by-step production runbooks, environment variable dictionaries, port configuration, Tailscale Funnel setup, batch launchers, and systemd services. |
| **[DEVELOPMENT.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/DEVELOPMENT.md)** | Developer onboarding guide: local testing workflows, running automated test suites (134+ checks), adding new videos, modifying trigger rules, and debugging gotchas. |

---

## 3. High-Level System Overview & Server Inventory

The ecosystem spans **three active server nodes** communicating across LAN, WAN, and VPN networks:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 SLEEPCARE MULTI-NODE TOPOLOGY                               │
├────────────────────────────────┬───────────────────────────────┬────────────────────────────┤
│ Node Name & Directory          │ Network Address & Ports       │ Core Role & Responsibilities│
├────────────────────────────────┼───────────────────────────────┼────────────────────────────┤
│ 1. Raspberry Pi 5 Edge Node    │ LAN: 192.168.x.x:8000         │ "Detect, Decide, Forward"  │
│    (CPAP_Raspberry_Pi)         │ Tailscale Funnel / Public     │ Ingests patient CSVs, runs │
│                                │ Binding: 0.0.0.0:8000         │ threshold triage, timing.  │
├────────────────────────────────┼───────────────────────────────┼────────────────────────────┤
│ 2. CPAP Video Server (VM4)     │ Host: 159.84.143.246:8080     │ Media Streaming & GenAI    │
│    (CPAP_Video_Server)         │ Binding: 0.0.0.0:8080         │ 39 1080p MP4s, 78 WebVTTs, │
│                                │ Dashboard: http://localhost:8080│ HTTP 206 TTFB <5ms, Veo 3.1│
├────────────────────────────────┼───────────────────────────────┼────────────────────────────┤
│ 3. AI Supervisor Server (VM3)  │ Host: 159.84.143.151:8000     │ 7-Layer ML Engine & Sync   │
│    (CPAP_AI_Server)            │ Webhook Daemon: :8001         │ CUSUM, XGBoost, CatBoost,  │
│                                │ Binding: 0.0.0.0:8000, :8001  │ Cox survival, uplift.      │
├────────────────────────────────┼───────────────────────────────┼────────────────────────────┤
│ 4. Central Clinical Backend    │ Host: http://159.84.143.151:80│ Central Database & Portal  │
│    (VM2 - Reference Node)      │ (External VM)                 │ PostgreSQL DB_Clinical,    │
│                                │                               │ Clinician web dashboard.   │
└────────────────────────────────┴───────────────────────────────┴────────────────────────────┘
```

---

## 4. Key Accomplishments & Current Status

During the internship period, the following milestones were achieved and tested:

1. **Real-Time Edge Triage Engine**:
   - Implemented a lightweight, sub-6ms decision engine on Raspberry Pi 5 (`edge_detection.py`) covering 37 clinical rules (Videos 1–27 for CPAP metrics; Videos 28–37 for Withings, Masimo, Hexoskin, and Somno-Art wearable anomalies).
   - Designed a dual-phase telemetry reporting loop (`/ingest` + `/timing/{id}`) calculating real client RTT and pushing millisecond metrics to the central clinical database (`DB_Clinical.telemetry.event_traces`).

2. **Enterprise Media Streaming & Virtual Sequence Assembly**:
   - Curated and indexed **39 Full HD (1080p, 30fps) videos** paired with **78 bilingual WebVTT subtitle tracks (100% English & French parity)**.
   - Built a high-throughput HTTP 206 Partial Content byte-range streaming engine in FastAPI achieving **< 5ms Time-to-First-Byte (TTFB)**.
   - Implemented **Scenario 2 Virtual Sequence Stitching**: eliminated server re-encoding bottlenecks by delivering playlist sequences with client-side 1.5s Alpha Crossfade (`fade_1_5s`) and solving the duplicate subtitle DOM overlay problem.

3. **Multi-Tier Pre-Generation Deduplication Shield**:
   - Engineered an in-memory 3-level deduplication shield (`deduplication_engine.py`) for Scenario 3 Generative AI synthesis (Level 1 MD5 prompt hash, Level 2 slug match, Level 3 deep metadata semantics), cutting costly Google Cloud Veo 3.1 API calls to **< 1ms reuse**.
   - Built an atomic, thread-safe `AssignmentLedger` preventing duplicate video prescriptions to patients.

4. **7-Layer Machine Learning Intelligence Hub**:
   - Operationalized the end-to-end analytical pipeline in `CPAP_AI_Server` (`M4_FINAL_F2.ipynb` / `core/pipeline.py`) across 41,117 patients: CUSUM/EWMA online drift alarms, phenotype clustering, multimodal state transitions, stacked supervised risk classification ($z\_risk$), Cox proportional hazards survival modeling, and CATE causal uplift intervention selection.
   - Built a dual-port architecture (Port 8000 for REST/Dashboard, Port 8001 for background catalog sync webhooks) with an automatic pre-flight port scanner (`scripts/clear_ports.py`) resolving Windows socket conflicts.

---

## 5. Security & Credentials Matrix

Each server relies on strict header tokens to prevent unauthorized mutations. Configure these in each server's local `.env` file (see `.env.example` templates):

| Token Variable | Environment Configuration | Used By | Purpose |
| :--- | :--- | :--- | :--- |
| `API_KEY` (Pi Edge) | `Set in CPAP_Raspberry_Pi/.env` | Phone App $\to$ Pi Edge | Authenticates `POST /ingest` & `/timing` |
| `SERVER_API_KEY` / `VIDEO_SERVER_API_KEY` | `Set in CPAP_Video_Server/.env` | Pi Edge & AI Server $\to$ Video VM4 | Authenticates `POST /api/orchestrate` & `/api/vertex-generate` |
| `VIDEO_SERVER_KEY` / `X-Video-Server-Key` | `Set in CPAP_Video_Server/.env` | Video VM4 $\to$ Central VM2 | Pushes video assignments (`POST /api/videos/{id}/assign`) |
| `BACKEND_API_KEY` / `X-ML-Key` | `Set in CPAP_AI_Server/.env` | AI Server & Video VM $\to$ Central VM2 | Pushes predictions & telemetry traces |
| `AI_SERVER_API_KEY` | `Set in CPAP_AI_Server/.env` | Admin clients $\to$ AI Server | Authenticates AI pipeline execution |
| `GOOGLE_VERTEX_API_KEY` | `Set in CPAP_Video_Server/.env` | Video VM4 $\to$ Google Cloud | Synthesizes Veo 3.1 videos & Gemini Flash subtitles |

> [!WARNING]
> Live `.env` files contain sensitive operational secrets. Ensure `.env` is never committed to public Git repositories or shared unencrypted.

---

## 6. Known Quirks, Traps & Watchouts for the Next Intern

Before writing any new code, read these critical quirks discovered and documented during development:

1. **The `pressure90` Column Naming Mismatch on Edge Pi**:
   - The patient mobile app exports CPAP pressure as `pressure90` (lowercase).
   - In `edge_detection.py`, the code looks for `Presure90` (note spelling) or `pressure`. If the incoming CSV has `pressure90`, it falls back to `0.0`, causing pressure-based rules (videos 4, 7, 10, 11) to fail to trigger on raw phone data.
   - *Fix pending*: Add `pressure90` to the column resolution tuple in `edge_detection.py`.

2. **Phone App Calling Deprecated `POST /event`**:
   - `POST /event` was deleted on 2026-09-03 in favor of the clean `/ingest` + `/timing` protocol.
   - Older builds of the mobile phone app still attempt `POST /event` after `/timing` and log a "Failed to send" error even though `/ingest` succeeded. Coordinate with the mobile team to remove this legacy call.

3. **Video VM Localhost Dashboard Security Lock**:
   - Accessing `http://159.84.143.246:8080/dashboard` from an external browser returns an **HTTP 403 Forbidden** security card by design.
   - To inspect the Video VM dashboard remotely, use an SSH tunnel:
     ```bash
     ssh -L 8080:localhost:8080 user@159.84.143.246
     ```
     Then open `http://localhost:8080/dashboard` in your local browser.

4. **Scenario 3 Google Cloud Quota Limits**:
   - Live video rendering through Google Veo 3.1 requires high Vertex AI project quotas. If the Google Cloud account experiences quota exhaustion, Vertex returns `429 RESOURCE_EXHAUSTED`.
   - The 3-Level Pre-Gen Deduplication Shield handles this gracefully by prioritizing existing or cached assets (`generative_cache_index.json`).

5. **Windows Socket Reset (`WinError 64` / `10048`)**:
   - On Windows Server, abruptly closed browser tabs can cause Uvicorn IOCP resets. Both `start_server.bat` (Video Server) and `run_ai_server.bat` (AI Server) incorporate automatic port-clearing scripts (`clear_ports.py`) and auto-recovery process wrappers to guarantee 24/7 uptime.

---

## 7. Immediate Roadmap & Suggested Next Tasks

Here are the recommended priority tasks for the incoming intern:

- [ ] **Task 1: Harmonize Pressure Column Extraction on Pi Edge**
   - Update `CPAP_Raspberry_Pi/edge_detection.py` to accept `pressure90` alongside `Presure90` and `pressure`.
   - Re-run `test_csv/verify.py` to confirm zero regression.

- [ ] **Task 2: Async GenAI Job Polling on Video Server**
   - Currently, `POST /api/vertex-generate` waits synchronously for cloud synthesis. For videos exceeding 20 seconds, this can risk HTTP timeouts.
   - Implement a background task queue (e.g. Celery or FastAPI BackgroundTasks) with a job status polling route (`GET /api/vertex-generate/status/{job_id}`).

- [ ] **Task 3: Automated Database Reconnect on Central Backend**
   - On the Central VM2 backend, ensure the telemetry upsert query uses a single atomic SQL `MERGE` / `ON CONFLICT (event_id) DO UPDATE` to prevent occasional primary key race conditions between Phase 1 and Phase 2 pushes.

- [ ] **Task 4: Dynamic Wearable Rules Ingestion from Catalog**
   - Currently, `sync_catalog.py` on the Pi verifies that the catalog matches `edge_detection.WEARABLE_LOGIC`. Enhance `edge_detection.py` to dynamically evaluate trigger rules directly from `metadata/*.json` so new videos can be deployed without Python code changes.

---

## 8. Emergency Contacts & Project References

- **Academic Supervisor**: DISP Laboratory, Université Lumière Lyon 2 / INSA Lyon
- **Industrial Partner**: Linde HomeCare France (Medical Device & Telemonitoring Division)
- **Primary Development Workstations**:
  - Edge Node: Raspberry Pi 5 (Debian Linux Bookworm)
  - VM3 (AI Server): Windows Server 2022 (`159.84.143.151`)
  - VM4 (Video Server): Windows Server 2022 (`159.84.143.246`)
  - VM2 (Central Database & Clinical Portal): Ubuntu Linux (`159.84.143.151:80`)

*Good luck taking the SleepCare CPAP platform to its next evolution! Please proceed to [ARCHITECTURE.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/ARCHITECTURE.md) to explore the system design.*
