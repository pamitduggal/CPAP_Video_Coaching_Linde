# SleepCare CPAP Ecosystem: Unified REST API Manual

> DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France  
> Author: Pamit Duggal (Software and AI Engineering Intern)  
> Scope: REST endpoints, payloads, headers, and code examples

---

## 1. Network addresses and authentication

### Base URLs by node

| Node | Local Network URL | Production / Public URL |
| :--- | :--- | :--- |
| Raspberry Pi 5 Edge Node | `http://localhost:8000` | `http://192.168.x.x:8000` or `https://<funnel>.ts.net` |
| CPAP Video Server (VM4) | `http://localhost:8080` | `http://159.84.143.246:8080` |
| AI Supervisor Server (VM3) | `http://localhost:8000` | `http://159.84.143.151:8000` |
| AI Webhook Companion (VM3) | `http://localhost:8001` | `http://159.84.143.151:8001` |
| Central Clinical Backend (VM2)| Not applicable | `http://159.84.143.151:80` |

### Authentication headers

| Header Name | Expected Value | Used On |
| :--- | :--- | :--- |
| `X-API-Key` | Set in `CPAP_Raspberry_Pi/.env` | Pi Edge: `/ingest`, `/timing/{id}`, `/patient/{id}/*` |
| `X-API-KEY` | Set in `CPAP_Video_Server/.env` | Video VM: `/api/orchestrate`, `/api/vertex-generate`, `/api/catalog/rebuild` |
| `X-Video-Server-Key` | Set in `CPAP_Video_Server/.env` | Central Backend: `POST /api/videos/{patient_id}/assign` |
| `X-API-Key` | Set in `CPAP_AI_Server/.env` | Central Backend: `POST /api/telemetry/event-trace` |
| `X-ML-Key` | Set in `CPAP_AI_Server/.env` | Central Backend: `POST /api/data/predictions` |
| `X-API-KEY` | Set in `CPAP_AI_Server/.env` | AI Server: `/api/patient/{id}`, `/api/pipeline/run` |

---

## 2. Raspberry Pi edge endpoints

### Ingest nightly telemetry CSV (`POST /ingest`)
Receives a raw CSV file exported from the mobile app. The Pi extracts the newest row, evaluates the 37 rules, and triggers Video VM orchestration if an issue is found.

- Endpoint: `POST http://localhost:8000/ingest`
- Content type: `multipart/form-data`
- Header: `X-API-Key: <YOUR_EDGE_API_KEY>`

Form fields:
- `file`: Telemetry CSV file
- `patient_id` (string, required): For example, `"63678"`
- `language` (string, optional): `"en"` or `"fr"` (default: `"en"`)
- `sent_at` (string, optional): ISO-8601 client dispatch timestamp

Response when no coaching is required:
```json
{
  "event": false,
  "message": "Normal telemetry, no coaching required",
  "ingest_saved": "data/ingest/20260922_143000_63678.csv"
}
```

Response when an issue triggers an intervention:
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

### Report measured roundtrip time (`POST /timing/{event_id}`)
The mobile app hits this endpoint after the video player buffers, allowing the system to record real network transit time.

- Endpoint: `POST http://localhost:8000/timing/{event_id}`
- Content type: `application/json`
- Header: `X-API-Key: <YOUR_EDGE_API_KEY>`

Payload:
```json
{
  "rtt_ms": 342.8
}
```

Response:
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

## 3. Video Server orchestration endpoints (VM4)

### Orchestrate video coaching (`POST /api/orchestrate`)
Resolves video files for Scenario 1 (single clip) or Scenario 2 (stitched playlist), checks the assignment ledger, and notifies VM2.

- Endpoint: `POST http://159.84.143.246:8080/api/orchestrate`
- Content type: `application/json`
- Header: `X-API-KEY: <YOUR_VIDEO_SERVER_API_KEY>`

Supported payload variations:
1. By ID: `{"patient_id": "63678", "video_id": 29}`
2. By base filename: `{"patient_id": "63678", "video_filename": "14_Mask_style_change"}`
3. Full filename: `{"patient_id": "63678", "video_filename": "1_Mask_leak_adjust_straps.mp4"}`

Scenario 2 multi-clip request:
```json
{
  "event_id": "EVT_CPAP_2026_0922_01",
  "patient_id": "63678",
  "title": "Compound Leak and Discomfort Intervention",
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

Response (Scenario 2):
```json
{
  "status": "ok",
  "decision": {
    "event_id": "EVT_CPAP_2026_0922_01",
    "patient_id": "63678",
    "title": "Compound Leak and Discomfort Intervention",
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

Response when deduplication blocks a repeat:
```json
{
  "status": "already_assigned",
  "duplicate_detected": true,
  "message": "Video assignment already recorded in persistent ledger.",
  "dashboard_push": "skipped_duplicate"
}
```

---

## 4. Generative video synthesis (Scenario 3)

### On-demand video generation (`POST /api/vertex-generate`)
Renders an on-demand video using Google Cloud Veo 3.1 if the prompt is not already in the deduplication cache.

- Endpoint: `POST http://159.84.143.246:8080/api/vertex-generate`
- Content type: `application/json`
- Header: `X-API-KEY: <YOUR_VIDEO_SERVER_API_KEY>`

Payload:
```json
{
  "event_id": "EVT_GEN_2026_0922_01",
  "patient_id": "PATIENT_99412",
  "prompt": "Personalized 3D CPAP tubing repositioning during active sleep movement",
  "model": "veo-3.1-generate-preview",
  "duration_s": 10.0
}
```

Response when served from cache:
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

## 5. Media streaming endpoints

### Video stream (`GET /videos/{filename}`)
Streams MP4 video. Supports seeking through the standard `Range` header.

- Endpoint: `GET http://159.84.143.246:8080/videos/1_Mask_leak_adjust_straps.mp4`
- Range header: `Range: bytes=0-1048575` (requests the first 1 MB)
- Authentication: None (public read)

### WebVTT subtitles (`GET /subtitles/{filename}`)
Serves English or French subtitle files.

- Endpoint: `GET http://159.84.143.246:8080/subtitles/1_Mask_leak_adjust_straps.en.vtt`
- Content type: `text/vtt; charset=utf-8`
- Cache header: `Cache-Control: no-cache, no-store, must-revalidate, max-age=0`

---

## 6. Catalog synchronization

### Fetch trigger catalog (`GET /api/triggers/catalog`)
Returns the complete 39-video trigger matrix with boolean conditions and streaming URLs.

- Endpoint: `GET http://159.84.143.246:8080/api/triggers/catalog`
- Authentication: None

### Sync webhook listener (`POST /api/triggers/sync`)
Receiver on AI Server port 8001 and Pi Edge for automated catalog updates from VM4.

- Endpoint: `POST http://159.84.143.151:8001/api/triggers/sync`
- Headers: `X-API-KEY: <KEY>`, `X-ML-Key: <KEY>`

---

## 7. Working code examples

### Testing Scenario 1 with curl
```bash
curl -X POST http://159.84.143.246:8080/api/orchestrate \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <YOUR_KEY>" \
  -d '{"patient_id": "TEST_PATIENT", "video_id": 29, "trigger_reason": "CLI Test"}'
```

### Testing video byte-range in PowerShell
```powershell
Invoke-WebRequest -Uri "http://159.84.143.246:8080/videos/1_Mask_leak_adjust_straps.mp4" `
  -Headers @{ "Range" = "bytes=0-1024" } `
  -Method GET
```

### Python client example
```python
import requests

url = "http://159.84.143.246:8080/api/orchestrate"
headers = {
    "Content-Type": "application/json",
    "X-API-KEY": "<YOUR_KEY>"
}
payload = {
    "patient_id": "63678",
    "video_id": 1,
    "trigger_reason": "Elevated mask leak detected"
}

response = requests.post(url, json=payload, headers=headers, timeout=5.0)
print(response.json())
```

See [ROUTES.md](ROUTES.md) for the complete endpoint reference table.
