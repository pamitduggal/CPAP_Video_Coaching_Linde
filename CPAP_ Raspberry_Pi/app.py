"""
===============================================================================
CPAP Just-in-Time Video Coaching System — Raspberry Pi Edge Service (app.py)
-------------------------------------------------------------------------------
Laboratory: DISP Laboratory Lyon / Linde HomeCare France
Intern: Pamit Duggal | Supervisor: Yasaman Kakaei Siahkal

DESCRIPTION:
FastAPI REST server running on the Raspberry Pi 5 edge node. Handles:
1. POST /ingest  -> Ingests raw telemetry CSV from Pi local folder or phone app,
                    runs threshold detection (edge_detection.py), and selects
                    coaching videos via metadata rules (load_library.py).
2. POST /event   -> Receives pre-detected events + wearable biomarker CSV snapshots.
3. GET  /patient/{id}/coaching -> Dashboard polls to fetch assigned video decisions.
4. Real-time terminal logging & file logging for detected anomalies, video requests,
   and Latency/Overhead KPIs.
===============================================================================
"""

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Header, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import requests
from load_library import load_library, select_video
import edge_detection

# --- Environment Configurations ---
LIBRARY_ROOT = os.environ.get("LIBRARY_ROOT", ".")
API_KEY = os.environ.get("API_KEY", "")  # Security key matching mobile app
VIDEO_VM_URL = os.environ.get("VIDEO_VM_URL", "http://159.84.143.246:8080").rstrip("/")
VIDEO_SERVER_API_KEY = os.environ.get("VIDEO_SERVER_API_KEY", "")  # Shared secret for the Video VM Server; sent as X-API-KEY
GOOGLE_VERTEX_API_KEY = os.environ.get("GOOGLE_VERTEX_API_KEY", "") # Google Vertex AI API Key for Scenario 3
WITHINGS_DATA_DIR = Path(os.environ.get("WITHINGS_DATA_DIR", "data/withings"))
INGEST_DATA_DIR = Path(os.environ.get("INGEST_DATA_DIR", "data/ingest"))
LOG_DIR = Path(os.environ.get("LOG_DIR", "logs"))
EVENT_LOG_DIR = Path(os.environ.get("EVENT_LOG_DIR", "logs/events"))
def rate_limit_key(request: Request) -> str:
    """Rate-limit bucket for one caller.

    get_remote_address is wrong behind Tailscale Funnel: tailscaled terminates
    the connection on the Pi and proxies to localhost, so every caller on the
    internet shares the address 127.0.0.1 and therefore one bucket — a stranger
    hitting /ingest can spend the phone's whole 20/minute allowance. Callers
    holding the API key get their own bucket, so unauthenticated traffic can no
    longer lock the phone out. The key is hashed because slowapi keeps the value
    in memory and prints it in its own error paths; the bucket only needs to be
    stable and unguessable, not reversible.
    """
    key = request.headers.get("x-api-key")
    if key and hmac.compare_digest(key, API_KEY):
        return "key:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    # Unauthenticated: split by source where a proxy tells us one, so several
    # strangers do not share (and exhaust) a single anonymous bucket.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return "anon:" + forwarded.split(",")[0].strip()
    return "anon:" + (get_remote_address(request) or "unknown")


# Setup Rate Limiter (prevents brute forcing)
limiter = Limiter(key_func=rate_limit_key)

app = FastAPI(title="CPAP Just-in-Time Coaching - Edge Service")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# The console and server.log are for /ingest — the endpoint actually in use.
# The app still POSTs its whole export to /event, and one such batch becomes
# 100+ anomaly banners that bury every /ingest transaction, so /event is kept
# working but silent; its file logs under logs/ are still written in full.
class _IngestOnlyAccessLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/event" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_IngestOnlyAccessLog())

# Load 27 metadata JSON records into memory at startup
LIBRARY = load_library(LIBRARY_ROOT)
PENDING: dict = {}


def require_key(x_api_key: str):
    """Enforces API Key Authentication for incoming HTTP requests."""
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _append_formatted_log(log_type: str, patient_id: str, payload: dict):
    """
    Saves detected anomalies and video assignments into a clean log file on the Raspberry Pi
    (logs/detected_events_and_video_requests.log).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "detected_events_and_video_requests.log"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    log_entry = (
        f"[{timestamp}] [{log_type}] Patient: {patient_id} | "
        f"Payload: {json.dumps(payload, ensure_ascii=False)}\n"
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)


def print_detected_anomaly_console(patient_id: str, event: dict):
    """Prints clean, formatted event/anomaly details to the terminal console when detected."""
    print("\n" + "🚨"*35)
    print(" ⚠️ CPAP / BIOMARKER ANOMALY DETECTED ON EDGE NODE")
    print("🚨"*35)
    print(f" 👤 Patient ID         : {patient_id}")
    print(f" 🎯 Primary Trigger    : {event.get('trigger_type', 'Unknown')}")
    print(f" 🚨 Severity Level     : {str(event.get('severity', 'normal')).upper()}")
    print(f" 📊 Metrics Captured   : {json.dumps(event.get('metrics', {}), indent=2)}")
    if "all_events" in event:
        print(f" 🔢 Total Signals Flagged: {len(event['all_events'])}")
    print("🚨"*35 + "\n")


BUDGET_S = 60.0


def print_kpi_summary(start_time: float, scenario_name: str, patient_id: str, title: str,
                      exclude_ms: float = 0.0) -> float:
    """
    Prints the video assignment and the one timing the Pi can measure on its
    own clock: how long it took to turn the upload into a coaching decision.

    Transit is deliberately absent here. It is only known once the phone
    reports the round trip it measured to /timing, which necessarily arrives
    after this response has been sent — so the transit, total and budget are
    printed there instead of being estimated from two disagreeing clocks.
    Returns processing_time_ms so callers can persist it.
    """
    # exclude_ms is the outbound POST to the Video VM. It used to be inside
    # this figure, which made "Pi Processing Time" ~300ms of network to France
    # on top of ~6ms of actual edge work — the KPI is meant to measure the edge
    # node, so the hop is reported separately instead.
    processing_time_ms = max((time.time() - start_time) * 1000 - exclude_ms, 0.0)
    print("\n" + "="*70)
    print(" 🎬 VIDEO COACHING SELECTION & DASHBOARD PUSH SUMMARY")
    print("="*70)
    print(f" 👤 Patient ID           : {patient_id}")
    print(f" 📽️ Scenario Executed    : {scenario_name}")
    print(f" 📺 Video Asset Selected : {title}")
    print(f" ⚡ Pi Processing Time   : {processing_time_ms:.2f} ms")
    if exclude_ms:
        print(f" 🌐 Video VM Round Trip  : {exclude_ms:.2f} ms (excluded above)")
    print("="*70 + "\n")
    return processing_time_ms


def save_withings_csv(patient_id: str, csv_text: str) -> str:
    """Saves incoming Withings wearable biomarker CSV data for audit trails."""
    WITHINGS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = WITHINGS_DATA_DIR / f"{patient_id}_{int(time.time())}.csv"
    path.write_text(csv_text)
    return str(path)


def save_ingest_csv(patient_id: str, content: bytes) -> str:
    """Saves raw CPAP telemetry CSV bytes uploaded to /ingest."""
    INGEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = INGEST_DATA_DIR / f"{patient_id or 'unknown'}_{int(time.time())}.csv"
    path.write_bytes(content)
    return str(path)


# Best estimate, per patient device, of how far that phone's clock runs
# ahead of the Pi's, in ms. Transit time can never be negative, so the
# smallest delta ever seen from a device is the clearest read we get on its
# clock offset; everything after is re-based on it. Resets on restart, which
# is fine — it re-converges within a couple of events.
CLOCK_OFFSET_MS: dict[str, float] = {}

# A POST that sat in the phone's retry/backlog queue is not transit time.
# Deltas beyond this are still reported, but never allowed to become the
# offset estimate, so one stale batch can't poison every later reading.
MAX_PLAUSIBLE_TRANSIT_MS = 60_000.0


def compute_latency_ms(sent_at: str | None, received_at: datetime,
                       patient_id: str = "_default") -> tuple[float | None, float]:
    """Phone->Pi transit time for the KPI printout — pure calculation, no
    disk write (persistence now happens per-event via write_event_log).

    The phone and the Pi keep independent clocks. The raw
    (received_at - sent_at) delta therefore carries the difference between
    those two clocks on top of the real transit time, and goes NEGATIVE
    whenever the phone's clock runs ahead of the Pi's — which is what put
    a -382.9 ms floor under 42% of readings. One-way latency across two
    unsynchronised clocks is not directly measurable, so we estimate the
    offset as the smallest delta seen from this device and subtract it.

    Returns (latency_ms, offset_ms); latency_ms is None when sent_at is
    missing or unparseable. offset_ms is 0.0 when no skew has been observed.
    """
    if not sent_at:
        return None, 0.0
    try:
        sent_dt = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None, 0.0
    # A phone that sends a naive timestamp would otherwise raise TypeError
    # on the subtraction below and take the whole request down with it.
    if sent_dt.tzinfo is None:
        sent_dt = sent_dt.replace(tzinfo=timezone.utc)

    raw_ms = (received_at - sent_dt).total_seconds() * 1000

    known = CLOCK_OFFSET_MS.get(patient_id)
    if raw_ms < MAX_PLAUSIBLE_TRANSIT_MS and (known is None or raw_ms < known):
        CLOCK_OFFSET_MS[patient_id] = raw_ms
        known = raw_ms

    # Only correct once skew has actually proven itself with a negative
    # reading. A device whose deltas are all positive may simply have a
    # genuinely fast link, and subtracting its minimum would flatter the KPI.
    offset_ms = known if known is not None and known < 0 else 0.0
    return raw_ms - offset_ms, offset_ms


def _event_log_path(event_id: str) -> Path:
    EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return EVENT_LOG_DIR / f"{event_id}.json"


def write_event_log(event_id: str, fields: dict) -> None:
    """Create or update the ONE JSON file for this event_id, merging `fields`
    into whatever's already there — this file gets EDITED, not appended to,
    as the same event moves through detected -> sent -> received -> shown to
    the frontend/backend. No client_ip or anything else not needed to
    compute/aggregate the phone->Pi->frontend KPI per patient."""
    path = _event_log_path(event_id)
    record = json.loads(path.read_text()) if path.exists() else {}
    record.update(fields)
    path.write_text(json.dumps(record))


def mark_event_stage(event_id: str, field: str) -> None:
    """Set `field` to now, but only the FIRST time — repeated dashboard/
    backend polls shouldn't keep pushing the timestamp forward."""
    path = _event_log_path(event_id)
    record = json.loads(path.read_text()) if path.exists() else {}
    if record.get(field):
        return
    record[field] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(record))


def video_vm_headers() -> dict:
    """
    Headers for every POST to the Video VM Server. The server requires
    X-API-KEY on /api/orchestrate and /api/vertex-generate; if
    VIDEO_SERVER_API_KEY is unset the header is omitted and the server
    falls back to open-access mode.
    """
    headers = {"Content-Type": "application/json"}
    if VIDEO_SERVER_API_KEY:
        headers["X-API-KEY"] = VIDEO_SERVER_API_KEY
    return headers


_print = print


def _silent(*args, **kwargs) -> None:
    pass


# The dashboard's relevance field accepts only these three. Detection ranks
# events on its own five-level severity scale (critical/high/medium/low/routine)
# and that scale must keep "critical" — select_video sorts on it to pick which
# clip leads a stitched pair. So the two vocabularies are mapped here, at the
# outbound boundary, rather than by weakening the internal ranking.
DASHBOARD_RELEVANCE = ("low", "medium", "high")


def outbound_relevance(value) -> str:
    """Clamps a decision's relevance to what the dashboard will accept."""
    text = str(value or "high").strip().lower()
    if text in DASHBOARD_RELEVANCE:
        return text
    # critical, urgent, or anything a future rule invents: the dashboard has no
    # tier above high, so send high rather than a value it will reject.
    return "high"


def transition_label(transition: dict) -> str:
    """Renders the decision's transition dict as the VM's string form.

    The decision carries {"type": "crossfade", "duration_s": 1.5}; the VM's
    clips array wants "fade_1_5s" — the seconds with the decimal point as an
    underscore, since a dot would read as a file extension.
    """
    seconds = transition.get("duration_s", 1.5)
    # 1.5 -> "1_5", and 2.0 -> "2" so a whole number does not become "2_0".
    text = (f"{seconds:g}").replace(".", "_")
    return f"fade_{text}s"


def build_clips(decision: dict) -> list[dict]:
    """Builds the VM's clips array from a stitched decision, in play order.

    The per-clip URLs are assembled here rather than left to the VM: the VM
    derives url/subtitle_*_url for a single video from video_filename, but it
    stores a clips array verbatim, so a clip sent without them reaches the
    dashboard unplayable. The paths mirror what the VM returns for a single
    video (/videos/<bucket>/ and /subtitles/), so both shapes resolve the same
    way — if the VM ever enriches clips itself, these become redundant rather
    than wrong.
    """
    parts = [decision[k] for k in ("clip_1", "clip_2") if decision.get(k)]
    label = transition_label(decision.get("transition") or {})
    bucket = decision.get("storage_bucket", "existing")
    clips = []
    for step, clip in enumerate(parts, start=1):
        filename = os.path.basename(str(clip.get("filename", "")))
        subtitles = clip.get("subtitle_files") or {}
        entry = {
            "step": step,
            "video_id": clip.get("video_id"),
            "title": clip.get("title"),
            "video_filename": filename,
            "url": f"{VIDEO_VM_URL}/videos/{bucket}/{filename}",
            "duration_s": clip.get("duration_s"),
            # The last clip closes the sequence; every earlier one fades on.
            "transition": label if step < len(parts) else "end",
        }
        for code in ("en", "fr"):
            subtitle = subtitles.get(code)
            entry[f"subtitle_{code}_url"] = (
                f"{VIDEO_VM_URL}/subtitles/{os.path.basename(subtitle)}" if subtitle else None)
        clips.append(entry)
    return clips


def forward_to_video_vm(decision: dict, quiet: bool = False) -> dict | None:
    """
    Automatically notifies the Video VM Server (POST /api/orchestrate)
    after edge detection selects a coaching video. quiet=True keeps the
    console clear for /ingest when a large /event batch is being handled.
    """
    print = _silent if quiet else _print
    if not VIDEO_VM_URL:
        print("[EDGE -> VIDEO VM SKIPPED] VIDEO_VM_URL is empty — no video server configured.")
        return None
    if decision.get("action") == "none":
        print(f"[EDGE -> VIDEO VM SKIPPED] No coaching video matched for patient "
              f"{decision.get('patient_id', 'unknown')} — nothing to orchestrate. "
              f"Reason: {decision.get('message', 'action=none')}")
        return None

    # Handle scenario 1 (single) or scenario 2/3
    video_filename = decision.get("video_filename") or decision.get("video")
    if not video_filename and "clip_1" in decision:
        video_filename = decision["clip_1"].get("filename")
    elif not video_filename and "existing_clip" in decision:
        video_filename = decision["existing_clip"].get("filename")

    if not video_filename:
        print(f"[EDGE -> VIDEO VM SKIPPED] Decision '{decision.get('scenario', 'unknown')}' "
              f"carries no resolvable video filename — cannot orchestrate. Decision keys: "
              f"{sorted(decision.keys())}")
        return None

    video_filename = os.path.basename(str(video_filename))

    payload = {
        "patient_id": str(decision.get("patient_id", "63678")),
        "title": str(decision.get("title", "CPAP Coaching Video")),
        "video_filename": video_filename,
        # Rounded to whole seconds: the dashboard's /api/videos/{id}/assign
        # types duration_s as an int and 422s on a fractional value, which is
        # every scenario 2 decision (10s + 10s - 1.5s crossfade = 18.5). The
        # decision itself keeps the true 18.5 for the stitcher and the logs;
        # only this outbound field is rounded.
        "duration_s": round(float(decision.get("duration_s", decision.get("total_duration_s", 30)))),
        "category": str(decision.get("category", "coaching")),
        "trigger_reason": str(decision.get("trigger_reason", "anomaly_detected")),
        "relevance": outbound_relevance(decision.get("relevance")),
        "thumbnail_type": str(decision.get("thumbnail_type", "technical"))
    }

    # A stitched decision is two clips, but the payload above can only name one
    # file, so clip_2 used to be dropped here — the VM got "18 seconds" and a
    # single 10s clip, and the patient saw the first half only. Worse, the half
    # that vanished was the escalation: severity leads with the critical clip,
    # then composability swaps it second (14 -> 15 delivers "fix your mask" and
    # drops "contact your provider").
    #
    # The VM's multi-part contract is video_type "package" plus a clips array,
    # each entry carrying its own step/title/filename/duration and a transition
    # string ("fade_1_5s" between clips, "end" on the last). video_filename and
    # the top-level url stay clip 1's, matching how the VM renders a package.
    if decision.get("action") == "stitch_dual" and "clip_1" in decision:
        payload["video_type"] = "package"
        payload["clips"] = build_clips(decision)

    try:
        url = f"{VIDEO_VM_URL}/api/orchestrate"
        print(f"[EDGE -> VIDEO VM] Auto-forwarding decision to {url} for patient {payload['patient_id']}...")
        if not VIDEO_SERVER_API_KEY:
            print("[EDGE -> VIDEO VM WARNING] VIDEO_SERVER_API_KEY is unset — sending "
                  "without X-API-KEY; the video server will reject this with 403 "
                  "unless it is running in open-access mode.")
        resp = requests.post(url, json=payload, headers=video_vm_headers(), timeout=10)
        if resp.status_code == 403:
            print("[EDGE -> VIDEO VM WARNING] 403 Forbidden from the video server — "
                  "VIDEO_SERVER_API_KEY does not match its SERVER_API_KEY.")
        resp.raise_for_status()
        res_data = resp.json()
        print(f"[EDGE -> VIDEO VM] Successfully orchestrated! Push status: {res_data.get('dashboard_push')}")
        return res_data
    except Exception as e:
        print(f"[EDGE -> VIDEO VM WARNING] Failed to forward to Video VM: {e}")
        return {"error": str(e)}


@app.post("/ingest")
@limiter.limit("20/minute")
async def ingest(request: Request,
                 file: UploadFile = File(...),
                 language: str = Form("en"),
                 patient_id: str = Form(""),
                 sent_at: str = Form(None),
                 x_api_key: str = Header(None),
                 x_sent_at: str = Header(None)):
    """
    ENDPOINT 1: Raw Telemetry CSV Ingestion & Video Selection Pipeline.

    sent_at is the phone's clock stamped right before the upload starts; it
    can arrive as a form field or as the X-Sent-At header, whichever is
    easier for the app to attach to a multipart request. Both are optional —
    without one there is no phone-side reference point, so the transit KPI is
    reported as unavailable rather than guessed at.
    """
    t0 = time.time()
    received_at = datetime.now(timezone.utc)
    require_key(x_api_key)
    sent_at = sent_at or x_sent_at

    content = await file.read()
    ingest_saved = save_ingest_csv(patient_id, content)

    # 1. Edge threshold triage (CPAP + Biomarkers)
    event = edge_detection.detect_event(content)
    if not event:
        print(f"\n[INGEST] Patient {patient_id}: Telemetry normal — No anomaly detected.")
        return {"event": False, "message": "Normal telemetry — no coaching required", "ingest_saved": ingest_saved}

    if patient_id:
        event["patient_id"] = patient_id
    event["language"] = language

    # Print & log detected anomaly
    print_detected_anomaly_console(event["patient_id"], event)
    _append_formatted_log("ANOMALY_DETECTED", event["patient_id"], event)

    # 2. Select coaching video based on Scenario 1, 2, or 3 metadata search
    decision = select_video(event, LIBRARY)
    event_id = str(uuid.uuid4())
    PENDING[event["patient_id"]] = {"event_id": event_id, "decision": decision}

    # 3. Automatically forward request to Video VM server
    t_vm = time.time()
    vm_push_res = forward_to_video_vm(decision)
    vm_push_ms = (time.time() - t_vm) * 1000

    # Print & log video selection
    processing_ms = print_kpi_summary(t0, decision.get("scenario", "Scenario 1"),
                                      event["patient_id"], decision.get("title", "Coaching Asset"),
                                      exclude_ms=vm_push_ms)
    _append_formatted_log("VIDEO_ASSIGNED", event["patient_id"], decision)

    # The Pi is the detector here (raw CSV in, event out), so detected_at is
    # the Pi's own arrival moment; sent_at is the phone's, and the two only
    # differ by the upload's transit time. latency_ms and processing_ms are
    # stored alongside the raw stamps so a day can be aggregated without
    # re-deriving them from timestamps in 3000 files.
    write_event_log(event_id, {
        "event_id": event_id,
        "patient_id": event["patient_id"],
        "source": "ingest",

        # what was detected — the anomaly banner, in fields
        "trigger_type": event.get("trigger_type"),
        "severity": event.get("severity"),
        "metrics": event.get("metrics"),
        "signals_flagged": len(event.get("all_events", [event])),

        # what was decided
        "scenario": decision.get("scenario"),
        "video_title": decision.get("title"),
        "video_filename": decision.get("video_filename"),
        "video_vm_push": (vm_push_res or {}).get("status") if isinstance(vm_push_res, dict) else None,
        "video_vm_push_ms": round(vm_push_ms, 1),

        # when, and how long each leg took
        "detected_at": received_at.isoformat(),
        "sent_at": sent_at,
        "received_at": received_at.isoformat(),
        "processing_ms": round(processing_ms, 1),
        # transit_ms, total_ms and the budget verdict are filled in by /timing
        # once the phone reports the round trip it measured.
        "transit_source": "pending_rtt",
    })

    return {"event": True, "detected": event, "decision": decision, "video_vm_orchestrate": vm_push_res, "ingest_saved": ingest_saved,
            "event_id": event_id,
            "processing_ms": round(processing_ms, 1)}


@app.post("/event")
@limiter.limit("20/minute")
async def receive_event(request: Request, x_api_key: str = Header(None)):
    """
    ENDPOINT 2: Mobile App Pre-Detected Event Ingestion.
    """
    t0 = time.time()
    received_at = datetime.now(timezone.utc)
    require_key(x_api_key)

    body = await request.json()
    items = body["events"] if isinstance(body, dict) and "events" in body else [body]
    sent_at = body.get("sent_at") if isinstance(body, dict) else None

    results = []
    for item in items:
        trigger = item.get("trigger_type") or item.get("event")
        if not trigger:
            raise HTTPException(status_code=422, detail="Each event needs 'event' or 'trigger_type'")

        event_id = item.get("event_id") or str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "trigger_type": trigger,
            "severity": item.get("severity"),
            "language": item.get("language") or "en",
            "patient_id": str(item.get("patient_id") or "demo-patient"),
            "metrics": item.get("data") or item.get("metrics"),
        }

        # File log only — the console belongs to /ingest
        _append_formatted_log("ANOMALY_RECEIVED", event["patient_id"], event)

        # Select coaching video
        decision = select_video(event, LIBRARY)
        PENDING[event["patient_id"]] = {"event_id": event_id, "decision": decision}

        # Automatically forward request to Video VM server
        vm_push_res = forward_to_video_vm(decision, quiet=True)

        results.append({"detected": event, "decision": decision, "video_vm_orchestrate": vm_push_res})

        # Log video assignment
        _append_formatted_log("VIDEO_ASSIGNED", event["patient_id"], decision)

        # No per-item file here. The app posts its whole export in one call,
        # so writing one file per item buried the /ingest records under 100+
        # of them; /ingest is the endpoint in use and owns logs/events. The
        # batch still lands in the append-only log above.

    withings_saved = None
    withings_csv = body.get("withings_csv") if isinstance(body, dict) else None
    if withings_csv and results:
        withings_saved = save_withings_csv(results[0]["detected"]["patient_id"], withings_csv)

    withings_patient_id = body.get("withings_patient_id") if isinstance(body, dict) else None

    # Clock offset is tracked per device, so the patient has to be resolved
    # before the latency is computed rather than alongside the printout.
    p_id = results[0]["detected"]["patient_id"] if results else "_default"
    latency_ms, clock_offset_ms = compute_latency_ms(sent_at, received_at, p_id)

    return {
        "received": len(results),
        "results": results,
        "withings_patient_id": withings_patient_id,
        "withings_saved": withings_saved,
        "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
        "clock_offset_ms": round(clock_offset_ms, 1) if clock_offset_ms else 0.0,
    }


@app.get("/patient/{patient_id}/coaching")
@limiter.limit("120/minute")
def get_coaching(request: Request, patient_id: str, x_api_key: str = Header(None)):
    """
    ENDPOINT 3: Web App Dashboard Polling Endpoint.
    """
    require_key(x_api_key)
    entry = PENDING.get(patient_id)
    decision = entry["decision"] if entry else None
    if decision:
        print(f"\n[DASHBOARD POLL] Patient {patient_id} requested video. Serving: '{decision.get('title')}'")
        _append_formatted_log("DASHBOARD_FETCHED_VIDEO", patient_id, decision)
        mark_event_stage(entry["event_id"], "frontend_fetched_at")
    return {"pending": bool(decision), "decision": decision}


@app.post("/patient/{patient_id}/clear")
@limiter.limit("60/minute")
def clear_coaching(request: Request, patient_id: str, x_api_key: str = Header(None)):
    """
    ENDPOINT 4: Marks video as watched and clears pending queue.
    """
    require_key(x_api_key)
    entry = PENDING.pop(patient_id, None)
    print(f"[DASHBOARD CLEAR] Patient {patient_id} finished watching video.")
    _append_formatted_log("DASHBOARD_CLEARED_VIDEO", patient_id, {"status": "cleared"})
    if entry:
        mark_event_stage(entry["event_id"], "frontend_cleared_at")
    return {"cleared": patient_id}


@app.post("/timing/{event_id}")
@limiter.limit("60/minute")
async def report_timing(request: Request, event_id: str, x_api_key: str = Header(None)):
    """
    ENDPOINT 5: The phone reports the round trip it measured for one /ingest.

    Transit measured as (Pi arrival - phone send) is only as good as the
    agreement between two clocks, and here the phone's runs tens of ms ahead
    of the Pi's — the same size as the transit itself. A round trip is
    immune to that: both stamps come from the phone's own clock, so whatever
    it is offset by cancels out. Subtracting the processing_ms the Pi already
    reported leaves pure network time, halved for the one-way figure.

    Body: {"rtt_ms": <t1 - t0 measured by the phone>}
    """
    require_key(x_api_key)
    body = await request.json()
    rtt_ms = body.get("rtt_ms")
    if rtt_ms is None:
        raise HTTPException(status_code=422, detail="Body needs 'rtt_ms'")
    try:
        rtt_ms = float(rtt_ms)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="'rtt_ms' must be a number")

    path = _event_log_path(event_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No such event: {event_id}")
    record = json.loads(path.read_text())

    # Everything the Pi held the connection for is not network, and all of it
    # was measured on the Pi's clock alone, so it subtracts cleanly. That is
    # edge work PLUS the outbound POST to the Video VM: the VM hop is reported
    # separately in the KPI summary because it is not edge processing, but the
    # phone's round trip still contains it, so it has to come out here too —
    # otherwise those ~300ms are misattributed to network transit and the
    # one-way figure comes out roughly three times too large.
    processing_ms = record.get("processing_ms") or 0.0
    vm_push_ms = record.get("video_vm_push_ms") or 0.0
    server_ms = processing_ms + vm_push_ms
    network_ms = max(rtt_ms - server_ms, 0.0)

    transit_ms = network_ms / 2
    total_ms = transit_ms + server_ms
    budget_passed = total_ms / 1000 <= BUDGET_S

    # rtt_ms and network_ms are intermediate steps on the way to these two;
    # only the figures that mean something on their own are kept.
    write_event_log(event_id, {
        "latency_ms": round(transit_ms, 1),
        "total_latency_ms": round(total_ms, 1),
        "server_ms": round(server_ms, 1),
        "budget_s": BUDGET_S,
        "budget_passed": budget_passed,
        "transit_source": "measured_rtt",
    })

    print("\n" + "="*70)
    print(" ⏱️ TRANSACTION TIMING (measured round trip — no clock skew)")
    print("="*70)
    print(f" 👤 Patient ID           : {record.get('patient_id', 'unknown')}")
    print(f" 📡 Round Trip Measured  : {rtt_ms:.2f} ms")
    print(f" 🌐 Phone -> Pi Transit  : {transit_ms:.2f} ms")
    print(f" ⚡ Pi Processing Time   : {processing_ms:.2f} ms")
    if vm_push_ms:
        print(f" 🛰️ Video VM Round Trip  : {vm_push_ms:.2f} ms")
    print(f" 🏁 Total Phone -> Ready : {total_ms:.2f} ms")
    verdict = "PASSED ✅" if budget_passed else "EXCEEDED ❌"
    print(f" ⏱️ 60-Second Budget     : {total_ms/1000:.3f}s / {BUDGET_S:.1f}s ({verdict})")
    print("="*70 + "\n")

    return {"event_id": event_id, "rtt_ms": round(rtt_ms, 1),
            "processing_ms": round(processing_ms, 1),
            "video_vm_push_ms": round(vm_push_ms, 1),
            "network_ms": round(network_ms, 1),
            "transit_ms": round(transit_ms, 1),
            "total_ms": round(total_ms, 1),
            "budget_passed": budget_passed}


@app.get("/health")
@limiter.limit("60/minute")
def health(request: Request):
    """
    ENDPOINT 5: Health Check & Network Auto-Discovery.
    """
    return {
        "status": "ok",
        "service": "telemetry-pi",
        "version": 2,
        "total_indexed_videos": len(LIBRARY.get("by_video_id", {}))
    }
