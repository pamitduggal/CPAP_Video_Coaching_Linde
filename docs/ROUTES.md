# SleepCare CPAP Ecosystem: Route and Endpoint Reference

> DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France  
> Author: Pamit Duggal (Software and AI Engineering Intern)  
> Scope: Complete endpoint table across edge, video, and AI servers

---

## 1. Raspberry Pi edge node routes (`app.py`, port 8000)

| Method | Path | Auth Header | Rate Limit | Request Body or Parameters | Success Code | Error Codes | Description |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `POST` | `/ingest` | `X-API-Key: <key>` | 20/min | `multipart/form-data`: `file`, `patient_id`, `language`, `sent_at` | `200` | 400, 401, 422, 500 | Ingests nightly CSV, runs triage, notifies Video VM. |
| `POST` | `/timing/{event_id}` | `X-API-Key: <key>` | 60/min | JSON: `{"rtt_ms": float}` | `200` | 400, 401, 404 | Logs client roundtrip time and calculates transit latency. |
| `GET` | `/patient/{patient_id}/coaching` | `X-API-Key: <key>` | 120/min | Path: `patient_id` (string) | `200` | 401, 404 | Polling route for pending video recommendations. |
| `POST` | `/patient/{patient_id}/clear` | `X-API-Key: <key>` | 60/min | Path: `patient_id` (string) | `200` | 401, 404 | Clears watched status (`frontend_cleared_at`). |
| `GET` | `/health` | None | 60/min | None | `200` | None | Health check reporting indexed video count. |
| `POST` | `/api/triggers/sync` | None (Internal) | 60/min | JSON: Trigger catalog array | `200` | 400, 500 | Inbound catalog sync webhook from Video VM. |

---

## 2. CPAP Video Server routes (`video_vm_server.py`, port 8080)

### Media streaming endpoints

| Method | Path | Auth Header | Request Headers | Output Format | Status Codes |
| :--- | :--- | :---: | :--- | :--- | :---: |
| `GET`, `HEAD` | `/videos/{filename}` | None | `Range: bytes=X-Y` (optional) | 1080p MP4 byte-range stream (`video/mp4`) | `200`, `206`, `404` |
| `GET`, `HEAD` | `/videos/existing/{filename}` | None | `Range: bytes=X-Y` (optional) | Direct stream for curated videos 1 to 37 | `200`, `206`, `404` |
| `GET`, `HEAD` | `/videos/new/{filename}` | None | `Range: bytes=X-Y` (optional) | Direct stream for generated videos 38 and 39 | `200`, `206`, `404` |
| `GET`, `HEAD` | `/subtitles/{filename}` | None | Zero-cache response | WebVTT track (`text/vtt; charset=utf-8`) | `200`, `404` |
| `GET` | `/subtitles/existing/{filename}`| None | Zero-cache response | Curated WebVTT subtitles 1 to 37 | `200`, `404` |
| `GET` | `/subtitles/new/{filename}` | None | Zero-cache response | Generated WebVTT subtitles 38 and 39 | `200`, `404` |

### Orchestration and generation endpoints

| Method | Path | Auth Header | Request Schema | Success Code | Error Codes |
| :--- | :--- | :--- | :--- | :---: | :---: |
| `POST` | `/api/orchestrate` | `X-API-KEY` | JSON: `patient_id`, `video_id` or `video_filename`, `trigger_reason`, or `clips` array | `200` | 400, 401, 403, 404, 500 |
| `POST` | `/api/vertex-generate` | `X-API-KEY` | JSON: `patient_id`, `prompt`, `model`, `duration_s` | `200` | 400, 401, 403, 429, 500 |

### Catalog and administration endpoints

| Method | Path | Auth Header | Description | Success Code |
| :--- | :--- | :---: | :--- | :---: |
| `GET` | `/api/triggers/catalog` | None | Returns 39-video trigger matrix and streaming URLs | `200` |
| `GET` | `/api/library` | None | Returns filesystem inventory of videos and subtitles | `200` |
| `POST` | `/api/triggers/broadcast` | `X-API-KEY` | Fires webhook sync to AI Server and Pi Edge | `200` |
| `POST` | `/api/catalog/rebuild` | `X-API-KEY` | Re-scans disk and regenerates metadata JSON files | `200` |
| `GET` | `/health` | None | Server status, directory paths, and ledger size | `200` |
| `GET` | `/api/kpis` | None | Video availability and TTFB benchmarks | `200` |
| `GET` | `/api/assignments/history` | None | Complete persistent assignment ledger history | `200` |
| `DELETE`| `/api/assignments/reset` | `X-API-KEY` | Clears persistent assignment history ledger | `200` |
| `GET` | `/api/activity/latest` | Localhost only | Returns recent events for live dashboard | `200`, `403` |
| `GET` | `/api/logs/stream` | Localhost only | Server-Sent Events (SSE) server log stream | `200`, `403` |
| `GET` | `/` or `/dashboard` | Localhost only | Clinical operations web console | `200`, `403` |
| `GET` | `/favicon.ico` | None | Empty 204 No Content response | `204` |

---

## 3. CPAP AI Supervisor Server routes (`core/server.py`)

### Primary port 8000 endpoints

| Method | Path | Auth Header | Description | Status Codes |
| :--- | :--- | :---: | :--- | :---: |
| `GET` | `/` | None | Content-negotiated: Serves HTML dashboard or JSON info | `200` |
| `GET` | `/dashboard` | None | Single-page clinical dashboard | `200` |
| `GET` | `/health` | None | Health check: pipeline state, models, Video VM ping | `200` |
| `GET` | `/api/dashboard/stats` | None | Telemetry counts, active catalog, tracker stats | `200` |
| `GET` | `/api/dashboard/kpis` | None | Clinical adherence, risk, and alarm metrics | `200` |
| `GET` | `/api/server/logs` | None | In-memory log stream for dashboard console (`since_id`) | `200` |
| `GET` | `/api/patient/{patient_id}` | `X-API-KEY` | AI predictions and Scenario 1 video recommendation | `200`, `404` |
| `GET` | `/api/patient/{patient_id}/playlist`| `X-API-KEY` | Scenario 2 virtual playlist sequence | `200`, `404` |
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

### Secondary port 8001 endpoints (catalog sync listener)

| Method | Path | Auth Header | Description | Status Codes |
| :--- | :--- | :---: | :--- | :---: |
| `POST` | `/api/triggers/sync` | `X-API-KEY` / `X-ML-Key` | Webhook receiver updating local catalog cache | `200`, `401`, `500` |
| `GET` | `/health` | None | Health check for port 8001 daemon | `200` |

---

## 4. Central Clinical Backend endpoints (VM2 reference)

| Method | Path | Auth Header | Caller | Description | Status Codes |
| :--- | :--- | :---: | :---: | :--- | :---: |
| `POST` | `/api/videos/{patient_id}/assign` | `X-Video-Server-Key` | Video VM | Pushes assigned coaching video and step transitions | `200`, `403`, `500` |
| `POST` | `/api/telemetry/event-trace` | `X-API-Key` | Pi & VM4 | Logs timing timestamps ($t_0$ to $t_7$) and latency | `200`, `401`, `500` |
| `POST` | `/api/data/predictions` | `X-ML-Key` | AI Server | Ingests ML risk scores ($z\_risk$) and action plans | `200`, `401`, `500` |
| `GET` | `/api/data/cpap-usage` | `X-ML-Key` | AI Server | Telemetry stream query for model training | `200`, `401` |

See [STATE.md](STATE.md) for data persistence details.
