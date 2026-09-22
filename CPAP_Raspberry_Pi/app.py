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
2. GET  /patient/{id}/coaching -> Dashboard polls to fetch assigned video decisions.
3. Real-time terminal logging & file logging for detected anomalies, video requests,
   and Latency/Overhead KPIs.
===============================================================================
"""

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (FastAPI, Request, Header, HTTPException, UploadFile, File, Form,
                     BackgroundTasks)
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import requests
from load_library import load_library, select_video
import edge_detection

# load_library already calls load_dotenv() at import time, so in practice .env
# has been read by the time this module configures itself. Doing it explicitly
# here means app.py's own config no longer rides on another module's import
# side effect — reorder the imports above and the telemetry keys below would
# silently fall back to their defaults instead.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Environment Configurations ---
LIBRARY_ROOT = os.environ.get("LIBRARY_ROOT", ".")
API_KEY = os.environ.get("API_KEY", "")  # Security key matching mobile app; set via .env
VIDEO_VM_URL = os.environ.get("VIDEO_VM_URL", "http://159.84.143.246:8080").rstrip("/")
VIDEO_SERVER_API_KEY = os.environ.get("VIDEO_SERVER_API_KEY", "")  # Shared secret for the Video VM Server; sent as X-API-KEY
# How long the Pi waits on a scenario 3 generation. Kept short on purpose: the
# VM runs generation synchronously, so it can take minutes, and /ingest must
# not hold the phone's request open that long. Timing out here does not cancel
# the VM's work — see request_generation().
GENERATION_TIMEOUT_S = float(os.environ.get("GENERATION_TIMEOUT_S", "20"))
WITHINGS_DATA_DIR = Path(os.environ.get("WITHINGS_DATA_DIR", "data/withings"))
INGEST_DATA_DIR = Path(os.environ.get("INGEST_DATA_DIR", "data/ingest"))
LOG_DIR = Path(os.environ.get("LOG_DIR", "logs"))
EVENT_LOG_DIR = Path(os.environ.get("EVENT_LOG_DIR", "logs/events"))

# --- Central backend telemetry (DB_Clinical.telemetry.event_traces) ---
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "").rstrip("/")
BACKEND_API_KEY = os.environ.get("BACKEND_API_KEY", "")
# Kill switch. An empty BACKEND_API_URL disables the push just as effectively;
# the flag exists so the URL can stay configured while one run is deliberately
# kept out of the clinical database.
TELEMETRY_ENABLED = os.environ.get("TELEMETRY_ENABLED", "true").strip().lower() in ("1", "true", "yes")
# Split connect/read rather than one number: the push runs off the request path,
# so slowness costs the patient nothing, but a black-holed socket would still
# pin a worker thread until it gave up.
BACKEND_TIMEOUT = (2.0, 3.0)


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

# Load the 37 metadata JSON records into memory at startup
LIBRARY = load_library(LIBRARY_ROOT)
PENDING: dict = {}


def require_key(x_api_key: str):
    """Enforces API Key Authentication for incoming HTTP requests."""
    if API_KEY and (not x_api_key or not hmac.compare_digest(x_api_key, API_KEY)):
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


def request_generation(decision: dict, event_id: str | None = None, log=None) -> dict:
    """
    Scenario 3: ask the Video VM to generate a clip it does not already hold
    (POST /api/vertex-generate). Used when detection flagged a condition the
    library has no coaching video for, so there is nothing to orchestrate.

    Three findings from live testing against the VM shape this, all deliberate:

    1. **The VM used to report success on failure.** It answered HTTP 200 with
       "status": "success" and a resolvable url even when Google refused the
       generation. The VM owner fixed this on 2026-09-03 ("success" now means
       real bytes or a valid cache hit; otherwise "failed" plus error_code), so
       the top-level status is read again — but the nested "vertex_api_status"
       is still cross-checked, since it is the field that exposed the lie.
    2. **The call is synchronous on the VM.** One generation request blocks
       /api/orchestrate for every patient until it finishes, and a real one ran
       past 300s. The timeout below bounds only how long the Pi waits; it does
       not cancel the VM's work, so a timeout here means "unknown", not
       "failed", and the result is reported that way.
    3. **A cache may return someone else's clip.** Several generated names have
       been byte-identical, so a returned url is not evidence a generation
       happened — and the VM now replays the quota-era placeholder entries
       (28, 29, 30) as status=success / cache_hit=true. A cache hit is
       therefore reported as "cached", never "generated". Verify by hashing
       the file before trusting it clinically.
    """
    log = log or _print
    request = decision.get("vertex_ai_request") or {}
    payload = {
        "patient_id": str(decision.get("patient_id", "63678")),
        "prompt": request.get("prompt", ""),
        # Correlation key. The VM stamps its own t5_received_at_vm against this
        # id in telemetry.event_traces; without it the VM's leg of the trace
        # cannot be joined to the Pi's and lands on nothing.
        "event_id": event_id,
    }
    # No "model" key: the VM interpolates it into the Vertex URL path, so a
    # wrong value asks for a model that does not exist. Its own default is
    # correct, and the model belongs to whoever owns the Vertex relationship.

    url = f"{VIDEO_VM_URL}/api/vertex-generate"
    log(f"[EDGE -> VIDEO VM] Scenario 3: requesting generation at {url} for patient "
        f"{payload['patient_id']} — no library clip covers "
        f"{decision.get('uncovered_signals') or 'this condition'}.")
    try:
        resp = requests.post(url, json=payload, headers=video_vm_headers(), timeout=GENERATION_TIMEOUT_S)
        if resp.status_code == 403:
            log("[EDGE -> VIDEO VM WARNING] 403 Forbidden — VIDEO_SERVER_API_KEY does "
                "not match the video server's SERVER_API_KEY.")
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        log(f"[EDGE -> VIDEO VM WARNING] Generation did not answer within "
            f"{GENERATION_TIMEOUT_S}s. The VM is probably still working — treat this "
            f"as unknown, not failed, and do not retry (a retry blocks the VM again).")
        return {"generation_status": "unknown_timeout",
                "detail": f"no response within {GENERATION_TIMEOUT_S}s"}
    except Exception as e:
        log(f"[EDGE -> VIDEO VM WARNING] Generation request failed: {e}")
        return {"generation_status": "failed", "error": str(e)}

    # Three signals, and a real generation needs all three to agree. The VM
    # owner fixed the top-level status on 2026-09-03 so that "success" means
    # real bytes or a valid cache hit, with "failed" + error_code otherwise —
    # but the nested vertex_api_status is kept as a cross-check, because it is
    # what caught the VM claiming success over a Vertex 403 in the first place.
    top_status = str(data.get("status", "")).lower()
    vertex_status = str(data.get("vertex_api_status", "")).lower()
    error_code = data.get("error_code")
    cache_hit = bool(data.get("cache_hit"))

    cached_markers = ("cached_reuse", "cached", "cache_hit")
    vertex_ok = vertex_status.startswith("http_2") or vertex_status in ("ok", "success", "generated")
    # Only treat vertex_api_status as a veto when it is present AND says
    # something other than ok/cached — an absent field must not read as failure.
    vertex_contradicts = bool(vertex_status) and not vertex_ok and vertex_status not in cached_markers

    if top_status != "success" or error_code or vertex_contradicts:
        gen_status = "not_generated"
        log(f"[EDGE -> VIDEO VM WARNING] No video was generated. status="
            f"'{data.get('status')}' error_code={error_code!r} "
            f"vertex_api_status='{data.get('vertex_api_status')}' — "
            f"{data.get('error_message') or 'no error_message'}. "
            f"Any url in this response points at cached or placeholder content.")
    elif cache_hit or vertex_status in cached_markers:
        # A cache hit is NOT evidence a render happened. During the Google
        # quota outage the VM populated entries 28/29/30 with placeholders to
        # avoid downstream 404s, and it now replays those as
        # status=success / cache_hit=true forever. Every generated name served
        # so far has been the same 10,127,558-byte file (md5 bbb75d1e6d5b) —
        # hash the url before showing a cached clip to a patient.
        gen_status = "cached"
        log(f"[EDGE -> VIDEO VM] Cache hit ({data.get('vertex_api_status')}) — the VM "
            f"replayed a stored clip and rendered nothing. Treat as UNVERIFIED until "
            f"the file is hashed: the quota-era placeholders replay as success too.")
    else:
        gen_status = "generated"
        log(f"[EDGE -> VIDEO VM] Generation reported complete for patient "
            f"{payload['patient_id']}.")

    return {
        "generation_status": gen_status,
        "vertex_api_status": data.get("vertex_api_status"),
        "reported_status": data.get("status"),
        "error_code": error_code,
        "error_message": data.get("error_message"),
        "cache_hit": cache_hit,
        "url": data.get("url"),
        "raw": data,
    }


def forward_to_video_vm(decision: dict, event_id: str | None = None,
                        quiet: bool = False) -> dict | None:
    """
    Automatically notifies the Video VM Server after edge detection selects a
    coaching video: POST /api/orchestrate for scenarios 1 and 2, or
    /api/vertex-generate for a scenario 3 decision with no clip to send.
    quiet=True swaps the console printout for the silent one (unused since
    /event was removed).
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

    # Scenario 3 carries no clip to orchestrate — it is a different VM route.
    if decision.get("action") == "generate":
        return request_generation(decision, event_id=event_id, log=print)

    # Handle scenario 1 (single) or scenario 2
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
        # Correlation key for the VM's own telemetry leg — it stamps
        # t5_received_at_vm against this id on the same event_traces row the Pi
        # opened. OrchestrateRequest types it optional, so an omitted id is
        # accepted silently and the VM's timing simply never joins up.
        "event_id": event_id,
        "scenario": decision.get("scenario"),
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


def trace_video_filename(decision: dict) -> str | None:
    """The one filename that stands for this decision in the trace row.

    A plain decision.get("video_filename") writes NULL for every scenario 2
    event: a stitched decision carries no top-level filename, its two clips
    hold their own. Falls back to clip 1, the same asset forward_to_video_vm()
    names as the package's lead. Scenario 3 has no library file at all and
    correctly stays None.
    """
    filename = decision.get("video_filename") or decision.get("video")
    if not filename and "clip_1" in decision:
        filename = decision["clip_1"].get("filename")
    return os.path.basename(str(filename)) if filename else None


def vm_push_status(vm_push_res) -> str:
    """Collapses forward_to_video_vm's three return shapes into one word.

    None means nothing was orchestrated (action=none, or no VM configured),
    {"error": ...} means the POST failed, anything else means the VM answered.
    The fuller status stays in the local event log; the backend column only
    needs to separate a delivered event from an undelivered one.
    """
    if vm_push_res is None:
        return "skipped"
    if not isinstance(vm_push_res, dict):
        return "unknown"
    return "error" if vm_push_res.get("error") else "ok"


def post_event_trace(phase: int, payload: dict) -> None:
    """Fire-and-forget one phase of an event trace at the central backend.

    Runs as a BackgroundTasks callable, i.e. AFTER the response has gone back
    to the phone. That ordering is not cosmetic. /timing derives network
    transit as (rtt - processing_ms - vm_push_ms), and this call sits in
    neither term, so any millisecond spent here while the phone is still
    timing would be charged to the network and then doubled into the one-way
    figure — the same misattribution the VM hop used to cause.

    Never raises: a telemetry sink must not be able to take down ingestion.
    """
    if not TELEMETRY_ENABLED or not BACKEND_API_URL:
        return
    event_id = payload.get("event_id", "unknown")
    headers = {"Content-Type": "application/json"}
    if BACKEND_API_KEY:
        headers["X-API-Key"] = BACKEND_API_KEY
    # Retried because losing a phase 1 is silent AND misleading: the backend
    # upserts on event_id, so a later phase 2 still creates the row and marks
    # it lifecycle_status "complete" — a row that looks finished while missing
    # severity, scenario, trigger_type and every timestamp. One transient
    # "No route to host" in a 36-event burst produced exactly that.
    #
    # Only connection-level failures are retried. A non-200 is the backend
    # rejecting the payload's shape, and resending an identical body cannot
    # fix that — it would just triple the noise.
    for attempt, backoff in enumerate((0.5, 1.5, None), start=1):
        try:
            resp = requests.post(f"{BACKEND_API_URL}/event-trace", json=payload,
                                 headers=headers, timeout=BACKEND_TIMEOUT)
            break
        except Exception as e:
            if backoff is None:
                print(f"[EDGE -> BACKEND UNREACHABLE] Phase {phase} '{event_id}' "
                      f"skipped after {attempt} attempts: {e}")
                try:
                    write_event_log(event_id, {"backend_sync": f"phase{phase}_unreachable"})
                except Exception:
                    pass
                return
            time.sleep(backoff)
    # Phase 1 and phase 2 are both background tasks and can reach the backend
    # together. Its upsert is check-then-insert, not atomic, so when no row
    # exists yet — normally the Video VM's own post creates it first, but not
    # when the VM is unreachable — both phases insert and the loser gets a
    # 500 PRIMARY KEY violation. Unlike schema drift, resending does fix this:
    # the row now exists, so the retry lands as an update.
    if resp.status_code == 500 and ("PRIMARY KEY" in resp.text or "IntegrityError" in resp.text):
        time.sleep(0.5)
        try:
            resp = requests.post(f"{BACKEND_API_URL}/event-trace", json=payload,
                                 headers=headers, timeout=BACKEND_TIMEOUT)
        except Exception as e:
            print(f"[EDGE -> BACKEND WARNING] Phase {phase} '{event_id}' retry after "
                  f"duplicate-key race failed: {e}")
    try:
        if resp.status_code == 200:
            print(f"[EDGE -> BACKEND] Phase {phase} trace '{event_id}' synced to DB_Clinical.")
            outcome = f"phase{phase}_ok"
        else:
            # A rejected payload is schema drift, not a network blip, and it is
            # the failure that would otherwise be invisible — the row simply
            # never appears in SQL Server. The backend returns a structured
            # detail on 422, so keep the body.
            print(f"[EDGE -> BACKEND REJECTED] Phase {phase} '{event_id}' -> "
                  f"HTTP {resp.status_code}: {resp.text[:300]}")
            outcome = f"phase{phase}_rejected_{resp.status_code}"
    except Exception as e:
        # Only a malformed response body can land here now; the network paths
        # returned above.
        print(f"[EDGE -> BACKEND WARNING] Phase {phase} '{event_id}' response unreadable: {e}")
        outcome = f"phase{phase}_bad_response"
    # Recorded against the event itself so a row missing from the clinical DB
    # can be explained from logs/events/<id>.json, without grepping stdout.
    try:
        write_event_log(event_id, {"backend_sync": outcome})
    except Exception:
        pass


@app.post("/ingest")
@limiter.limit("20/minute")
async def ingest(request: Request,
                 background_tasks: BackgroundTasks,
                 file: UploadFile = File(...),
                 language: str = Form("en"),
                 patient_id: str = Form(""),
                 sent_at: str = Form(None),
                 x_api_key: str = Header(None),
                 x_sent_at: str = Header(None),
                 x_test_run: str = Header(None)):
    """
    ENDPOINT 1: Raw Telemetry CSV Ingestion & Video Selection Pipeline.

    sent_at is the phone's clock stamped right before the upload starts; it
    can arrive as a form field or as the X-Sent-At header, whichever is
    easier for the app to attach to a multipart request. Both are optional —
    without one there is no phone-side reference point, so the transit KPI is
    reported as unavailable rather than guessed at.

    X-Test-Run marks fixture traffic (test_csv/run_tests.sh sets it). It rides
    through to the backend as is_test so 35 synthetic events per run stay out
    of the clinical dashboard's aggregates instead of polluting them.
    """
    t0 = time.time()
    received_at = datetime.now(timezone.utc)
    require_key(x_api_key)
    sent_at = sent_at or x_sent_at
    is_test = str(x_test_run or "").strip().lower() in ("1", "true", "yes")

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
    #
    # t3 is stamped BEFORE the hop, t4 after it. The pipeline decides first and
    # pushes second, so t3 (processed) genuinely precedes t4 (pushed) — stamping
    # t3 after the KPI summary further down, as the integration guide's snippet
    # did, would file rows where t4 < t3 and read as clock corruption.
    t3_processed_at = datetime.now(timezone.utc)
    # t4 marks the HANDOFF — the moment the Pi puts the request on the wire —
    # not the moment the VM answers. Stamping it after the round trip returned
    # put it ~300 ms late and, crucially, behind the VM's own
    # t5_received_at_vm: every row in event_traces ran t3 -> t5 -> t4, making
    # the VM's inbound transit (t5 - t4) negative. The round trip is already
    # reported in full as vm_push_ms, so t4 only has to mark the send.
    t4_pushed_at_vm = datetime.now(timezone.utc)
    t_vm = time.time()
    vm_push_res = forward_to_video_vm(decision, event_id=event_id)
    vm_push_ms = (time.time() - t_vm) * 1000

    # Scenario 3 has no library filename, so the ONLY playable asset it will
    # ever have is the url the generation call returns. PENDING already holds
    # this same decision object, so merging here is what lets
    # GET /patient/{id}/coaching serve a generated clip at all — without it the
    # dashboard polls back a decision with nothing to play.
    if decision.get("action") == "generate" and isinstance(vm_push_res, dict):
        gen_status = vm_push_res.get("generation_status")
        decision["generation_status"] = gen_status
        # Trusted only when the VM actually rendered: "cached" means it replayed
        # a stored file, which during the quota outage was a placeholder.
        decision["generation_verified"] = gen_status == "generated"
        if vm_push_res.get("error_code"):
            decision["generation_error"] = vm_push_res.get("error_code")
        if vm_push_res.get("url") and gen_status in ("generated", "cached"):
            decision["video_url"] = vm_push_res["url"]

    # Print & log video selection
    processing_ms = print_kpi_summary(t0, decision.get("scenario", "Scenario 1"),
                                      event["patient_id"], decision.get("title", "Coaching Asset"),
                                      exclude_ms=vm_push_ms)
    _append_formatted_log("VIDEO_ASSIGNED", event["patient_id"], decision)

    # Rounded ONCE, here, and reused by the event log, phase 1 and (via the
    # log) phase 2. Rounding each consumer separately made the two phases
    # disagree: phase 1 sent 2dp off the live float while phase 2 rebuilt
    # server_ms from the log's 1dp copy, so a trace row failed its own
    # server_ms == pi_processing_ms + vm_push_ms identity by up to 0.05 ms.
    processing_ms_r = round(processing_ms, 2)
    vm_push_ms_r = round(vm_push_ms, 2)

    # The Pi is the detector here (raw CSV in, event out), so detected_at is
    # the Pi's own arrival moment; sent_at is the phone's, and the two only
    # differ by the upload's transit time. latency_ms and processing_ms are
    # stored alongside the raw stamps so a day can be aggregated without
    # re-deriving them from timestamps in 3000 files.
    write_event_log(event_id, {
        "event_id": event_id,
        "patient_id": event["patient_id"],
        "source": "ingest",
        # Persisted so /timing can carry the same flag into phase 2 — without
        # it a fixture run's phase 1 lands as is_test but its RTT completion
        # lands as clinical traffic, on the same row.
        "is_test": is_test,

        # what was detected — the anomaly banner, in fields
        "trigger_type": event.get("trigger_type"),
        "severity": event.get("severity"),
        "metrics": event.get("metrics"),
        "signals_flagged": len(event.get("all_events", [event])),

        # what was decided
        "scenario": decision.get("scenario"),
        "video_title": decision.get("title"),
        "video_filename": decision.get("video_filename"),
        # scenario 1/2 answer with "status"; scenario 3 answers with
        # "generation_status" — log whichever the route actually returned.
        "video_vm_push": ((vm_push_res or {}).get("status")
                          or (vm_push_res or {}).get("generation_status")) if isinstance(vm_push_res, dict) else None,
        "video_vm_push_ms": vm_push_ms_r,

        # when, and how long each leg took
        "detected_at": received_at.isoformat(),
        "sent_at": sent_at,
        "received_at": received_at.isoformat(),
        "processing_ms": processing_ms_r,
        # transit_ms, total_ms and the budget verdict are filled in by /timing
        # once the phone reports the round trip it measured.
        "transit_source": "pending_rtt",
    })

    # Phase 1 of the central KPI trace. Queued rather than awaited — see
    # post_event_trace() for why this must not sit on the request path.
    background_tasks.add_task(post_event_trace, 1, {
        "event_id": event_id,
        # event["patient_id"], not the form field: the form value is optional
        # and arrives empty on any upload that omits it, where the event always
        # carries a resolved id.
        "patient_id": event["patient_id"],
        "trigger_type": event.get("trigger_type"),
        # The raw event severity (critical/high/medium/low/routine), NOT the
        # decision's relevance. relevance is hardcoded "high" on every matched
        # decision because it is a dashboard display field, so sourcing
        # severity from it would flatten every row in the clinical DB to one
        # tier and destroy the triage gradient. The backend accepts all five.
        "severity": event.get("severity"),
        "scenario": decision.get("scenario"),
        "action": decision.get("action"),
        "video_title": decision.get("title"),
        "video_filename": trace_video_filename(decision),
        "signals_flagged": len(event.get("all_events", [event])),
        "vm_push_status": vm_push_status(vm_push_res),
        "is_test": is_test,

        # t0 is the Pi's own arrival, not a phone stamp: the Pi is the detector
        # here (raw CSV in, event out), so no earlier moment exists to report.
        # t1 is the phone's clock and may be absent; it is sent for the record
        # only. The two clocks are unsynchronised by roughly the size of the
        # transit itself, so transit is derived from the phone's round trip in
        # phase 2 and never from t2 - t1.
        "t0_detected_at": received_at.isoformat(),
        "t1_sent_at": sent_at,
        "t2_received_at_pi": received_at.isoformat(),
        "t3_processed_at_pi": t3_processed_at.isoformat(),
        "t4_pushed_at_vm": t4_pushed_at_vm.isoformat(),

        # Edge work only; the VM hop is reported beside it, never inside it.
        # For a scenario 3 decision vm_push_ms is a synchronous generation
        # wait capped at GENERATION_TIMEOUT_S, not a network push — the
        # backend has to segment on `scenario` before averaging these.
        "pi_processing_ms": processing_ms_r,
        "vm_push_ms": vm_push_ms_r,
    })

    return {"event": True, "detected": event, "decision": decision, "video_vm_orchestrate": vm_push_res, "ingest_saved": ingest_saved,
            "event_id": event_id,
            "processing_ms": round(processing_ms, 1)}


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
async def report_timing(request: Request, background_tasks: BackgroundTasks,
                        event_id: str, x_api_key: str = Header(None)):
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

    # Phase 2 completes the row phase 1 opened: the backend upserts on event_id
    # and advances status partial -> complete. Sends the derived figures rather
    # than the raw round trip alone, because the derivation is not reproducible
    # from the payload — server_ms has to come out of the round trip before
    # halving, and only the Pi knows the VM hop that is buried inside it.
    # total is DERIVED from the two rounded components it is stored beside,
    # not rounded independently from the full-precision float. Rounding all
    # three separately left the trace row failing its own
    # total_latency_ms == transit_latency_ms + server_ms identity by 0.01 ms —
    # physically meaningless, but enough to fail a backend consistency check
    # on every row and send someone hunting a bug that isn't there.
    transit_r = round(transit_ms, 2)
    server_r = round(server_ms, 2)
    background_tasks.add_task(post_event_trace, 2, {
        "event_id": event_id,
        "patient_id": record.get("patient_id", "unknown"),
        "total_rtt_ms": round(rtt_ms, 2),
        "transit_latency_ms": transit_r,
        "server_ms": server_r,
        "total_latency_ms": round(transit_r + server_r, 2),
        # BUDGET_S, not a literal 60.0: the SLA verdict the backend stores has
        # to move with the budget the Pi actually judged against.
        "budget_s": BUDGET_S,
        "budget_passed": budget_passed,
        "is_test": bool(record.get("is_test")),
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
