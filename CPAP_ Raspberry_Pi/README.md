# CPAP Just-in-Time Video Coaching — Raspberry Pi Edge Service

FastAPI service running on the Raspberry Pi 5 edge node.

DISP Laboratory Lyon / Linde HomeCare France.

The Pi sits in the middle of a three-party system:

```
  phone app  ──POST /ingest (CSV)──▶   ┌─────────────┐  ──POST /api/orchestrate──▶  Video VM
             ──POST /event  (JSON)──▶  │  Pi (:8000) │                              (renders +
                                       │   app.py    │                               serves clips)
  dashboard  ◀──GET /patient/{id}/coaching                                                │
             ──POST /patient/{id}/clear──▶ └──────────┘                                   │
                                                                                     patient sees video
```

The Pi **detects, decides, and forwards**. It does not render or serve video
files — the Video VM does that. It also never pushes to the central telemetry
database; all patient data arrives *inbound* from the phone.

---

## Layout

| Path | What it is |
|---|---|
| `app.py` | The service. Routes, auth, rate limiting, logging, the Video VM push. |
| `edge_detection.py` | Threshold triage over a raw CPAP/biomarker CSV → an event dict (or `None`). |
| `load_library.py` | Loads the video metadata registry at startup and implements `select_video()` (the three scenarios). |
| `metadata/` | 27 records `video_01..27.json` plus `master_video_metadata.json` (skipped by the loader). Indexed by `video_id`, `trigger_type`, and clinical tag. |
| `data/ingest/` | Raw CSVs POSTed to `/ingest`, kept for audit. |
| `data/withings/` | Wearable CSV snapshots that arrived on `/event`, as `<patient_id>_<ts>.csv`. |
| `logs/events/` | One JSON file per `/ingest` transaction, named by `event_id`. |
| `logs/detected_events_and_video_requests.log` | Append-only human-readable log of anomalies, assignments, and dashboard fetches. |
| `test_csv/` | Fixture CSVs and `run_tests.sh` for exercising the pipeline. |
| `config.py` | **Dead code** — nothing imports it. Its `127.0.0.1` defaults are never evaluated; ignore them. |

There is no `main.py` and no `library/` directory. Earlier revisions of this
README referenced both.

## Run

```bash
cd ~/Desktop/CPAP_Edge_copy
pip install -r requirements.txt          # fastapi uvicorn requests pandas python-multipart slowapi python-dotenv
uvicorn app:app --host 0.0.0.0 --port 8000
```

Binds `0.0.0.0` deliberately — the Tailscale tunnel and other devices on the LAN
must reach it. `.env` is loaded on import.

Nothing supervises this process: there is no systemd unit and no cron entry, so
it dies with the terminal that started it. Check what is actually serving before
concluding a code change took effect:

```bash
ps aux | grep uvicorn      # confirm the path it was launched from
```

## Configuration (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `API_KEY` | `osa-demo` | Shared secret the phone and dashboard must send as `X-API-Key`. |
| `VIDEO_VM_URL` | `http://159.84.143.246:8080` | Video VM base URL. Trailing slash stripped. |
| `VIDEO_SERVER_API_KEY` | *(empty)* | Sent to the Video VM as `X-API-KEY`. Must equal `SERVER_API_KEY` on the VM host, or it answers `403`. |
| `GOOGLE_VERTEX_API_KEY` | placeholder | Vertex AI (Veo) key, embedded in the scenario 3 request. |
| `GOOGLE_CLOUD_PROJECT` | — | `cpap-coaching-project`. |
| `GOOGLE_CLOUD_LOCATION` | — | `us-central1`. |
| `LIBRARY_ROOT` | `.` | Where to find metadata. The loader tries `<root>/*.json`, `<root>/metadata/*.json`, then `metadata/*.json`. |
| `LOG_DIR` | `logs` | Human-readable log destination. |
| `EVENT_LOG_DIR` | `logs/events` | Per-transaction JSON records. |
| `INGEST_DATA_DIR` | `data/ingest` | Saved raw upload CSVs. |
| `WITHINGS_DATA_DIR` | `data/withings` | Saved wearable CSVs. |

`.env` holds live credentials — keep it out of any copy you share. A Vertex key
is also hardcoded as a fallback default in `load_library.py`; treat it as a
secret to rotate, not as an example to copy.

## Auth and rate limiting

Every route except `/health` requires `X-API-Key: <API_KEY>`; wrong or missing
gives `401`. Comparison is constant-time (`hmac.compare_digest`).

Rate limits are per-caller, keyed by a hash of the API key when one is present
and by `X-Forwarded-For`/peer address otherwise. This matters behind Tailscale
Funnel: `tailscaled` terminates the connection on the Pi and proxies to
localhost, so a naive remote-address key would put every caller on the internet
into one `127.0.0.1` bucket and let a stranger exhaust the phone's allowance.

| Route | Limit |
|---|---|
| `POST /ingest`, `POST /event` | 20/minute |
| `POST /patient/{id}/clear`, `POST /timing/{id}`, `GET /health` | 60/minute |
| `GET /patient/{id}/coaching` | 120/minute |

CORS is currently wide open (`allow_origins=["*"]`). Fine for the demo; tighten
before anything resembling production.

## API

### `POST /ingest` — raw telemetry CSV (the endpoint actually in use)

`multipart/form-data`: `file` (CSV, required), `patient_id`, `language` (default
`en`), and `sent_at` — the phone's clock stamped right before the upload, sent
either as a form field or the `X-Sent-At` header. Both `sent_at` forms are
optional; without one the transit KPI is reported as unavailable rather than
guessed.

The Pi saves the CSV, runs `edge_detection.detect_event()`, and on a hit selects
a video, queues it for the dashboard, pushes it to the Video VM, and writes a
`logs/events/<event_id>.json` record.

Quiet telemetry short-circuits:

```json
{"event": false, "message": "Normal telemetry — no coaching required", "ingest_saved": "..."}
```

On a detection:

```json
{"event": true, "detected": {...}, "decision": {...},
 "video_vm_orchestrate": {...}, "ingest_saved": "...",
 "event_id": "005e189a-…", "processing_ms": 265.4}
```

Keep `event_id` — `/timing` needs it.

### `POST /event` — pre-detected events + wearable snapshot

Used when the phone has already done the detection. Accepts one event object or
a batch under `events`:

```json
{
  "events": [
    { "patient_id": "P001", "event": "mask_leak", "severity": "high",
      "data": { "AtHomePatientId": "P001", "Leaks95": "31", "AHI": "8", "Use": "5.1", "ts": "..." } }
  ],
  "sent_at": "2026-07-19T10:00:00.000Z",
  "withings_patient_id": "48560663",
  "withings_devices": { "<deviceid>": "BPM Connect" },
  "withings_csv": "date,measurement,value,unit,device,type\n2026-07-19T10:00:00.000Z,Diastolic BP,72,mmHg,BPM Connect,9"
}
```

`event` maps to `trigger_type`; `data` is kept as `metrics`. Each item gets a
video decision and a Video VM push. The `withings_*` fields are the phone's own
on-device Withings pull riding along in the *same* request as the event —
coherent with it, not a separate call. They are optional, and when present the
CSV is written to `data/withings/<patient_id>_<ts>.csv`.

```json
{"received": 1, "results": [...], "withings_patient_id": "48560663",
 "withings_saved": "...", "latency_ms": 358.6, "clock_offset_ms": 0.0}
```

This route is deliberately **silent on the console** and writes no per-event
file under `logs/events/`: the app posts its whole export in one call, and 100+
anomaly banners buried every `/ingest` transaction. Its records still land in
the append-only log in full.

### `GET /patient/{patient_id}/coaching` — dashboard polling

```json
{"pending": true, "decision": { "scenario": "scenario_1_single", "title": "...", ... }}
```

Returns `{"pending": false, "decision": null}` when nothing is queued. The first
successful poll stamps `frontend_fetched_at` on the event record; later polls do
not move it.

### `POST /patient/{patient_id}/clear` — mark watched

Pops the pending decision and stamps `frontend_cleared_at`. → `{"cleared": "<id>"}`

### `POST /timing/{event_id}` — phone reports the round trip

Body `{"rtt_ms": <number>}`. See the KPI section below. `422` without a numeric
`rtt_ms`, `404` for an unknown `event_id`.

### `GET /health` — no auth

```json
{"status": "ok", "service": "telemetry-pi", "version": 2, "total_indexed_videos": 27}
```

`"service": "telemetry-pi"` is the marker the phone's LAN auto-discovery uses to
recognise the server.

## Video selection — the three scenarios

`select_video(event, LIBRARY)` in `load_library.py` resolves an event to a
`video_id` (directly, or via a `trigger_type` lookup) and returns one of:

**Scenario 1 — single event → single existing clip (~10s).** `action: "reuse"`.
Carries `video_filename`, subtitles for the requested language (falling back to
`en`), duration, topic, and safety level.

**Scenario 2 — two or more events → two clips stitched with a fade (~18.5s).**
`action: "stitch_dual"`. Clip order is checked against each record's
`composability.can_precede` and swapped when that gives better clinical
coherence. Returns `clip_1` and `clip_2`, each with its own filename, title, and
duration.

**Scenario 3 — partial match → existing clip + Vertex AI generation.**
`action: "generate_hybrid"`. Returns `existing_clip`, a 1.5s crossfade spec, and
a `vertex_ai_request` prompt payload (`google-vertex-veo`, 10s target,
`3D_medical_animation_clean`) for the VM to execute.

**No match.** `{"scenario": "none", "action": "none", "message": "No matching coaching video found in library."}` — `forward_to_video_vm` skips these.

## Downstream: the Video VM

This is the Pi's **only outbound HTTP call**:

```
POST {VIDEO_VM_URL}/api/orchestrate
Content-Type: application/json
X-API-KEY: {VIDEO_SERVER_API_KEY}     # omitted when unset — the VM then 403s
                                      # unless it is in open-access mode
```

```json
{"patient_id": "63678", "title": "...", "video_filename": "23_RadG_….mp4",
 "duration_s": 19, "category": "coaching", "trigger_reason": "...",
 "relevance": "high", "thumbnail_type": "technical"}
```

Two payload details are load-bearing:

- **`relevance` is clamped to `low|medium|high`.** Detection ranks events on a
  five-level scale internally (including `critical`, which scenario 2 sorts on
  to decide which clip leads). The dashboard rejects anything above `high`, so
  the mapping happens at this outbound boundary rather than by weakening the
  internal ranking.
- **`duration_s` is rounded to a whole second.** The dashboard's
  `/api/videos/{id}/assign` types it as an int and `422`s on a fraction — which
  is every scenario 2 decision (10 + 10 − 1.5 = 18.5). The decision itself keeps
  the true value for the stitcher and the logs.

A stitched decision adds `video_type: "package"` and a `clips` array, each entry
carrying its own `step`, `title`, `filename`, `duration_s`, subtitle URLs, and a
`transition` (`fade_1_5s` between clips, `end` on the last). `video_filename`
and the top-level `url` stay clip 1's, matching how the VM renders a package.

> **Known issue:** the Pi sends both clips correctly, but the Video VM currently
> drops `clip_2`, so the escalation half of a scenario 2 pair never reaches the
> patient. This is a VM-side fix, not a Pi-side one.

Failures here are logged and swallowed — a `403` or an unreachable VM does not
fail the `/ingest` request. Check the console for `[EDGE -> VIDEO VM WARNING]`.

## Latency KPI

Transit measured as *(Pi arrival − phone send)* is only as trustworthy as the
agreement between two clocks, and the phone's runs tens of ms ahead of the Pi's
— the same magnitude as the transit itself. So the real figure comes from a
round trip, where both stamps come from the phone's own clock and the offset
cancels:

1. `/ingest` returns `event_id` and `processing_ms`; the record is written with
   `transit_source: "pending_rtt"`.
2. The phone measures its own round trip and POSTs `{"rtt_ms": …}` to
   `/timing/{event_id}`.
3. The Pi subtracts everything it held the connection for — `processing_ms`
   **plus** `video_vm_push_ms`, since the VM hop is inside the phone's round
   trip too — halves the remainder for the one-way figure, and rewrites the
   record with `transit_source: "measured_rtt"`.

Omitting the VM hop from that subtraction misattributes ~300ms to network
transit and inflates the one-way figure roughly threefold.

`BUDGET_S = 60.0` (`app.py:135`) is the end-to-end target; each record carries
`budget_passed`.

One file per transaction, `logs/events/<event_id>.json`:

```json
{"event_id": "005e189a-…", "patient_id": "191831", "source": "ingest",
 "trigger_type": "radg_pulse_instability", "severity": "high",
 "metrics": {"radg_pr_var": true}, "signals_flagged": 1,
 "scenario": "scenario_1_single", "video_title": "RadG - Pulse or Breathing Instability",
 "video_filename": "23_RadG_Pulse_or_breathing_instability.mp4",
 "video_vm_push": "ok", "video_vm_push_ms": 265.4,
 "detected_at": "…", "sent_at": "…", "received_at": "…",
 "processing_ms": 265.4, "transit_source": "measured_rtt",
 "latency_ms": 1.7, "total_latency_ms": 267.1,
 "budget_s": 60.0, "budget_passed": true}
```

Derived figures are stored next to the raw stamps so a day can be aggregated
without re-deriving them from timestamps across thousands of files. `/event`
computes a `latency_ms` inline (with per-device clock-offset tracking) but
writes no per-transaction file.

## Expose across networks

The phone (cellular) and the Pi are on different networks behind NAT, so the Pi
needs a public front door. Preferred — Tailscale Funnel, which gives a stable
URL:

```bash
tailscale funnel 8000
```

Alternative: `ngrok http 8000`, but the free-tier URL changes on every restart,
so the phone's `RECEIVER_BASE_URL` needs updating each time.

Note that Funnel puts `/ingest` on the public internet. The API key is the only
thing in front of it — see the rate-limiting note above for why the bucket key
is not the peer address.

## Deploy on a fresh Pi

1. Copy `app.py`, `edge_detection.py`, `load_library.py`, `requirements.txt`,
   and the `metadata/` directory; `pip install -r requirements.txt`.
2. Write `.env` with at minimum `API_KEY`, `VIDEO_VM_URL`, and
   `VIDEO_SERVER_API_KEY` — plus the three `GOOGLE_*` vars if scenario 3 is in
   play. An `.env` with only `API_KEY` yields a Pi that reaches the Video VM and
   is refused with `403`.
3. `uvicorn app:app --host 0.0.0.0 --port 8000`.
4. Install Tailscale (`curl -fsSL https://tailscale.com/install.sh | sh`),
   `sudo tailscale up`, then `tailscale funnel 8000`.
5. Point the phone's `RECEIVER_BASE_URL` at the Funnel URL. Contract and app
   code stay identical.

## Testing checklist

1. `curl http://localhost:8000/health` → confirms the server runs and reports
   `total_indexed_videos: 27`. A `0` there means the metadata glob missed;
   check `LIBRARY_ROOT` and the working directory.
2. Open `https://<funnel-host>.ts.net/health` from the phone's browser →
   confirms the cross-network path.
3. `bash test_csv/run_tests.sh` → drives the fixture CSVs through `/ingest`.
4. In the app config screen, **Send Test Event** → expect HTTP 200 and a console
   banner on the Pi.
5. Only then **Analyze & Send** for real detected events.

Confirm the Video VM is actually reachable before blaming the pipeline:

```bash
curl -m 10 -o /dev/null -w '%{http_code}\n' http://159.84.143.246:8080/health
```

As of 2026-09-02 that host answers neither ICMP nor TCP from this Pi, though it
was serving successfully on 2026-08-31. When it is down, `/ingest` still
succeeds and the decision is still queued for the dashboard — only the push
fails, with a `[EDGE -> VIDEO VM WARNING]` line.
