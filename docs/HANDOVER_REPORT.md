# SleepCare CPAP Ecosystem: Technical Handover Report

> DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France  
> Project: Just-in-Time Clinical Video Coaching and Multimodal AI Telemonitoring for CPAP Therapy  
> Author: Pamit Duggal (Software and AI Engineering Intern)  
> Date: September 2026  
> Intended readers: Incoming software and AI engineering interns, research engineers, and clinical system administrators

---

## 1. Project context and handover scope

I wrote this report to give the next engineering intern a clear, unfiltered view of what is running, why we built it this way, and where the traps are.

SleepCare addresses a practical failure point in sleep apnea treatment. Continuous Positive Airway Pressure (CPAP) works well clinically, but nearly half of patients stop using their machine within the first year. They run into mask leaks, nasal soreness, or pressure discomfort, get frustrated, and leave the device in a closet. Routine clinical check-ups happen months too late to catch this.

Our goal was to close that feedback loop. When a patient syncs their device data in the morning, our system evaluates the previous night across 37 clinical rules on a local edge node. If something went wrong, the patient receives a short, targeted coaching video explaining how to adjust their strap, clean their mask, or change their humidifier setting. For broader cohort management, an AI server tracks 41,117 patients across seven analytical layers, identifying individuals heading toward therapy abandonment and queuing clinical phone calls or visits.

We demonstrated this entire closed-loop system live to our consortium partners in Berlin, running over simulated 5G Quality on Demand network slices. The cohort analysis showed a 90.12% CMS compliance rate.

![SleepCare Architecture](images/sleepcare_architecture.jpg)

---

## 2. Documentation index

I split our system documentation into separate reference guides in this `docs/` folder:

| Document | Scope |
| :--- | :--- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Multi-node topology, sequence diagrams, and latency budget from phone ingest to video start. |
| [COMPONENTS.md](COMPONENTS.md) | Deep dive into the Raspberry Pi edge node, Video VM, AI Supervisor, and Central Backend. |
| [CODEBASE_MAP.md](CODEBASE_MAP.md) | File-by-file inventory of scripts, configurations, models, and assets across all three codebases. |
| [API.md](API.md) | Request and response formats for data ingestion, video streaming, catalog sync, and ML triggering. |
| [ROUTES.md](ROUTES.md) | Endpoint catalog with HTTP verbs, authentication headers, and status codes. |
| [STATE.md](STATE.md) | JSON ledgers, deduplication prompt cache, trigger matrices, and atomic file-swap logic. |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production setup, environment configuration, Windows batch files, and systemd units. |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local test suite execution, adding new coaching videos, and rule modification procedures. |

---

## 3. Server node inventory

Our testbed spans three active computing nodes communicating across private LAN and VPN connections:

```text
+--------------------------------+-------------------------------+------------------------------+
| Node and Directory             | Network Address and Ports     | Primary Responsibility       |
+--------------------------------+-------------------------------+------------------------------+
| 1. Raspberry Pi 5 Edge Node    | LAN: 192.168.x.x:8000         | Evaluates nightly CSVs,      |
|    (CPAP_Raspberry_Pi)         | Public: Tailscale Funnel      | runs 37 clinical rules,      |
|                                | Bind: 0.0.0.0:8000            | measures client RTT.         |
+--------------------------------+-------------------------------+------------------------------+
| 2. CPAP Video Server (VM4)     | Host: 159.84.143.246:8080     | Serves 39 1080p MP4 videos   |
|    (CPAP_Video_Server)         | Bind: 0.0.0.0:8080            | and 78 WebVTT subtitles over |
|                                | Web UI: http://localhost:8080 | HTTP 206 byte ranges.        |
+--------------------------------+-------------------------------+------------------------------+
| 3. AI Supervisor Server (VM3)  | Host: 159.84.143.151:8000     | 7-layer ML pipeline across   |
|    (CPAP_AI_Server)            | Daemon: 159.84.143.151:8001   | 41,117 patients; catalog     |
|                                | Bind: 0.0.0.0:8000, :8001     | sync listener on port 8001.  |
+--------------------------------+-------------------------------+------------------------------+
| 4. Central Clinical Backend    | Host: 159.84.143.151:80       | PostgreSQL DB_Clinical,      |
|    (VM2 Reference Node)        | (External VM managed by team) | clinician web portal.        |
+--------------------------------+-------------------------------+------------------------------+
```

---

## 4. Key milestones achieved

Here is what we completed and verified during the internship:

1. **Edge triage engine**:
   - Wrote a Python triage engine (`edge_detection.py`) that runs in under 6 milliseconds on the Raspberry Pi 5.
   - Handled 37 clinical triggers: Videos 1 to 27 cover standard CPAP machine metrics (leak rate, residual AHI, hours of use), while Videos 28 to 37 monitor continuous wearable inputs (Withings ScanWatch, Masimo pulse oximetry, Hexoskin smart shirts, and Somno-Art EEG headbands).
   - Built a two-phase telemetry reporting loop (`/ingest` followed by `/timing/{id}`) that captures real client roundtrip latency and writes trace metrics into the clinical database (`DB_Clinical.telemetry.event_traces`).

2. **Media streaming and playlist sequencing**:
   - Indexed 39 Full HD (1080p, 30fps) coaching videos and authored 78 matching WebVTT subtitle files (full parity across French and English).
   - Configured FastAPI with chunked HTTP 206 Partial Content streaming, keeping initial byte latency under 5 milliseconds on our network tests.
   - Built virtual playlist stitching for Scenario 2: rather than re-encoding two MP4 files together on the server, the server delivers an ordered JSON playlist and the client web player executes a clean 1.5-second crossfade (`fade_1_5s`), bypassing server rendering bottlenecks.

3. **Deduplication shield for generative video**:
   - For Scenario 3 (on-demand video synthesis with Google Veo 3.1), cloud API calls are slow and expensive. I built a three-tier deduplication filter in `deduplication_engine.py`. It first checks an MD5 hash of the clinical prompt, then searches a slug lookup table, and finally compares semantic keywords. If an identical clip was generated earlier, it returns the cached video in less than one millisecond.
   - Created an atomic `AssignmentLedger` using file swaps to prevent duplicate video prescriptions from reaching the same patient.

4. **Machine learning supervisor**:
   - Packaged the end-to-end analytical pipeline (`M4_FINAL_F2.ipynb` and `core/pipeline.py`) across 41,117 patient records.
   - Configured statistical control charts (CUSUM and EWMA) for sudden shifts, gradient boosted decision trees for 30-day dropout risk, Cox proportional hazards for long-term survival, and uplift models to decide whether video, telephone, or in-person outreach works best.
   - Implemented a two-port service design (port 8000 for the clinician dashboard, port 8001 for background catalog sync webhooks) with a port cleanup utility (`scripts/clear_ports.py`) that prevents socket collisions during server restarts on Windows.

---

## 5. Security and credentials

We took care to sanitize the entire codebase before publishing this repository. Production API keys have been removed and replaced with environment variables:

| Variable | Location | Caller and Destination | Purpose |
| :--- | :--- | :--- | :--- |
| `API_KEY` | `CPAP_Raspberry_Pi/.env` | Mobile Phone -> Pi Edge | Protects `POST /ingest` and `POST /timing` |
| `SERVER_API_KEY` | `CPAP_Video_Server/.env` | Pi Edge & AI Server -> Video VM | Protects `POST /api/orchestrate` and `/api/vertex-generate` |
| `VIDEO_SERVER_KEY` | `CPAP_Video_Server/.env` | Video VM -> Central VM2 | Signs video assignment webhooks |
| `BACKEND_API_KEY` | `CPAP_AI_Server/.env` | AI Server & Video VM -> Central VM2 | Authorizes telemetry and prediction pushes |
| `AI_SERVER_API_KEY` | `CPAP_AI_Server/.env` | Clinician clients -> AI Server | Authorizes pipeline execution requests |
| `GOOGLE_VERTEX_API_KEY` | `CPAP_Video_Server/.env` | Video VM -> Google Cloud | Authorizes Veo 3.1 video generation |

Keep your active `.env` files out of Git. Use `.env.example` as a template whenever setting up a new environment.

---

## 6. Practical engineering notes and watchouts

These are specific quirks I encountered during development that will save you hours of debugging:

1. **The `pressure90` column name on the edge node**:
   The patient mobile app exports CPAP pressure as `pressure90` in lowercase. In `edge_detection.py`, earlier code checked for `Presure90` (with a single 's') or `pressure`. If the incoming CSV only contains `pressure90`, the parser falls back to `0.0`. This means pressure-dependent rules (such as Videos 4, 7, 10, and 11) will not fire on raw phone data unless `pressure90` is explicitly handled. Adding that field to the column tuple in `edge_detection.py` is an immediate easy win.

2. **Mobile app sending legacy `POST /event`**:
   We removed the old `POST /event` endpoint on the Pi in early September in favor of the cleaner `/ingest` plus `/timing` workflow. Certain test builds of the mobile phone app still attempt to send data to `/event` after logging timing. The phone will display an error message even though the ingestion was successful. You will need to coordinate with the mobile team to remove that dead call.

3. **Video server dashboard access restrictions**:
   If you try opening `http://159.84.143.246:8080/dashboard` directly in your laptop browser, you will get an HTTP 403 Forbidden error. This is intentional; external requests are blocked for security. To view the dashboard remotely, set up an SSH port forward:
   ```bash
   ssh -L 8080:localhost:8080 user@159.84.143.246
   ```
   Then open `http://localhost:8080/dashboard` locally.

4. **Vertex AI quota ceilings**:
   Rendering new video clips with Google Veo 3.1 consumes substantial GPU quotas. If your Google Cloud project hits its limit, Vertex returns an HTTP 429 quota error. Our deduplication engine handles this by falling back to pre-existing video clips whenever possible.

5. **Windows socket collisions**:
   On Windows Server 2022, Uvicorn occasionally holds onto port 8000 after an unexpected terminal close. If you try restarting the server immediately, Python throws a `WinError 10048` (address already in use). We added `scripts/clear_ports.py` to the startup batch script to identify the orphaned PID and terminate it before launching.

---

## 7. Recommended next steps

If you are continuing development on SleepCare, here is where I recommend starting:

1. **Pressure column normalization**: Update `CPAP_Raspberry_Pi/edge_detection.py` to resolve `pressure90` and verify the change with `test_csv/verify.py`.
2. **Asynchronous job handling for video generation**: At present, `POST /api/vertex-generate` holds the HTTP connection open while the cloud model renders the video. If the video takes longer than 20 seconds, the request risks timing out. Switching this to a background queue with a status check endpoint (`GET /api/vertex-generate/status/{job_id}`) would make this much more reliable.
3. **Database upsert hardening**: On the central VM2 backend, ensure the telemetry ingestion query uses `ON CONFLICT (event_id) DO UPDATE` to avoid occasional primary key conflicts between Phase 1 and Phase 2 pushes.
4. **Dynamic trigger updates on the Pi**: Currently, changing a rule on the Pi requires modifying `edge_detection.py`. Updating `sync_catalog.py` to evaluate rule conditions dynamically from `metadata/*.json` would allow clinicians to deploy new rules without touching Python code.

---

## 8. Reference contacts

- **Academic Supervisor**: DISP Laboratory, Université Lumière Lyon 2 / INSA Lyon
- **Industrial Partner**: Linde HomeCare France
- **Server hardware details**:
  - Edge Node: Raspberry Pi 5 (Debian 12 Bookworm, aarch64)
  - VM3 (AI Supervisor): Windows Server 2022 (`159.84.143.151`)
  - VM4 (Video Server): Windows Server 2022 (`159.84.143.246`)
  - VM2 (Central Database): Ubuntu Linux (`159.84.143.151:80`)

Next, read [ARCHITECTURE.md](ARCHITECTURE.md) for the end-to-end telemetry flow.
