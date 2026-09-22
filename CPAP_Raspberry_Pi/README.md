# CPAP Just-in-Time Video Coaching: Raspberry Pi Edge Service

FastAPI edge computing service for the patient-side Raspberry Pi 5.  
DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France.

---

## What this node does

The Pi runs right next to the patient. It receives raw CSV exports from the mobile companion app, checks for therapy problems against 37 clinical rules in under 6 milliseconds, and decides what video to show. It does not store or render video files; video streaming belongs to the Video VM. The Pi only figures out which clip the patient needs, orders it from the Video VM, and logs timing telemetry back to the central database.

Here is the operational loop:
1. The phone app sends a nightly CSV to `POST /ingest`.
2. `edge_detection.py` parses the newest therapy row and evaluates rule thresholds.
3. `load_library.py` selects an intervention: a single clip (Scenario 1), a dual-clip playlist sequence (Scenario 2), or a generative prompt (Scenario 3).
4. The Pi notifies the Video VM (`POST /api/orchestrate` or `POST /api/vertex-generate`).
5. When playback starts, the phone hits `POST /timing/{id}` so we can measure true roundtrip latency.

---

## Directory layout

```text
CPAP_Raspberry_Pi/
├── app.py                # FastAPI HTTP service (:8000), auth, ingest, and timing
├── edge_detection.py     # Rule engine evaluating the 37 clinical triggers
├── load_library.py       # Startup video catalog loader and scenario routing logic
├── sync_catalog.py       # Sync script pulling trigger updates from the Video VM
├── metadata/             # 37 individual video metadata files (video_01..37.json)
├── test_csv/             # Test fixtures and regression verification scripts
├── phone_csv/            # Sample CSV files formatted for mobile testing
└── .env.example          # Environment variable template
```

---

## Quick start

### 1. Configure environment
```bash
cp .env.example .env
```
Open `.env` and set `API_KEY` (must match the key configured on the phone), `VIDEO_SERVER_API_KEY`, and `BACKEND_API_KEY`.

### 2. Run the server
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Check the health endpoint:
```bash
curl -s http://localhost:8000/health
```

---

## Detailed documentation

To avoid duplicating technical details, detailed architecture and route tables live in `docs/`:

| Topic | Document |
| :--- | :--- |
| Multi-node topology and flow | [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) |
| Rule definitions and threshold logic | [docs/COMPONENTS.md](../docs/COMPONENTS.md) |
| File and module inventory | [docs/CODEBASE_MAP.md](../docs/CODEBASE_MAP.md) |
| API schemas and payload formats | [docs/API.md](../docs/API.md) |
| Route index and HTTP status codes | [docs/ROUTES.md](../docs/ROUTES.md) |
| Log files and event persistence | [docs/STATE.md](../docs/STATE.md) |
| Production deployment and Tailscale setup | [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) |
| Regression test scripts | [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) |
| Intern handover notes | [docs/HANDOVER_REPORT.md](../docs/HANDOVER_REPORT.md) |
