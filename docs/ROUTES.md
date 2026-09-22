# SleepCare CPAP Ecosystem — Exhaustive Route & Endpoint Index

> **DISP Laboratory (Lyon) & Linde HomeCare France**  
> *Author: Pamit Duggal (Software & AI Engineering Intern)*  
> *Scope: Comprehensive Route Table, Parameters, Schemas & Status Codes*

---

## 1. Raspberry Pi 5 Edge Node Routes (`app.py` - Port 8000)

| Method | Path | Auth Header | Rate Limit | Request Body / Parameters | Success | Error Codes | Description |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `POST` | `/ingest` | `X-API-Key: <key>` | 20/min | `multipart/form-data`: `file`, `patient_id`, `language`, `sent_at` | `200` | 400, 401, 422, 500 | Ingests nightly CSV, runs triage, forwards to Video VM. |
| `POST` | `/timing/{event_id}` | `X-API-Key: <key>` | 60/min | JSON: `{"rtt_ms": float}` | `200` | 400, 401, 404 | Records client roundtrip time and calculates transit latency. |
| `GET` | `/patient/{patient_id}/coaching` | `X-API-Key: <key>` | 120/min | Path: `patient_id` (string) | `200` | 401, 404 | Dashboard polling for pending video recommendations. |
| `POST` | `/patient/{patient_id}/clear` | `X-API-Key: <key>` | 60/min | Path: `patient_id` (string) | `200` | 401, 404 | Marks pending coaching watched (`frontend_cleared_at`). |
| `GET` | `/health` | None | 60/min | None | `200` | — | Health probe returning service name and indexed video count. |
| `POST` | `/api/triggers/sync` | None / Internal | 60/min | JSON: Updated trigger catalog array | `200` | 400, 500 | Inbound catalog broadcast receiver from Video VM. |

---

## 2. CPAP Video Server Routes (`video_vm_server.py` - Port 8080)

### 2.1 Media Streaming & Asset Delivery

| Method | Path | Auth | Headers | Expected Output | Status Codes |
| :--- | :--- | :---: | :--- | :--- | :---: |
| `GET`, `HEAD` | `/videos/{filename}` | None | `Range: bytes=X-Y` (optional) | 1080p MP4 byte-range stream (`video/mp4`) | `200`, `206`, `404` |
| `GET`, `HEAD` | `/videos/existing/{filename}` | None | `Range: bytes=X-Y` (optional) | Direct stream for curated videos 1–37 | `200`, `206`, `404` |
| `GET`, `HEAD` | `/videos/new/{filename}` | None | `Range: bytes=X-Y` (optional) | Direct stream for generated videos 38+ | `200`, `206`, `404` |
| `GET`, `HEAD` | `/subtitles/{filename}` | None | Zero-cache headers emitted | WebVTT track (`text/vtt; charset=utf-8`) | `200`, `404` |
| `GET` | `/subtitles/existing/{filename}`| None | Zero-cache headers emitted | Curated WebVTT subtitles 1–37 | `200`, `404` |
| `GET` | `/subtitles/new/{filename}` | None | Zero-cache headers emitted | Generated WebVTT subtitles 38+ | `200`, `404` |

### 2.2 Video Orchestration & Synthesis

| Method | Path | Auth Header | Request Body Schema | Success | Error Codes |
| :--- | :--- | :--- | :--- | :---: | :---: |
| `POST` | `/api/orchestrate` | `X-API-KEY` | JSON: `patient_id`, `video_id` / `video_filename`, `trigger_reason`, or `clips` array | `200` | 400, 401, 403, 404, 500 |
| `POST` | `/api/vertex-generate` | `X-API-KEY` | JSON: `patient_id`, `prompt`, `model`, `duration_s` | `200` | 400, 401, 403, 429, 500 |

### 2.3 Catalog & Cluster Administration

| Method | Path | Auth Header | Description | Success |
| :--- | :--- | :---: | :--- | :---: |
| `GET` | `/api/triggers/catalog` | None | Returns 39-video trigger matrix and streaming URLs | `200` |
| `GET` | `/api/library` | None | Returns directory inventory of videos and subtitles | `200` |
| `POST` | `/api/triggers/broadcast` | `X-API-KEY` | Manually triggers webhook sync to AI Server and Pi Edge | `200` |
| `POST` | `/api/catalog/rebuild` | `X-API-KEY` | Re-scans disk, regenerates metadata JSONs & catalogs | `200` |
| `GET` | `/health` | None | Server status, directory paths, and ledger size | `200` |
| `GET` | `/api/kpis` | None | Live system KPIs, TTFB benchmarks, domain distribution | `200` |
| `GET` | `/api/assignments/history` | None | Complete persistent assignment ledger history | `200` |
| `DELETE`| `/api/assignments/reset` | `X-API-KEY` | Resets persistent assignment history ledger | `200` |
| `GET` | `/api/activity/latest` | Localhost | Returns recent scenario events for Live Radar | `200`, `403` |
| `GET` | `/api/logs/stream` | Localhost | Real-time Server-Sent Events (SSE) server log stream | `200`, `403` |
| `GET` | `/` or `/dashboard` | Localhost | Serves single-page clinical operations web console | `200`, `403` |
| `GET` | `/favicon.ico` | None | Lightweight 204 No Content response | `204` |

---

## 3. CPAP AI Supervisor Server Routes (`core/server.py`)

### 3.1 Primary Port 8000 Endpoints

| Method | Path | Auth Header | Description | Status Codes |
| :--- | :--- | :---: | :--- | :---: |
| `GET` | `/` | None | Content-negotiated: Serves HTML dashboard or JSON info | `200` |
| `GET` | `/dashboard` | None | Interactive Single-Page HTML Dashboard | `200` |
| `GET` | `/health` | None | Health check: pipeline state, models, Video VM ping | `200` |
| `GET` | `/api/dashboard/stats` | None | Aggregated telemetry, active catalog, tracker stats | `200` |
| `GET` | `/api/dashboard/kpis` | None | Clinical, adherence, risk, and alarm cohort metrics | `200` |
| `GET` | `/api/server/logs` | None | Ring-buffer log stream for streaming console (`since_id`) | `200` |
| `GET` | `/api/patient/{patient_id}` | `X-API-KEY` | Comprehensive AI predictions and Scenario 1 video | `200`, `404` |
| `GET` | `/api/patient/{patient_id}/playlist`| `X-API-KEY` | Scenario 2 virtual-stitched video sequence playlist | `200`, `404` |
| `GET` | `/api/patients` | `X-API-KEY` | Paginated cohort patient predictions (`limit`, `offset`) | `200` |
| `POST` | `/api/pipeline/run` | `X-API-KEY` | Triggers background execution of 7-layer ML pipeline | `200`, `409` |
| `POST` | `/api/pipeline/push` | `X-API-KEY` | Pushes generated prediction artifacts to central DB | `200`, `500` |
| `POST` | `/api/pipeline/orchestrate-videos` | `X-API-KEY` | Dispatches video prescriptions for eligible cohort | `200` |
| `GET` | `/api/pipeline/status` | None | Pipeline execution status (`idle`, `running`, `failed`) | `200` |
| `POST` | `/api/video-server/orchestrate/{id}`| `X-API-KEY` | Single-patient video dispatch with local dedup check | `200` |
| `GET` | `/api/video-server/assigned-tracker`| `X-API-KEY` | Returns persistent assignment tracker statistics | `200` |
| `POST` | `/api/video-server/assigned-tracker/clear`| `X-API-KEY`| Resets local persistent assignment tracker | `200` |
| `POST` | `/api/video-server/vertex-generate`| `X-API-KEY` | Proxies Scenario 3 GenAI request to Video VM | `200` |
| `GET` | `/api/video-server/health` | None | Health check of connected Video VM Server | `200` |
| `POST` | `/api/video-server/sync-catalog` | `X-API-KEY` | Manually triggers catalog sync from Video VM | `200` |
| `GET` | `/api/proxy/video/{filename}` | None | Proxies video stream from Video VM with HTTP 206 | `200`, `206` |
| `GET` | `/api/proxy/subtitle/{filename}`| None | Proxies WebVTT subtitles without CORS restrictions | `200` |

### 3.2 Secondary Port 8001 Endpoints (Webhook Companion)

| Method | Path | Auth Header | Description | Status Codes |
| :--- | :--- | :---: | :--- | :---: |
| `POST` | `/api/triggers/sync` | `X-API-KEY` / `X-ML-Key` | Inbound webhook updating local catalog cache | `200`, `401`, `500` |
| `GET` | `/health` | None | Health probe for webhook companion daemon | `200` |

---

## 4. Central Clinical Backend Endpoints (VM2 - Reference)

| Method | Path | Auth Header | Caller | Description | Status Codes |
| :--- | :--- | :---: | :---: | :--- | :---: |
| `POST` | `/api/videos/{patient_id}/assign` | `X-Video-Server-Key` | Video VM | Pushes assigned coaching video & step transitions | `200`, `403`, `500` |
| `POST` | `/api/telemetry/event-trace` | `X-API-Key` | Pi & VM4 | Upserts $t_0 \dots t_7$ timing & latency KPI trace | `200`, `401`, `500` |
| `POST` | `/api/data/predictions` | `X-ML-Key` | AI Server | Ingests ML risk scores ($z\_risk$) and action plans | `200`, `401`, `500` |
| `GET` | `/api/data/cpap-usage` | `X-ML-Key` | AI Server | Telemetry stream query for model training | `200`, `401` |

---

*Proceed to [STATE.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/STATE.md) for data persistence, ledger, and cache architectures.*
