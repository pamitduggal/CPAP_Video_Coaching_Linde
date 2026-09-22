# SleepCare CPAP Ecosystem — Unified REST API Manual

> **DISP Laboratory (Lyon) & Linde HomeCare France**  
> *Author: Pamit Duggal (Software & AI Engineering Intern)*  
> *Scope: Multi-Node API Interfaces, Schemas & Working Code Samples*

---

## 1. Global API Architecture & Conventions

### Base URLs by Target Node

| Subsystem Node | Local Network URL | Production / Public URL |
| :--- | :--- | :--- |
| **Raspberry Pi 5 Edge Node** | `http://localhost:8000` | `http://192.168.x.x:8000` or `https://<funnel>.ts.net` |
| **CPAP Video Server (VM4)** | `http://localhost:8080` | `http://159.84.143.246:8080` |
| **AI Supervisor Server (VM3)** | `http://localhost:8000` | `http://159.84.143.151:8000` |
| **AI Webhook Companion (VM3)** | `http://localhost:8001` | `http://159.84.143.151:8001` |
| **Central Clinical Backend (VM2)**| — | `http://159.84.143.151:80` |

### Standard Authentication Headers Matrix

| Header Key | Expected Value | Used For Endpoints |
| :--- | :--- | :--- |
| `X-API-Key` | `<YOUR_EDGE_API_KEY>` | Pi Edge: `/ingest`, `/timing/{id}`, `/patient/{id}/*` |
| `X-API-KEY` | `<YOUR_VIDEO_SERVER_API_KEY>` | Video VM: `/api/orchestrate`, `/api/vertex-generate`, `/api/catalog/rebuild` |
| `X-Video-Server-Key` | `<YOUR_VIDEO_SERVER_KEY>` | Central Backend: `POST /api/videos/{patient_id}/assign` |
| `X-API-Key` | `<YOUR_BACKEND_API_KEY>` | Central Backend: `POST /api/telemetry/event-trace` |
| `X-ML-Key` | `<YOUR_BACKEND_API_KEY>` | Central Backend: `POST /api/data/predictions` |
| `X-API-KEY` | `<YOUR_AI_SERVER_API_KEY>` | AI Server: `/api/patient/{id}`, `/api/pipeline/run` |

---

## 2. Edge Ingestion & Telemetry APIs (Raspberry Pi 5)

### 2.1 Ingest Nightly Telemetry CSV (`POST /ingest`)
Uploads a patient telemetry CSV from the mobile app. The Pi extracts the newest night, evaluates 37 anomaly rules, and triggers Video VM orchestration if an event is detected.

- **URL**: `POST http://localhost:8000/ingest`
- **Content-Type**: `multipart/form-data`
- **Header**: `X-API-Key: <YOUR_EDGE_API_KEY>`

#### Form Fields:
- `file`: The raw telemetry CSV file.
- `patient_id` (string, required): e.g. `"63678"`.
- `language` (string, optional): `"en"` or `"fr"` (default: `"en"`).
- `sent_at` (string, optional): ISO-8601 client dispatch timestamp (e.g. `2026-09-22T14:30:00.000Z`).

#### Response (Quiet Night — No Coaching):
```json
{
  "event": false,
  "message": "Normal telemetry — no coaching required",
  "ingest_saved": "data/ingest/20260922_143000_63678.csv"
}
```

#### Response (Anomaly Flagged — Coaching Dispatched):
```json
{
  "event": true,
  "event_id": "005e189a-32df-42fa-8761-4148b3b70821",
  "processing_ms": 5.5,
  "detected": {
    "trigger_type": "mask_leak",
    "severity": "medium",
    "video_id": 1,
    "metrics": {
      "leaks95": 26.4,
      "usage_hours": 6.8,
      "ahi": 3.2
    }
  },
  "decision": {
    "action": "reuse",
    "scenario": "scenario_1_single",
    "video_id": 1,
    "video_filename": "1_Mask_leak_adjust_straps.mp4",
    "title": "Adjust Mask Straps",
    "duration_s": 10
  },
  "video_vm_orchestrate": {
    "status": "ok",
    "dashboard_push": "success"
  },
  "ingest_saved": "data/ingest/20260922_143000_63678.csv"
}
```

### 2.2 Report Measured Roundtrip Time (`POST /timing/{event_id}`)
Reports the client-observed roundtrip time for the `/ingest` transaction to calculate true transit latency.

- **URL**: `POST http://localhost:8000/timing/{event_id}`
- **Content-Type**: `application/json`
- **Header**: `X-API-Key: <YOUR_EDGE_API_KEY>`

#### Request Payload:
```json
{
  "rtt_ms": 342.8
}
```

#### Response:
```json
{
  "status": "recorded",
  "event_id": "005e189a-32df-42fa-8761-4148b3b70821",
  "transit_latency_ms": 28.5,
  "total_latency_ms": 356.6,
  "budget_passed": true
}
```

---

## 3. Video Orchestration & Dynamic Resolution APIs (Video Server VM4)

### 3.1 Orchestrate Video Coaching (`POST /api/orchestrate`)
Resolves media assets for Scenario 1 (single clip) or Scenario 2 (virtual sequence stitching), checks the persistent assignment ledger, and pushes the intervention to VM2.

- **URL**: `POST http://159.84.143.246:8080/api/orchestrate`
- **Content-Type**: `application/json`
- **Header**: `X-API-KEY: <YOUR_VIDEO_SERVER_API_KEY>`

#### Flexible Inputs Supported:
1. Numeric ID: `{"patient_id": "63678", "video_id": 29}`
2. Extensionless string: `{"patient_id": "63678", "video_filename": "14_Mask_style_change"}`
3. Exact MP4: `{"patient_id": "63678", "video_filename": "1_Mask_leak_adjust_straps.mp4"}`

#### Stitched Sequence Request (Scenario 2):
```json
{
  "event_id": "EVT_CPAP_2026_0922_01",
  "patient_id": "63678",
  "title": "Compound Leak & Discomfort Intervention",
  "clips": [
    {
      "video_id": 1,
      "title": "Adjust Mask Straps",
      "transition": "fade_1_5s"
    },
    {
      "video_id": 4,
      "title": "Activate Ramp Mode",
      "transition": "fade_1_5s"
    }
  ]
}
```

#### Response (Scenario 2 Success):
```json
{
  "status": "ok",
  "decision": {
    "event_id": "EVT_CPAP_2026_0922_01",
    "patient_id": "63678",
    "title": "Compound Leak & Discomfort Intervention",
    "video_filename": "1_Mask_leak_adjust_straps.mp4",
    "url": "http://159.84.143.246:8080/videos/existing/1_Mask_leak_adjust_straps.mp4",
    "subtitle_en_url": "http://159.84.143.246:8080/subtitles/1_Mask_leak_adjust_straps.en.vtt",
    "subtitle_fr_url": "http://159.84.143.246:8080/subtitles/1_Mask_leak_adjust_straps.fr.vtt",
    "duration_s": 18.5,
    "scenario": "scenario_2_stitched_sequence",
    "sequence_count": 2,
    "transition_type": "fade_1_5s",
    "clips": [
      {
        "step": 1,
        "video_id": 1,
        "title": "Adjust Mask Straps",
        "duration_s": 10.0,
        "url": "http://159.84.143.246:8080/videos/existing/1_Mask_leak_adjust_straps.mp4",
        "transition": "fade_1_5s"
      },
      {
        "step": 2,
        "video_id": 4,
        "title": "Activate Ramp Mode",
        "duration_s": 10.0,
        "url": "http://159.84.143.246:8080/videos/existing/4_Low_usage_ramp_mode.mp4",
        "transition": "fade_1_5s"
      }
    ],
    "vm_processing_ms": 2.15
  },
  "dashboard_push": "success"
}
```

#### Response (Deduplication Shield Active):
```json
{
  "status": "already_assigned",
  "duplicate_detected": true,
  "message": "Video assignment already recorded in persistent ledger.",
  "dashboard_push": "skipped_duplicate"
}
```

---

## 4. Generative AI Video Synthesis (Scenario 3)

### 4.1 On-Demand Video Generation (`POST /api/vertex-generate`)
Dispatches on-demand generative video synthesis to Google Cloud Veo 3.1, guarded by the 3-Level Pre-Gen Deduplication Shield.

- **URL**: `POST http://159.84.143.246:8080/api/vertex-generate`
- **Content-Type**: `application/json`
- **Header**: `X-API-KEY: <YOUR_VIDEO_SERVER_API_KEY>`

#### Request Payload:
```json
{
  "event_id": "EVT_GEN_2026_0922_01",
  "patient_id": "PATIENT_99412",
  "prompt": "Personalized 3D CPAP tubing repositioning during active sleep movement",
  "model": "veo-3.1-generate-preview",
  "duration_s": 10.0
}
```

#### Response (Level 3 Deduplication Cache Hit):
```json
{
  "status": "success",
  "event_id": "EVT_GEN_2026_0922_01",
  "scenario": "scenario_3_hybrid_generated",
  "generated_video_filename": "39_Humidifier_Tube_Adjustment_Animation.mp4",
  "bucket": "new_videos",
  "url": "http://159.84.143.246:8080/videos/new/39_Humidifier_Tube_Adjustment_Animation.mp4",
  "cache_hit": true,
  "deduplication_shield": {
    "active": true,
    "matched_title": "Humidifier Tube Adjustment Animation",
    "match_reason": "Level 3: Full Metadata Semantic Match"
  },
  "vm_processing_ms": 11.4
}
```

---

## 5. Streaming & Media Endpoints (Video Server VM4)

### 5.1 HTTP 206 Partial Content Video Stream (`GET /videos/{filename}`)
Streams 1080p MP4 videos across `existing_videos/` and `new_videos/`. Supports random seeking via `Range: bytes=X-Y`.

- **URL**: `GET http://159.84.143.246:8080/videos/1_Mask_leak_adjust_straps.mp4`
- **Header (Optional)**: `Range: bytes=0-1048575` (requests first 1 MB)
- **Auth**: Public Read

### 5.2 Zero-Cache WebVTT Subtitles (`GET /subtitles/{filename}`)
Serves bilingual WebVTT subtitle files (`.en.vtt` or `.fr.vtt`) with strict zero-cache headers.

- **URL**: `GET http://159.84.143.246:8080/subtitles/1_Mask_leak_adjust_straps.en.vtt`
- **Content-Type**: `text/vtt; charset=utf-8`
- **Cache-Control**: `no-cache, no-store, must-revalidate, max-age=0`

---

## 6. Catalog Synchronization & Webhooks

### 6.1 Query Trigger Catalog (`GET /api/triggers/catalog`)
Returns the complete 39-video distributed trigger catalog with boolean logic and streaming URLs.

- **URL**: `GET http://159.84.143.246:8080/api/triggers/catalog`
- **Auth**: Public Read

### 6.2 Inbound Catalog Sync Webhook (`POST /api/triggers/sync`)
Receiver on AI Server Port 8001 and Pi Edge for automated catalog broadcasts from VM4.

- **URL**: `POST http://159.84.143.151:8001/api/triggers/sync`
- **Header**: `X-API-KEY: <YOUR_VIDEO_SERVER_API_KEY>`
- **Header**: `X-ML-Key: <YOUR_BACKEND_API_KEY>`

---

## 7. Operational Code Recipes (curl, PowerShell, Python)

### 7.1 Testing Scenario 1 via curl
```bash
curl -X POST http://159.84.143.246:8080/api/orchestrate \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <YOUR_VIDEO_SERVER_API_KEY>" \
  -d '{"patient_id": "TEST_PATIENT", "video_id": 29, "trigger_reason": "Live API Test"}'
```

### 7.2 Testing Video Range Stream via PowerShell
```powershell
Invoke-WebRequest -Uri "http://159.84.143.246:8080/videos/1_Mask_leak_adjust_straps.mp4" `
  -Headers @{ "Range" = "bytes=0-1024" } `
  -Method GET
```

### 7.3 Python Orchestration Client Example
```python
import requests

url = "http://159.84.143.246:8080/api/orchestrate"
headers = {
    "Content-Type": "application/json",
    "X-API-KEY": "<YOUR_VIDEO_SERVER_API_KEY>"
}
payload = {
    "patient_id": "63678",
    "video_id": 1,
    "trigger_reason": "Elevated mask leak detected"
}

response = requests.post(url, json=payload, headers=headers, timeout=5.0)
print(response.json())
```

---

*Proceed to [ROUTES.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/ROUTES.md) for an exhaustive route-by-route table.*
