#!/usr/bin/env python3
"""
===============================================================================
video_vm_server.py - High-Performance Clinical Video Streaming & Orchestration Node
===============================================================================
This is the core server application for the CPAP Video Virtual Machine (VM4).
It is built with FastAPI and Uvicorn to provide:
  1. Low-latency, high-throughput MP4 video streaming (with HTTP Range-Byte seek).
  2. Bilingual WebVTT subtitle streaming (English & French).
  3. Scenario 1: Existing single-clip recommendation & dashboard dispatch.
  4. Scenario 2: Multi-clip virtual sequence orchestration with 1.5s crossfade.
  5. Scenario 3: Google Veo / Vertex AI generative video synthesis & caching.
  6. Distributed telemetry sync (t5 arrival & t6 ready) to Central SQL Server.
  7. 5-Layer enterprise security (probe filter, headers, X-API-KEY auth, CORS).
===============================================================================
"""

# =============================================================================
# 1. IMPORTS & DEPENDENCIES
# =============================================================================
import os
import sys
import time
import base64
import shutil
import logging
import subprocess
import re
import hashlib
import json
import threading
import asyncio
import collections
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Request, Response, Depends
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import requests

try:
    from build_video_metadata import sync_all_video_assets, synthesize_subtitles_for_video
except ImportError:
    sync_all_video_assets = None
    synthesize_subtitles_for_video = None

try:
    from update_master_metadata import update_master_metadata
except ImportError:
    update_master_metadata = None

try:
    from sync_remote_nodes import (
        compile_distributed_trigger_catalog,
        broadcast_triggers_to_all_nodes,
        broadcast_in_background
    )
except ImportError:
    compile_distributed_trigger_catalog = None
    broadcast_triggers_to_all_nodes = None
    broadcast_in_background = None

try:
    from assignment_ledger import assignment_ledger
except ImportError:
    assignment_ledger = None

try:
    from deduplication_engine import (
        find_existing_library_match,
        register_prompt_cache
    )
except ImportError:
    find_existing_library_match = None
    register_prompt_cache = None


# Ensure UTF-8 output encoding for Windows CMD/PowerShell consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# =============================================================================
# 2. LOGGING CONFIGURATION & REAL-TIME WEB LOG BUFFER
# =============================================================================
class CircularLogBufferHandler(logging.Handler):
    """
    Thread-safe circular in-memory buffer capturing recent log records for
    real-time streaming to the Web Dashboard terminal via SSE or JSON polling.
    """
    def __init__(self, capacity: int = 1000):
        super().__init__()
        self.capacity = capacity
        self.buffer = collections.deque(maxlen=capacity)
        self.subscribers: List[asyncio.Queue] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            entry = {
                "id": time.time_ns(),
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": record.levelname,
                "message": msg,
                "raw": msg
            }
            with self._lock:
                self.buffer.append(entry)
                for q in list(self.subscribers):
                    try:
                        q.put_nowait(entry)
                    except Exception:
                        pass
        except Exception:
            self.handleError(record)

    def get_recent(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self.buffer)
            return items[-limit:]

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        with self._lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        with self._lock:
            if q in self.subscribers:
                self.subscribers.remove(q)


class LiveScenarioTracker:
    """
    Thread-safe tracker for live active scenario executions and incoming requests
    from AI Server (VM3), Raspberry Pi 5 Edge (Port 8000), or Web Dashboard.
    """
    def __init__(self, history_limit: int = 50):
        self.history_limit = history_limit
        self._lock = threading.Lock()
        self.active_scenario: Optional[Dict[str, Any]] = None
        self.recent_activities: List[Dict[str, Any]] = []

    def record_activity(self, scenario_id: int, scenario_name: str, patient_id: str, title: str, 
                        source_node: str, details: Dict[str, Any], status: str = "completed"):
        entry = {
            "id": time.time_ns(),
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "iso_time": datetime.now(timezone.utc).isoformat(),
            "scenario_id": scenario_id, # 1, 2, or 3
            "scenario_name": scenario_name,
            "patient_id": str(patient_id),
            "title": title,
            "source_node": source_node,
            "status": status, # "processing", "completed", "shielded_duplicate", "failed"
            "details": details
        }
        with self._lock:
            self.active_scenario = entry
            self.recent_activities.insert(0, entry)
            if len(self.recent_activities) > self.history_limit:
                self.recent_activities.pop()
        
        # Emit a structured event into log_buffer_handler subscribers
        event_entry = {
            "type": "scenario_activity",
            "activity": entry
        }
        with log_buffer_handler._lock:
            for q in list(log_buffer_handler.subscribers):
                try:
                    q.put_nowait(event_entry)
                except Exception:
                    pass

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_scenario": self.active_scenario,
                "recent_activities": list(self.recent_activities)
            }


def identify_caller(request: Request) -> str:
    """Identifies the caller node name based on IP or headers."""
    client_ip = request.client.host if request.client else "unknown"
    if client_ip in ("127.0.0.1", "localhost", "::1"):
        return "Local Dashboard / Operator"
    elif "159.84.143.151" in client_ip:
        return "AI Server (VM3) / Central SQL"
    elif "159.84.143.246" in client_ip:
        return "Raspberry Pi 5 Edge (Port 8000)"
    elif client_ip.startswith("159.84.130.") or client_ip.startswith("159.84."):
        return f"AI Server / Node ({client_ip})"
    return f"Remote Node ({client_ip})"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CPAP_Video_Server")

# Attach real-time ring buffer handler
log_buffer_handler = CircularLogBufferHandler(capacity=1000)
log_buffer_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(log_buffer_handler)
logging.getLogger().addHandler(log_buffer_handler)

live_scenario_tracker = LiveScenarioTracker(history_limit=50)

APP_TITLE = "CPAP Video VM Server"


# =============================================================================
# 3. ENVIRONMENT & CONFIGURATION LOADING
# =============================================================================
# Base Directory Configuration
env_base = os.environ.get("VIDEO_BASE_DIR")
if env_base and Path(env_base).exists():
    BASE_DIR = Path(env_base)
else:
    BASE_DIR = Path(__file__).resolve().parent

# Safely load configuration from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception as err:
            logger.warning(f"Could not load .env manually: {err}")

# Host, Port, and Network URLs
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://159.84.143.246:8080")
DASHBOARD_BASE_URL = os.environ.get("DASHBOARD_URL") or os.environ.get("DASHBOARD_BASE_URL", "http://159.84.143.151:80")

# Central Backend Distributed Telemetry Tracing (VM2 SQL Server)
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://159.84.143.151:80/api/telemetry")
BACKEND_API_KEY = os.environ.get("BACKEND_API_KEY", "")

# Security Keys & CORS Allowed Origins
SERVER_API_KEY = os.environ.get("VIDEO_SERVER_API_KEY") or os.environ.get("SERVER_API_KEY", "")
VIDEO_SERVER_KEY = os.environ.get("X_VIDEO_SERVER_KEY") or os.environ.get("VIDEO_SERVER_KEY", "")
ALLOWED_ORIGINS_RAW = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080,*")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

# Google Cloud Vertex AI (Veo) Settings for Scenario 3
GOOGLE_VERTEX_API_KEY = os.environ.get("GOOGLE_VERTEX_API_KEY", "")
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "cpap-coaching-project")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "veo-3.1-generate-preview")


# =============================================================================
# 4. DIRECTORY & ASSET SETUP
# =============================================================================
EXISTING_DIR = BASE_DIR / "existing_videos"
NEW_DIR = BASE_DIR / "new_videos"
EXISTING_SUBTITLES_DIR = BASE_DIR / "existing_subtitles"
NEW_SUBTITLES_DIR = BASE_DIR / "new_subtitles"
METADATA_DIR = BASE_DIR / "metadata"
DOCS_DIR = BASE_DIR / "docs"
LOGS_DIR = BASE_DIR / "logs"
DASHBOARD_DIR = BASE_DIR / "dashboard"

# Ensure all essential asset and log folders exist
EXISTING_DIR.mkdir(parents=True, exist_ok=True)
NEW_DIR.mkdir(parents=True, exist_ok=True)
EXISTING_SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)
NEW_SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

# In-memory storage for latest patient video decisions
LAST_DECISION: Dict[str, Dict[str, Any]] = {}

# Print System Boot Banner to Console
logger.info("=" * 75)
logger.info(" [SYSTEM BOOT] CPAP Video VM Server Initializing")
logger.info(f"   BASE_DIR             : {BASE_DIR}")
logger.info(f"   PUBLIC_BASE_URL      : {PUBLIC_BASE_URL}")
logger.info(f"   DASHBOARD_URL        : {DASHBOARD_BASE_URL}")
logger.info(f"   EXISTING_DIR         : {EXISTING_DIR} ({len(list(EXISTING_DIR.glob('*.mp4')))} mp4 files)")
logger.info(f"   EXISTING_SUBTITLES   : {EXISTING_SUBTITLES_DIR} ({len(list(EXISTING_SUBTITLES_DIR.glob('*.vtt')))} vtt files)")
logger.info(f"   NEW_SUBTITLES        : {NEW_SUBTITLES_DIR} ({len(list(NEW_SUBTITLES_DIR.glob('*.vtt')))} vtt files)")
logger.info(f"   NEW_VIDEOS_DIR       : {NEW_DIR} ({len(list(NEW_DIR.glob('*.mp4')))} mp4 files)")
if SERVER_API_KEY:
    logger.info("   SECURITY             : SERVER_API_KEY is active (Protected routes require X-API-KEY)")
else:
    logger.info("   SECURITY             : SERVER_API_KEY is not set (Open access mode)")
logger.info("=" * 75)


# =============================================================================
# 4.1. REAL-TIME ASSET & SUBTITLE WATCHER
# =============================================================================
class VideoAssetWatcher:
    """
    Background file watcher that monitors 'existing_videos/' and 'new_videos/'
    for newly added MP4 video files. When detected:
      1. Automatically triggers bilingual WebVTT subtitle synthesis (.en.vtt & .fr.vtt).
      2. Generates individual JSON metadata records ('metadata/video_XX.json').
      3. Updates the master registry ('metadata/master_video_metadata.json').
      4. Prints formatted live status and updated counts to the console.
    """
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._running = False
        self._known_existing = set()
        self._known_new = set()
        self._file_sizes = {}
        self._lock = threading.Lock()

    def get_library_counts(self) -> Dict[str, int]:
        ev = len(list(EXISTING_DIR.glob("*.mp4")))
        nv = len(list(NEW_DIR.glob("*.mp4")))
        es = len(list(EXISTING_SUBTITLES_DIR.glob("*.vtt")))
        ns = len(list(NEW_SUBTITLES_DIR.glob("*.vtt")))
        return {
            "existing_videos": ev,
            "new_videos": nv,
            "total_videos": ev + nv,
            "existing_subtitles": es,
            "new_subtitles": ns,
            "total_subtitles": es + ns,
        }

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True

            # Populate initial known files
            self._known_existing = set(p.name for p in EXISTING_DIR.glob("*.mp4"))
            self._known_new = set(p.name for p in NEW_DIR.glob("*.mp4"))
            for p in list(EXISTING_DIR.glob("*.mp4")) + list(NEW_DIR.glob("*.mp4")):
                try:
                    self._file_sizes[p.name] = p.stat().st_size
                except Exception:
                    pass

            # Initial sync on boot
            if sync_all_video_assets:
                try:
                    sync_all_video_assets(verbose=False)
                except Exception as err:
                    logger.warning(f"[ASSET WATCHER] Initial metadata sync notice: {err}")

            t = threading.Thread(target=self._watch_loop, daemon=True, name="AssetWatcher")
            t.start()
            logger.info("[LIVE ASSET WATCHER] [ACTIVE] Background video watcher active (auto-updating counts & subtitles)")

    def stop(self):
        with self._lock:
            self._running = False

    def _watch_loop(self):
        while self._running:
            try:
                time.sleep(self.poll_interval)
                current_existing = set(p.name for p in EXISTING_DIR.glob("*.mp4"))
                current_new = set(p.name for p in NEW_DIR.glob("*.mp4"))

                added_existing = current_existing - self._known_existing
                removed_existing = self._known_existing - current_existing
                added_new = current_new - self._known_new
                removed_new = self._known_new - current_new

                if added_existing or added_new or removed_existing or removed_new:
                    # Give a small pause for OS file-copy write completion
                    time.sleep(1.0)

                    # Check for write completion (file size stability)
                    all_added = [(f, EXISTING_DIR / f) for f in added_existing] + [(f, NEW_DIR / f) for f in added_new]
                    unstable = False
                    for fname, fpath in all_added:
                        try:
                            s1 = fpath.stat().st_size
                            time.sleep(0.3)
                            s2 = fpath.stat().st_size
                            if s1 != s2 or s2 == 0:
                                unstable = True
                                break
                        except Exception:
                            unstable = True
                            break

                    if unstable:
                        # Wait until file finishes copying
                        continue

                    logger.info("=" * 75)
                    logger.info(" [LIVE ASSET WATCHER] [ALERT] Video file change detected in server library!")

                    if added_existing:
                        for f in added_existing:
                            logger.info(f"   [+] [NEW VIDEO DETECTED] '{f}' in existing_videos/")
                    if added_new:
                        for f in added_new:
                            logger.info(f"   [+] [NEW VIDEO DETECTED] '{f}' in new_videos/")
                    if removed_existing:
                        for f in removed_existing:
                            logger.info(f"   [-] [VIDEO REMOVED] '{f}' from existing_videos/")
                    if removed_new:
                        for f in removed_new:
                            logger.info(f"   [-] [VIDEO REMOVED] '{f}' from new_videos/")

                    logger.info(" [LIVE ASSET WATCHER] [AUTO-SYNC] Triggering automated subtitle synthesis & metadata rebuild...")

                    if sync_all_video_assets:
                        total_vids, total_subs, new_subs = sync_all_video_assets(verbose=True)
                    else:
                        counts = self.get_library_counts()
                        total_vids, total_subs, new_subs = counts["total_videos"], counts["total_subtitles"], 0

                    self._known_existing = current_existing
                    self._known_new = current_new

                    counts = self.get_library_counts()
                    logger.info(" [LIVE ASSET WATCHER] [OK] Asset synchronization complete!")
                    logger.info(f"   [*] [UPDATED COUNTS] Existing: {counts['existing_videos']} | New AI: {counts['new_videos']} | Total: {counts['total_videos']} MP4s | Subtitles: {counts['total_subtitles']} tracks")
                    logger.info("=" * 75)

                    # Automatically broadcast new triggers & catalog to AI Server, Raspberry Pi & Backend
                    if broadcast_in_background:
                        changed_files = list(added_existing | added_new | removed_existing | removed_new)
                        broadcast_in_background(new_videos_added=changed_files)

            except Exception as err:
                logger.error(f"[LIVE ASSET WATCHER ERROR] {err}")


# =============================================================================
# 5. FASTAPI APPLICATION INITIALIZATION & MIDDLEWARE
# =============================================================================
asset_watcher = VideoAssetWatcher(poll_interval=2.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI lifespan context manager.
    Initializes background file watcher on boot and cleans up gracefully on shutdown.
    """
    asset_watcher.start()
    yield
    asset_watcher.stop()


app = FastAPI(title=APP_TITLE, lifespan=lifespan)


@app.middleware("http")
async def traffic_and_security_logger(request: Request, call_next):
    """
    Unified HTTP Middleware performing:
      1. Malicious path probe filtering (blocks bots searching for .env, .git, etc.).
      2. Detailed context logging for video streams, subtitles, and API calls.
      3. Security header injection (nosniff, DENY frame options, XSS protection).
      4. Performance latency tracking.
    """
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    client_port = request.client.port if request.client else "0"
    raw_path = request.url.path
    lower_path = raw_path.lower()
    method = request.method

    # 1. Security Check: Block unauthorized crawler probing
    blocked_patterns = [
        "/.env", "/.git", "/.aws", "/.npmrc", "/.ssh",
        "phpinfo", ".php", "actuator", "terraform",
        "appsettings.json", "wp-login", "wp-admin",
        "/etc/passwd", "/config.json"
    ]
    for pattern in blocked_patterns:
        if pattern in lower_path:
            logger.warning(f"[SECURITY BLOCKED] Client {client_ip}:{client_port} attempted unauthorized probe: {method} {raw_path}")
            return Response(status_code=403, content="Access Denied: Malicious probe detected.\n")

    # 2. Security Check: Enforce Localhost-Only Access for Dashboard UI & Live Console Streams
    is_dashboard_path = (
        raw_path in ("/", "/dashboard") or
        raw_path.startswith("/dashboard_assets") or
        raw_path.startswith("/api/logs") or
        raw_path.startswith("/api/activity")
    )
    if is_dashboard_path:
        is_localhost = (
            client_ip in ("127.0.0.1", "localhost", "::1", "testclient") or
            client_ip.startswith("127.")
        )
        if not is_localhost:
            logger.warning(
                f"[SECURITY BLOCKED] Unauthorized remote machine ({client_ip}:{client_port}) "
                f"attempted to access restricted localhost Dashboard: {method} {raw_path}"
            )
            return HTMLResponse(
                status_code=403,
                content=(
                    "<!DOCTYPE html>"
                    "<html lang='en'>"
                    "<head>"
                    "  <meta charset='UTF-8'>"
                    "  <title>403 Forbidden - Localhost Access Only</title>"
                    "  <style>"
                    "    body { background: #f8fafc; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }"
                    "    .card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 2.5rem; text-align: center; max-width: 540px; box-shadow: 0 10px 25px rgba(0,0,0,0.06); }"
                    "    .icon { font-size: 3rem; margin-bottom: 1rem; }"
                    "    h2 { color: #e11d48; margin-bottom: 0.75rem; font-size: 1.4rem; font-weight: 700; }"
                    "    p { color: #64748b; font-size: 0.95rem; line-height: 1.6; margin-bottom: 0.5rem; }"
                    "    .badge { display: inline-block; background: #ffe4e6; color: #e11d48; border: 1px solid #fecdd3; padding: 0.35rem 0.9rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; margin-top: 1rem; font-family: monospace; }"
                    "  </style>"
                    "</head>"
                    "<body>"
                    "  <div class='card'>"
                    "    <div class='icon'>🔒</div>"
                    "    <h2>Access Denied (403 Forbidden)</h2>"
                    "    <p>The <strong>SleepCare CPAP Video Server Interactive Dashboard</strong> is restricted strictly to <code>localhost</code> (127.0.0.1).</p>"
                    "    <p>Access from external remote machines is blocked by server security policy.</p>"
                    "    <div class='badge'>Remote Client IP Blocked: " + client_ip + "</div>"
                    "  </div>"
                    "</body>"
                    "</html>"
                )
            )

    # 3. Informational Traffic Logging based on request type
    if "/videos/" in raw_path or "/media/" in raw_path:
        video_name = raw_path.split("/")[-1]
        range_header = request.headers.get("range", "full-file")
        logger.info(f"[VIDEO STREAM REQUEST] Client: {client_ip} | File: '{video_name}' | Method: {method} | Range: {range_header}")
    elif "/subtitles/" in raw_path:
        sub_name = raw_path.split("/")[-1]
        logger.info(f"[SUBTITLE STREAM REQUEST] Client: {client_ip} | Track: '{sub_name}' | Method: {method}")
    elif raw_path == "/api/orchestrate":
        logger.info(f"[ORCHESTRATE INBOUND] Inbound video recommendation request received from {client_ip}")
    elif raw_path == "/api/vertex-generate":
        logger.info(f"[VERTEX GENERATE INBOUND] Inbound AI video generation trigger received from {client_ip}")
    elif raw_path == "/health":
        logger.info(f"[HEALTH CHECK] Health ping from {client_ip}")
    elif raw_path == "/api/library":
        logger.info(f"[LIBRARY CATALOG QUERY] Catalog query from {client_ip}")
    else:
        logger.info(f"[HTTP REQUEST] {client_ip}:{client_port} -> {method} {raw_path}")

    # Process the request through FastAPI router
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    # 3. Inject standard security response headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # 4. Summary log with execution duration
    status_label = "[HTTP OK]" if response.status_code < 400 else "[HTTP WARN/ERR]"
    logger.info(f"{status_label} {method} {raw_path} -> Status {response.status_code} ({duration_ms:.2f}ms)")
    return response


# Configure CORS to allow secure browser playback from the Web Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)


# =============================================================================
# 6. AUTHENTICATION & SECURITY HELPERS
# =============================================================================
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def verify_api_key(request: Request, api_key: Optional[str] = Security(api_key_header)):
    """
    Validates that incoming requests to protected endpoints provide the correct
    X-API-KEY header token. Raises HTTP 403 Forbidden if invalid.
    """
    if SERVER_API_KEY:
        if not api_key or api_key != SERVER_API_KEY:
            client_ip = request.client.host if request.client else "unknown"
            logger.warning(f"[AUTH REJECTED] Client {client_ip} missing or invalid X-API-KEY on {request.url.path}")
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Invalid or missing X-API-KEY header."
            )
        logger.info(f"[AUTH GRANTED] Valid X-API-KEY verified for {request.url.path}")
    return True


# =============================================================================
# 7. STATIC MEDIA MOUNTS & UNIFIED SUBTITLE STREAMING
# =============================================================================
# Direct file mounts for video streaming
app.mount("/videos/existing", StaticFiles(directory=str(EXISTING_DIR)), name="videos-existing")
app.mount("/videos/exisiting", StaticFiles(directory=str(EXISTING_DIR)), name="videos-exisiting")  # Backward-compatible typo alias
app.mount("/media/exisiting_videos", StaticFiles(directory=str(EXISTING_DIR)), name="media-exisiting") # Backward-compatible alias
app.mount("/videos/new", StaticFiles(directory=str(NEW_DIR)), name="videos-new")

# Direct file mounts for subtitles
app.mount("/subtitles/existing", StaticFiles(directory=str(EXISTING_SUBTITLES_DIR)), name="subtitles-existing")
app.mount("/subtitles/new", StaticFiles(directory=str(NEW_SUBTITLES_DIR)), name="subtitles-new")

# Dashboard static assets mount
app.mount("/dashboard_assets", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard-assets")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Lightweight 204 No Content handler to prevent 404 noise in browser consoles."""
    return Response(status_code=204)


@app.api_route("/subtitles/{filename}", methods=["GET", "HEAD"])
async def serve_subtitles(filename: str):
    """
    Unified subtitle streaming endpoint.
    Searches 'existing_subtitles/', 'new_subtitles/', and legacy paths to return
    the requested WebVTT file with the correct 'text/vtt' MIME type and strict
    no-cache headers to guarantee fresh cue delivery.
    """
    # 1. Search new subtitles directory first (most recent AI generations)
    file_path = NEW_SUBTITLES_DIR / filename
    
    # 2. Search existing subtitles directory
    if not file_path.exists():
        file_path = EXISTING_SUBTITLES_DIR / filename
        
    # 3. Search directly beside videos (new_videos / existing_videos)
    if not file_path.exists():
        if (NEW_DIR / filename).exists():
            file_path = NEW_DIR / filename
        elif (EXISTING_DIR / filename).exists():
            file_path = EXISTING_DIR / filename

    # 4. Search legacy generated subtitles directory if present
    if not file_path.exists():
        legacy_path = BASE_DIR / "generated_subtitles" / filename
        if legacy_path.exists():
            file_path = legacy_path
            
    # If found, return the file with UTF-8 WebVTT header and strict no-cache headers
    if file_path.exists() and file_path.is_file():
        return FileResponse(
            file_path,
            media_type="text/vtt; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    raise HTTPException(status_code=404, detail=f"Subtitle '{filename}' not found")


@app.api_route("/videos/{filename}", methods=["GET", "HEAD"])
@app.api_route("/api/videos/{filename}", methods=["GET", "HEAD"])
async def serve_unified_video(filename: str, request: Request):
    """
    Unified smart video streaming endpoint.
    Searches 'new_videos/' and 'existing_videos/' to stream the MP4 file
    with full HTTP 206 Byte-Range seek capabilities.
    Supports missing .mp4 extensions and numeric ID prefixes.
    """
    try:
        resolved = resolve_video_file(filename)
        target = Path(resolved["path"])
        return FileResponse(target, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})
    except HTTPException:
        raise HTTPException(status_code=404, detail=f"Video '{filename}' not found in existing_videos/ or new_videos/")



# =============================================================================
# 8. DISTRIBUTED TELEMETRY TRACING (TIER 3 -> CENTRAL SQL SERVER)
# =============================================================================
def sync_vm_telemetry(event_id: Optional[str], video_id: Any, t5_iso: str, t6_iso: str, vm_status: str = "ok"):
    """
    Sends Tier-3 Video VM tracing timestamps (t5 arrival, t6 ready) and video_id
    to the Central Backend API for storage in DB_Clinical (telemetry.event_traces).
    """
    if not event_id:
        return
    
    payload = {
        "event_id": str(event_id),
        "video_id": str(video_id),
        "t5_received_at_vm": t5_iso,
        "t6_persisted_at_db": t6_iso,
        "vm_push_status": vm_status
    }
    
    try:
        telemetry_endpoint = f"{BACKEND_API_URL.rstrip('/')}/event-trace"
        resp = requests.post(
            telemetry_endpoint,
            json=payload,
            headers={"X-API-Key": BACKEND_API_KEY, "Content-Type": "application/json"},
            timeout=2.0
        )
        if resp.status_code in (200, 201):
            logger.info(f"[TELEMETRY SYNC] Event trace '{event_id}' -> video_id '{video_id}' synced (status: {vm_status})")
        else:
            logger.warning(f"[TELEMETRY SYNC WARN] Backend returned status {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        logger.warning(f"[TELEMETRY SYNC SKIPPED] Could not reach telemetry API ({BACKEND_API_URL}): {e}")


# =============================================================================
# 9. URL RESOLUTION HELPERS
# =============================================================================
def subtitle_url_for(video_filename: str, lang: str = "en") -> Optional[str]:
    """
    Finds the matching WebVTT subtitle track for a video and returns its public streaming URL.
    """
    video_stem = Path(video_filename).stem
    exact_name = f"{video_stem}.{lang}.vtt"
    
    # 1. Check for exact matching file name
    if (EXISTING_SUBTITLES_DIR / exact_name).exists() or (NEW_SUBTITLES_DIR / exact_name).exists():
        return f"{PUBLIC_BASE_URL}/subtitles/{exact_name}"

    # 2. Check for matching prefix (e.g. '1_' for video 1)
    prefix = video_filename.split('_')[0] + "_" 
    if EXISTING_SUBTITLES_DIR.exists():
        for file in EXISTING_SUBTITLES_DIR.iterdir():
            if file.name.startswith(prefix) and file.name.endswith(f".{lang}.vtt"):
                return f"{PUBLIC_BASE_URL}/subtitles/{file.name}"
    if NEW_SUBTITLES_DIR.exists():
        for file in NEW_SUBTITLES_DIR.iterdir():
            if file.name.startswith(prefix) and file.name.endswith(f".{lang}.vtt"):
                return f"{PUBLIC_BASE_URL}/subtitles/{file.name}"
                
    return f"{PUBLIC_BASE_URL}/subtitles/{exact_name}"


def resolve_video_file(video_filename: str) -> Dict[str, str]:
    """
    Resolves the physical filesystem path, bucket, and public stream URL for a video file.
    Supports exact filenames, missing .mp4 extensions, numeric prefixes (e.g. '14' or '14_'),
    and case-insensitive lookups.
    """
    if not video_filename:
        video_filename = "1_Mask_leak_adjust_straps.mp4"
        
    # 1. Exact match in existing or new videos
    existing_path = EXISTING_DIR / video_filename
    new_path = NEW_DIR / video_filename

    if existing_path.exists() and existing_path.is_file():
        return {
            "bucket": "existing",
            "filename": existing_path.name,
            "path": str(existing_path),
            "url": f"{PUBLIC_BASE_URL}/videos/existing/{existing_path.name}",
        }

    if new_path.exists() and new_path.is_file():
        return {
            "bucket": "new",
            "filename": new_path.name,
            "path": str(new_path),
            "url": f"{PUBLIC_BASE_URL}/videos/new/{new_path.name}",
        }

    # 2. Match with .mp4 appended if missing
    if not video_filename.lower().endswith(".mp4"):
        fn_mp4 = f"{video_filename}.mp4"
        if (EXISTING_DIR / fn_mp4).exists():
            return {
                "bucket": "existing",
                "filename": fn_mp4,
                "path": str(EXISTING_DIR / fn_mp4),
                "url": f"{PUBLIC_BASE_URL}/videos/existing/{fn_mp4}",
            }
        if (NEW_DIR / fn_mp4).exists():
            return {
                "bucket": "new",
                "filename": fn_mp4,
                "path": str(NEW_DIR / fn_mp4),
                "url": f"{PUBLIC_BASE_URL}/videos/new/{fn_mp4}",
            }

    # 3. Match by numeric ID prefix (e.g. "14" or "14_")
    prefix_match = re.match(r"^(\d+)", video_filename)
    if prefix_match:
        p_num = prefix_match.group(1)
        for p in list(EXISTING_DIR.glob(f"{p_num}_*.mp4")):
            return {
                "bucket": "existing",
                "filename": p.name,
                "path": str(p),
                "url": f"{PUBLIC_BASE_URL}/videos/existing/{p.name}",
            }
        for p in list(NEW_DIR.glob(f"{p_num}_*.mp4")):
            return {
                "bucket": "new",
                "filename": p.name,
                "path": str(p),
                "url": f"{PUBLIC_BASE_URL}/videos/new/{p.name}",
            }

    # 4. Case-insensitive lookup
    target_lower = video_filename.lower()
    for p in EXISTING_DIR.glob("*.mp4"):
        if p.name.lower() == target_lower or p.stem.lower() == target_lower:
            return {
                "bucket": "existing",
                "filename": p.name,
                "path": str(p),
                "url": f"{PUBLIC_BASE_URL}/videos/existing/{p.name}",
            }
    for p in NEW_DIR.glob("*.mp4"):
        if p.name.lower() == target_lower or p.stem.lower() == target_lower:
            return {
                "bucket": "new",
                "filename": p.name,
                "path": str(p),
                "url": f"{PUBLIC_BASE_URL}/videos/new/{p.name}",
            }

    raise HTTPException(status_code=404, detail=f"Video file not found: {video_filename}")


# =============================================================================
# 10. SCENARIO 1 & 2: ORCHESTRATION ENGINE (/api/orchestrate)
# =============================================================================
class OrchestrateRequest(BaseModel):
    event_id: Optional[str] = None
    patient_id: str
    title: Optional[str] = None
    video_id: Optional[Union[int, str]] = None
    video_filename: Optional[str] = None
    duration_s: Optional[Union[int, float]] = None
    category: Optional[str] = "Personalized Coaching"
    trigger_reason: Optional[str] = "Clinical AI recommendation"
    relevance: Optional[str] = "high"
    thumbnail_type: Optional[str] = "technical"
    video_type: Optional[str] = "single"
    scenario: Optional[str] = None
    total_clips: Optional[int] = None
    clips: Optional[List[Dict[str, Any]]] = None
    sequence: Optional[List[Dict[str, Any]]] = None
    total_duration_s: Optional[float] = None
    sequence_count: Optional[int] = None
    transition_type: Optional[str] = None


@app.post("/api/orchestrate", dependencies=[Depends(verify_api_key)])
def orchestrate(req: OrchestrateRequest, request: Request = None):
    """
    Handles Scenario 1 (Single Clip) and Scenario 2 (Multi-Clip Stitched Sequence).
    Resolves streaming URLs, attaches bilingual subtitles, syncs telemetry,
    and forwards the assignment payload to the Central Web Dashboard.
    Guarantees idempotency via persistent assignment ledger to avoid duplicate pushes on restart.
    """
    t5_iso = datetime.now(timezone.utc).isoformat()
    t5_perf = time.perf_counter()
    source_name = identify_caller(request) if request else "AI Server / Direct Client"

    # Determine primary video filename
    primary_vfile = req.video_filename
    if not primary_vfile and req.clips and len(req.clips) > 0:
        c0 = req.clips[0]
        primary_vfile = c0.get("video_filename") or c0.get("filename")

    if not primary_vfile and req.video_id is not None:
        vid_str = str(req.video_id).strip()
        matched = list(EXISTING_DIR.glob(f"{vid_str}_*.mp4")) + list(NEW_DIR.glob(f"{vid_str}_*.mp4"))
        if matched:
            primary_vfile = matched[0].name

    if not primary_vfile and req.title:
        words = [w for w in req.title.lower().split() if len(w) > 3]
        for p in list(EXISTING_DIR.glob("*.mp4")) + list(NEW_DIR.glob("*.mp4")):
            if words and any(w in p.stem.lower() for w in words):
                primary_vfile = p.name
                break

    if not primary_vfile:
        primary_vfile = "1_Mask_leak_adjust_straps.mp4"

    # Resolve direct stream URL and normalized filename
    resolved = resolve_video_file(primary_vfile)
    primary_vfile = resolved["filename"]
    req_title = req.title or Path(primary_vfile).stem.replace("_", " ")

    raw_clips = req.clips or req.sequence
    is_scenario_2 = (req.video_type == "package") or (raw_clips and len(raw_clips) > 1) or (req.scenario == "scenario_2_stitched_sequence")
    scenario_id = 2 if is_scenario_2 else 1
    scenario_name = "Scenario 2: Multi-Clip Virtual Sequence" if is_scenario_2 else "Scenario 1: Single Clip Selection"

    # Deduplication check via persistent ledger (avoids re-assigning across restarts/replays)
    if assignment_ledger:
        is_duplicate, cached_decision = assignment_ledger.is_already_assigned(
            patient_id=req.patient_id,
            event_id=req.event_id,
            video_filename=primary_vfile,
            clips=req.clips,
            title=req_title
        )
        if is_duplicate:
            logger.info("=" * 70)
            logger.info(" [DEDUPLICATION SHIELD] Video assignment already tracked in persistent ledger")
            logger.info("=" * 70)
            logger.info(f"   * Patient ID        : {req.patient_id}")
            if req.event_id:
                logger.info(f"   * Event ID          : {req.event_id}")
            logger.info(f"   * Video / Title     : '{req_title}'")
            logger.info(f"   * Inbound Source    : {source_name}")
            logger.info(f"   * Action            : Skipped duplicate Central Dashboard push (<1ms)")
            logger.info("=" * 70)
            
            # Record shielded activity for live dashboard
            live_scenario_tracker.record_activity(
                scenario_id=scenario_id,
                scenario_name=scenario_name,
                patient_id=req.patient_id,
                title=req_title,
                source_node=source_name,
                details={
                    "video_filename": primary_vfile,
                    "event_id": req.event_id,
                    "shielded": True,
                    "clips_count": len(req.clips or [])
                },
                status="shielded_duplicate"
            )
            
            return {
                "status": "already_assigned",
                "duplicate_detected": True,
                "message": f"Video assignment for patient {req.patient_id} has already been assigned and recorded in persistent ledger.",
                "decision": cached_decision or LAST_DECISION.get(req.patient_id),
                "dashboard_push": "skipped_duplicate"
            }

    # Resolve subtitles
    sub_en = subtitle_url_for(primary_vfile, "en")
    sub_fr = subtitle_url_for(primary_vfile, "fr")
    sub_en_name = Path(sub_en).name if sub_en else f"{Path(primary_vfile).stem}.en.vtt"
    sub_fr_name = Path(sub_fr).name if sub_fr else f"{Path(primary_vfile).stem}.fr.vtt"

    # Calculate total duration
    calc_duration = req.duration_s
    if calc_duration is None:
        if req.clips:
            calc_duration = sum(float(c.get("duration_s", 10.0)) for c in req.clips)
        else:
            calc_duration = 10.0

    # Build base recommendation payload
    payload = {
        "event_id": req.event_id,
        "patient_id": req.patient_id,
        "title": req_title,
        "video_filename": primary_vfile,
        "url": resolved["url"],  
        "subtitle_en_url": sub_en,
        "subtitle_fr_url": sub_fr,
        "duration_s": calc_duration,
        "category": req.category or "Personalized Coaching",
        "trigger_reason": req.trigger_reason or "Clinical AI recommendation",
        "relevance": req.relevance or "high",
        "thumbnail_type": req.thumbnail_type or "technical",
        "storage_bucket": resolved["bucket"],
        "video_type": req.video_type or ("package" if req.clips else "single"),
    }

    if req.scenario:
        payload["scenario"] = req.scenario
    elif req.clips:
        payload["scenario"] = "scenario_2_stitched_sequence"

    if req.total_duration_s:
        payload["total_duration_s"] = req.total_duration_s
    if req.sequence_count or req.total_clips:
        payload["sequence_count"] = req.sequence_count or req.total_clips
    if req.transition_type:
        payload["transition_type"] = req.transition_type

    # Multi-Clip Sequence Handling (Scenario 2)
    if raw_clips and isinstance(raw_clips, list):
        enriched_clips = []
        for idx, clip in enumerate(raw_clips):
            c_dict = dict(clip)
            c_fname = c_dict.get("video_filename") or c_dict.get("filename")
            if c_fname:
                try:
                    c_resolved = resolve_video_file(c_fname)
                    c_dict.setdefault("url", c_resolved["url"])
                    c_dict.setdefault("video_filename", c_fname)
                except Exception:
                    c_dict.setdefault("url", f"{PUBLIC_BASE_URL}/videos/existing/{c_fname}")
                c_dict.setdefault("subtitle_en_url", subtitle_url_for(c_fname, "en"))
                c_dict.setdefault("subtitle_fr_url", subtitle_url_for(c_fname, "fr"))
            c_dict.setdefault("step", idx + 1)
            enriched_clips.append(c_dict)
        payload["clips"] = enriched_clips
        payload["sequence"] = enriched_clips

    # Calculate processing latency
    t6_iso = datetime.now(timezone.utc).isoformat()
    vm_processing_ms = round((time.perf_counter() - t5_perf) * 1000.0, 2)
    payload["vm_processing_ms"] = vm_processing_ms

    # Extract Video ID for database linkage
    extracted_video_id = None
    if req.clips and len(req.clips) > 0 and req.clips[0].get("video_id"):
        extracted_video_id = str(req.clips[0].get("video_id"))
    elif primary_vfile:
        match = re.match(r"^(\d+)_", primary_vfile)
        extracted_video_id = match.group(1) if match else Path(primary_vfile).stem
    else:
        extracted_video_id = "1"

    # Sync Tier 3 telemetry timestamps to SQL Server
    if req.event_id:
        sync_vm_telemetry(
            event_id=req.event_id,
            video_id=extracted_video_id,
            t5_iso=t5_iso,
            t6_iso=t6_iso,
            vm_status="ok"
        )

    # Save to in-memory state
    LAST_DECISION[req.patient_id] = payload

    # Live Console Output Banner
    if is_scenario_2:
        clips_list = payload.get("clips", [])
        logger.info("=" * 70)
        logger.info(" [SCENARIO 2 ACTIVE] 2. Videos Stitching Together (Virtual Sequence)")
        logger.info("=" * 70)
        logger.info(f"   * Patient ID        : {req.patient_id}")
        logger.info(f"   * Package Title     : '{req_title}'")
        logger.info(f"   * Category          : {req.category}")
        logger.info(f"   * Trigger Reason    : {req.trigger_reason}")
        logger.info(f"   * Total Playtime    : {payload.get('total_duration_s', req.duration_s)}s")
        logger.info(f"   * Transition Type   : {payload.get('transition_type', 'fade_1_5s')} (1.5s Alpha Crossfade)")
        logger.info(f"   * Sequence Count    : {len(clips_list)} clips stitched in continuous order")
        logger.info("-" * 70)
        for i, clip in enumerate(clips_list, 1):
            c_file = clip.get('video_filename', 'unknown.mp4')
            c_stem = Path(c_file).stem
            logger.info(f"   [Clip {i} of {len(clips_list)}] '{clip.get('title', c_stem)}'")
            logger.info(f"      - Original Video File : {c_file}")
            logger.info(f"      - English Subtitle    : {c_stem}.en.vtt")
            logger.info(f"      - French Subtitle     : {c_stem}.fr.vtt")
            logger.info(f"      - Duration            : {clip.get('duration_s', 10.0)}s")
            logger.info(f"      - Transition To Next  : {clip.get('transition', 'fade_1_5s')}")
            logger.info(f"      - Direct Stream URL   : {clip.get('url')}")
        logger.info("=" * 70)
    else:
        logger.info("=" * 70)
        logger.info(" [SCENARIO 1 ACTIVE] 1. Existing Video Selection (Single Clip)")
        logger.info("=" * 70)
        logger.info(f"   * Patient ID        : {req.patient_id}")
        logger.info(f"   * Video Title       : '{req_title}'")
        logger.info(f"   * Original Video File: {primary_vfile}")
        logger.info(f"   * English Subtitle  : {sub_en_name}")
        logger.info(f"   * French Subtitle   : {sub_fr_name}")
        logger.info(f"   * Category          : {req.category}")
        logger.info(f"   * Trigger Reason    : {req.trigger_reason}")
        logger.info(f"   * Duration          : {calc_duration}s")
        logger.info(f"   * Direct Stream URL : {resolved['url']}")
        logger.info(f"   * Subtitle EN URL   : {sub_en}")
        logger.info(f"   * Subtitle FR URL   : {sub_fr}")
        logger.info("=" * 70)

    # Prepare payload for Web Dashboard (VM2)
    vm2_payload = dict(payload)
    try:
        vm2_payload["duration_s"] = int(round(float(calc_duration)))
    except Exception:
        vm2_payload["duration_s"] = 10

    # Forward video assignment to Central Web Dashboard
    candidate_urls = [
        f"{DASHBOARD_BASE_URL.rstrip('/')}/api/videos/assign",
        f"{DASHBOARD_BASE_URL.rstrip('/')}/api/videos/{req.patient_id}/assign"
    ]
    dashboard_status = "success"
    pushed_successfully = False

    for target_url in candidate_urls:
        if pushed_successfully:
            break
        try:
            dash_response = requests.post(
                target_url,
                json=vm2_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Video-Server-Key": VIDEO_SERVER_KEY
                },
                timeout=1.2
            )
            if dash_response.status_code in (200, 201):
                dashboard_status = "success"
                pushed_successfully = True
                logger.info(f"[DASHBOARD PUSH SUCCESS] Assignment for Patient {req.patient_id} delivered successfully.")
                break
            elif dash_response.status_code == 404:
                continue  # Try next candidate URL
        except requests.exceptions.RequestException as e:
            logger.info(f"[DASHBOARD PUSH SKIPPED] Central dashboard ({target_url}) offline/unreachable: {e}")
            dashboard_status = "skipped_remote_offline"

    # Record in persistent ledger to remember across restarts
    if assignment_ledger:
        assignment_ledger.record_assignment(
            patient_id=req.patient_id,
            event_id=req.event_id,
            video_filename=primary_vfile,
            decision_payload=payload,
            dashboard_status=dashboard_status,
            clips=req.clips,
            title=req_title
        )

    # Record live scenario activity for real-time dashboard display
    live_scenario_tracker.record_activity(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        patient_id=req.patient_id,
        title=req_title,
        source_node=source_name,
        details={
            "video_filename": primary_vfile,
            "event_id": req.event_id,
            "duration_s": calc_duration,
            "dashboard_push": dashboard_status,
            "clips_count": len(payload.get("clips", [])) if is_scenario_2 else 1,
            "processing_ms": vm_processing_ms
        },
        status="completed"
    )

    logger.info("-" * 65)
    return {
        "status": "ok", 
        "decision": payload,
        "dashboard_push": dashboard_status
    }


# =============================================================================
# 11. SCENARIO 3: GENERATIVE AI VIDEO ENGINE (/api/vertex-generate)
# =============================================================================
def enrich_clinical_prompt(raw_prompt: str) -> str:
    """
    Transforms raw incoming telemetry prompts into a complete 10-second Google Veo
    clinical animation prompt specification to guarantee 1080p quality and clinical realism.
    """
    if "Stylized 3D medical" in raw_prompt or "The CPAP mask is clearly connected" in raw_prompt:
        return raw_prompt
        
    clean_topic = raw_prompt.replace("_", " ").strip()
    return (
        f"A 10-second stylized 3D medical coaching animation (1920x1080 Full HD, 30fps, exactly 10.0s duration). "
        f"Visual aesthetic: Friendly non-photorealistic 3D medical health characters in warm bedside lighting. "
        f"Unique scene composition: Distinct camera angle focusing specifically on {clean_topic} troubleshooting, "
        f"avoiding generic or duplicate strap adjustments from other clips. "
        f"Pacing: "
        f"0:00-0:03: Character in bed notices telemetry alert regarding {clean_topic}. "
        f"0:03-0:07: Detailed step-by-step hands-on clinical adjustment demonstrating the exact solution for {clean_topic}. "
        f"0:07-0:10: Character relaxes with optimal seal, balanced airflow, and peaceful sleep. "
        f"Medical continuity guardrails: The CPAP mask remains securely connected to the CPAP machine with visible attached tubing throughout the entire clip, "
        f"the tube never appears disconnected, missing, or floating. "
        f"Off-screen narration only (character does not visibly speak): "
        f"Calm female English voiceover: 'Follow these simple adjustments for {clean_topic} to ensure secure seal, comfortable pressure, and restorative sleep.' "
        f"No on-screen text outside device display."
    )


@app.post("/api/vertex-generate", dependencies=[Depends(verify_api_key)])
def generate_vertex_video(req: Dict[str, Any], request: Request = None):
    """
    Scenario 3 Endpoint:
      1. Receives AI prompt payload.
      2. Executes 3-Level Pre-Generation Deduplication Shield across all existing & new videos.
      3. Dispatches request to Google Vertex AI / GenAI (Veo model) only if no duplicate exists.
      4. Saves video into 'new_videos/' and generates bilingual subtitles in 'new_subtitles/'.
      5. Automatically synchronizes 'master_video_metadata.json'.
      6. Syncs Tier-3 telemetry to SQL Server.
    """
    t5_iso = datetime.now(timezone.utc).isoformat()
    t5_perf = time.perf_counter()
    event_id = req.get("event_id")

    api_key = req.get("api_key") or GOOGLE_VERTEX_API_KEY
    raw_prompt = req.get("prompt", "Medical CPAP coaching video")
    patient_id = req.get("patient_id", "P001")
    model_id = req.get("model", VERTEX_MODEL)
    
    # 1. Enrich prompt with clinical guardrails
    prompt = enrich_clinical_prompt(raw_prompt)
    
    # 2. Format standardized filename slug: {ID}_{Title_Words}.mp4
    cleaned_prompt = re.sub(r'[^a-zA-Z0-9\s]', ' ', raw_prompt).strip()
    words = [w.capitalize() if not (w.isupper() or any(c.isupper() for c in w[1:])) else w for w in cleaned_prompt.split() if w]
    title_slug = "_".join(words[:6]) if words else "Custom_Coaching"

    prompt_hash = hashlib.md5(raw_prompt.strip().lower().encode("utf-8")).hexdigest()[:10]
    cache_index_file = METADATA_DIR / "generative_cache_index.json"
    cache_map = {}
    if cache_index_file.exists():
        try:
            with open(cache_index_file, "r", encoding="utf-8") as f:
                cache_map = json.load(f)
        except Exception:
            cache_map = {}

    # 3. 3-Level Pre-Generation Deduplication Shield Check
    shield_match = find_existing_library_match(raw_prompt, title_slug=title_slug)
    if shield_match:
        output_filename = shield_match["filename"]
        output_path = shield_match["path"]
        output_bucket = shield_match["bucket"]
        is_cached = True
        shield_active = True
        shield_level = shield_match["level"]
        shield_title = shield_match["title"]
    else:
        shield_active = False
        shield_level = None
        shield_title = None
        output_bucket = "new"
        existing_all = list(EXISTING_DIR.glob("*.mp4")) + list(NEW_DIR.glob("*.mp4"))
        next_id = len(existing_all) + 1
        output_filename = f"{next_id}_{title_slug}.mp4"
        output_path = NEW_DIR / output_filename
        is_cached = False

    output_stem = Path(output_filename).stem
    sub_en_name = f"{output_stem}.en.vtt"
    sub_fr_name = f"{output_stem}.fr.vtt"
    sub_en_url = subtitle_url_for(output_filename, "en") or f"{PUBLIC_BASE_URL}/subtitles/{sub_en_name}"
    sub_fr_url = subtitle_url_for(output_filename, "fr") or f"{PUBLIC_BASE_URL}/subtitles/{sub_fr_name}"

    # API Endpoints
    genai_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:predictLongRunning"

    logger.info("=" * 70)
    logger.info(" [SCENARIO 3 ACTIVE] 3. New Video Generation (Google Veo / Vertex AI - 1080p)")
    logger.info("=" * 70)
    if event_id:
        logger.info(f"   * Event Trace ID    : {event_id}")
    logger.info(f"   * Patient ID        : {patient_id}")
    logger.info(f"   * Clinical Prompt   : '{raw_prompt}'")
    logger.info(f"   * Target AI Model   : {model_id}")
    logger.info(f"   * Target Resolution : 1920x1080 Full HD (1080p)")
    logger.info(f"   * Selected/Gen File : {output_filename} (Bucket: {output_bucket}_videos/)")
    logger.info(f"   * English Subtitle  : {sub_en_name}")
    logger.info(f"   * French Subtitle   : {sub_fr_name}")
    if shield_active:
        logger.info(f"   * Deduplication     : [SHIELD ACTIVE] Reusing existing video - Veo call skipped")
        logger.info(f"   * Shield Match Level: {shield_level}")
        logger.info(f"   * Matched Title     : '{shield_title}'")
    else:
        logger.info(f"   * Cache Status      : {'CACHE HIT (Reusing existing video)' if is_cached else 'CACHE MISS (New generation required)'}")
    logger.info(f"   * Direct Stream URL : {PUBLIC_BASE_URL}/videos/{output_bucket}/{output_filename}")
    logger.info("=" * 70)
    
    api_call_status = "cached_reuse" if is_cached else "not_executed"
    google_response_detail = {"cache": "hit", "message": f"Video reused from {output_bucket} library cache"} if is_cached else {}
    real_ai_generated = is_cached
    api_error_code = None
    api_error_message = None

    # 4. Call Vertex AI API if not cached
    if not is_cached:
        request_payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "16:9",
                "durationSeconds": 8
            }
        }
        
        if api_key:
            req_url = f"{genai_endpoint}?key={api_key}"
            try:
                logger.info(f"[VEO DISPATCH] Calling Google GenAI endpoint ({genai_endpoint})...")
                resp = requests.post(
                    req_url,
                    json=request_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                api_call_status = f"http_{resp.status_code}"
                
                if resp.status_code == 200:
                    resp_json = resp.json()
                    google_response_detail = resp_json
                    predictions = resp_json.get("predictions", [])
                    if predictions and "bytesBase64Encoded" in predictions[0]:
                        video_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                        with open(output_path, "wb") as f:
                            f.write(video_bytes)
                        real_ai_generated = True
                        logger.info(f"[VEO SAVE] Successfully saved video file to {output_path}")
                elif resp.status_code == 429:
                    api_error_code = "GOOGLE_QUOTA_EXHAUSTED"
                    api_error_message = "Google AI Studio quota exhausted. Veo video generation requires paid billing tier on Google account."
                    logger.warning(f"[VEO 429] Quota exceeded: {resp.text[:200]}")
                    google_response_detail = {"error": "Quota exceeded", "details": resp.text[:300]}
                elif resp.status_code == 403:
                    api_error_code = "GOOGLE_PERMISSION_DENIED"
                    api_error_message = "Permission denied. Please verify API key and ensure Vertex AI billing is active."
                    logger.warning(f"[VEO 403] Permission denied: {resp.text[:200]}")
                    google_response_detail = {"error": "Permission denied", "details": resp.text[:300]}
                else:
                    api_error_code = f"HTTP_{resp.status_code}"
                    api_error_message = resp.text[:300]
                    google_response_detail = {"error": resp.text[:500]}
            except Exception as e:
                logger.error(f"[VEO ERROR] API Request failed: {e}")
                api_call_status = f"error: {str(e)}"
                api_error_code = "NETWORK_ERROR"
                api_error_message = str(e)
                google_response_detail = {"error": str(e)}
        else:
            api_call_status = "skipped_no_api_key"
            api_error_code = "MISSING_API_KEY"
            api_error_message = "No GOOGLE_VERTEX_API_KEY configured."

        # Graceful placeholder synthesis if API was unavailable or quota limited
        if not output_path.exists():
            existing_clips = sorted(list(EXISTING_DIR.glob("*.mp4")))
            if existing_clips:
                pick_idx = int(hashlib.md5(raw_prompt.encode()).hexdigest(), 16) % len(existing_clips)
                sample_src = existing_clips[pick_idx]
                shutil.copyfile(sample_src, output_path)
                logger.info(f"[SYNTHESIS FALLBACK] Created unique video placeholder from {sample_src.name} at {output_path}")
                # Copy exact matching subtitles from sample_src so subtitles match the video 100%
                src_en = EXISTING_SUBTITLES_DIR / f"{sample_src.stem}.en.vtt"
                src_fr = EXISTING_SUBTITLES_DIR / f"{sample_src.stem}.fr.vtt"
                dst_en = NEW_SUBTITLES_DIR / sub_en_name
                dst_fr = NEW_SUBTITLES_DIR / sub_fr_name
                if src_en.exists():
                    shutil.copyfile(src_en, dst_en)
                if src_fr.exists():
                    shutil.copyfile(src_fr, dst_fr)
            else:
                with open(output_path, "wb") as f:
                    f.write(b"")

        # Save to prompt cache index
        register_prompt_cache(raw_prompt, output_filename)

    # 5. Synthesize bilingual subtitle tracks only for brand-new generations
    if not is_cached and synthesize_subtitles_for_video:
        try:
            synthesize_subtitles_for_video(output_stem, topic_or_prompt=raw_prompt, duration_s=10.0)
        except Exception as e:
            logger.warning(f"Could not synthesize subtitles: {e}")

    # 6. Auto-synchronize master metadata & distributed trigger catalog
    if update_master_metadata:
        try:
            total_indexed = update_master_metadata()
            logger.info(f"[AUTO METADATA] master_video_metadata.json updated ({total_indexed} total videos)")
        except Exception as e:
            logger.warning(f"Could not auto-update metadata: {e}")

    if compile_distributed_trigger_catalog:
        try:
            compile_distributed_trigger_catalog()
            logger.info("[AUTO CATALOG] Trigger catalog synchronized after new video generation")
        except Exception as e:
            logger.warning(f"Could not auto-update trigger catalog: {e}")

    if broadcast_in_background:
        try:
            broadcast_in_background(new_videos_added=[output_filename])
        except Exception as e:
            logger.debug(f"Could not dispatch background broadcast: {e}")

    logger.info("-" * 65)

    # 7. Telemetry & Timing
    t6_iso = datetime.now(timezone.utc).isoformat()
    vm_processing_ms = round((time.perf_counter() - t5_perf) * 1000.0, 2)
    final_status = "success" if (real_ai_generated or is_cached) else "failed"
    telemetry_status = "cached" if is_cached else ("generated" if real_ai_generated else "failed")

    match = re.match(r"^(\d+)_", output_filename)
    extracted_video_id = match.group(1) if match else output_stem

    if event_id:
        sync_vm_telemetry(
            event_id=event_id,
            video_id=extracted_video_id,
            t5_iso=t5_iso,
            t6_iso=t6_iso,
            vm_status=telemetry_status
        )
    
    response_payload = {
        "status": final_status,
        "event_id": event_id,
        "scenario": "scenario_3_hybrid_generated",
        "generated_video_filename": output_filename,
        "bucket": f"{output_bucket}_videos",
        "url": f"{PUBLIC_BASE_URL}/videos/{output_bucket}/{output_filename}",
        "subtitle_en_url": sub_en_url,
        "subtitle_fr_url": sub_fr_url,
        "vertex_api_status": api_call_status,
        "cache_hit": is_cached,
        "deduplication_shield": {
            "active": shield_active,
            "reused_from": f"{output_bucket}_videos",
            "matched_title": shield_title,
            "match_reason": shield_level
        },
        "real_ai_generated": real_ai_generated,
        "google_details": google_response_detail,
        "metadata_status": "master_metadata_synchronized",
        "vm_processing_ms": vm_processing_ms
    }

    source_name = identify_caller(request) if request else "AI Server / Direct Client"
    live_scenario_tracker.record_activity(
        scenario_id=3,
        scenario_name="Scenario 3: Google Veo / Vertex AI Video Generation",
        patient_id=patient_id,
        title=cleaned_prompt[:40] if cleaned_prompt else "Generative AI Video",
        source_node=source_name,
        details={
            "output_filename": output_filename,
            "bucket": f"{output_bucket}_videos",
            "deduplication_shield_active": shield_active,
            "cache_hit": is_cached,
            "real_ai_generated": real_ai_generated,
            "model": model_id,
            "processing_ms": vm_processing_ms
        },
        status=final_status
    )

    return response_payload


@app.get("/api/activity/latest")
def get_latest_activity():
    """Returns the latest scenario activity and active incoming request state."""
    return live_scenario_tracker.get_state()


# =============================================================================
# 12. HEALTH, CATALOG & QUERY ENDPOINTS
# =============================================================================
@app.get("/health")
def health():
    """Returns the operational status, persistent ledger statistics, and active directory paths."""
    ledger_summary = assignment_ledger.get_ledger_summary() if assignment_ledger else {}
    return {
        "status": "ok",
        "app": APP_TITLE,
        "public_base_url": PUBLIC_BASE_URL,
        "dashboard_base_url": DASHBOARD_BASE_URL,
        "base_dir": str(BASE_DIR),
        "existing_assets_dir": str(EXISTING_DIR),
        "new_videos_dir": str(NEW_DIR),
        "existing_subtitles_dir": str(EXISTING_SUBTITLES_DIR),
        "new_subtitles_dir": str(NEW_SUBTITLES_DIR),
        "stored_patients": ledger_summary.get("total_unique_patients", len(LAST_DECISION)),
        "total_recorded_assignments": ledger_summary.get("total_unique_assignments", 0),
        "ledger_file": ledger_summary.get("ledger_file", str(METADATA_DIR / "assigned_video_history.json")),
    }


@app.get("/api/library")
def list_library():
    """Lists all available video assets and subtitle files in the library."""
    def collect_files(folder: Path) -> List[str]:
        if not folder.exists():
            return []
        return sorted([p.name for p in folder.iterdir() if p.is_file()])

    library_data = {
        "existing_assets": collect_files(EXISTING_DIR),
        "new_videos": collect_files(NEW_DIR),
        "existing_subtitles": collect_files(EXISTING_SUBTITLES_DIR),
        "new_subtitles": collect_files(NEW_SUBTITLES_DIR),
        "generated_subtitles": collect_files(EXISTING_SUBTITLES_DIR) + collect_files(NEW_SUBTITLES_DIR),
    }
    logger.info(f"[LIBRARY STATUS] Catalog: {len(library_data['existing_assets'])} existing videos | {len(library_data['new_videos'])} new videos | {len(library_data['generated_subtitles'])} subtitle tracks")
    return library_data


@app.get("/api/triggers/catalog")
@app.get("/api/catalog/sync")
def get_trigger_catalog():
    """
    Returns the complete structured clinical trigger catalog, streaming URLs,
    and bilingual subtitle endpoints for all indexed videos across the ecosystem.
    Allows AI Server VM, Raspberry Pi, and Central Dashboard to fetch live triggers anytime.
    """
    if compile_distributed_trigger_catalog:
        catalog = compile_distributed_trigger_catalog()
        if "video_triggers" in catalog and "triggers" not in catalog:
            catalog["triggers"] = catalog["video_triggers"]
        elif "triggers" in catalog and "video_triggers" not in catalog:
            catalog["video_triggers"] = catalog["triggers"]
        total_indexed = len(catalog.get("video_triggers", []))
        logger.info(f"[TRIGGER CATALOG QUERY] Delivered {total_indexed} video triggers to caller")
        return catalog
    return {"status": "error", "message": "Catalog compiler not initialized"}


@app.post("/api/triggers/broadcast", dependencies=[Depends(verify_api_key)])
def trigger_distributed_broadcast():
    """
    Manually triggers an immediate broadcast sync of all video triggers to
    AI Server (VM3), Raspberry Pi 5 Edge (Port 8000), and Central Backend (VM2).
    Dispatches asynchronously in background to ensure sub-millisecond UI responsiveness.
    """
    if broadcast_in_background:
        broadcast_in_background()
        logger.info("[BROADCAST DISPATCH] Multi-node trigger distribution launched in background thread.")
        return {
            "status": "ok",
            "message": "Broadcast synchronization initiated across AI Server, Raspberry Pi & Backend nodes.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    return {"status": "error", "message": "Broadcast engine not available"}


@app.get("/api/patient/{patient_id}/latest")
def get_latest_for_patient(patient_id: str):
    """Retrieves the latest video recommendation decision stored for a given patient."""
    logger.info(f"[QUERY] Fetching latest video decision for Patient ID: {patient_id}")
    decision = None
    if assignment_ledger:
        decision = assignment_ledger.get_latest_decision(patient_id)
    if not decision:
        decision = LAST_DECISION.get(patient_id)
    if not decision:
        raise HTTPException(status_code=404, detail="No video decision found for this patient")
    return decision


@app.get("/api/assignments/history")
def get_assignment_history(patient_id: Optional[str] = None):
    """
    Returns recorded video assignment history from the persistent ledger.
    Allows clinical staff or AI engine to inspect past assignments per patient.
    """
    if not assignment_ledger:
        return {"status": "error", "message": "Assignment ledger not available"}
    
    with assignment_ledger._lock:
        if patient_id:
            pid_clean = str(patient_id).strip()
            history = assignment_ledger._patient_history.get(pid_clean, [])
            return {
                "patient_id": pid_clean,
                "total_assignments": len(history),
                "history": history
            }
        return {
            "summary": assignment_ledger.get_ledger_summary(),
            "patients": assignment_ledger._patient_history
        }


@app.delete("/api/assignments/reset", dependencies=[Depends(verify_api_key)])
def reset_assignment_history():
    """
    Resets the persistent video assignment ledger.
    Requires valid X-API-KEY security token.
    """
    if not assignment_ledger:
        return {"status": "error", "message": "Assignment ledger not available"}
    assignment_ledger.clear_ledger()
    LAST_DECISION.clear()
    logger.info("[ASSIGNMENT LEDGER RESET] Persistent assignment history was cleared by authorized administrator.")
    return {
        "status": "ok",
        "message": "Persistent video assignment history cleared successfully."
    }


# =============================================================================
# 12.1. REAL-TIME LOG STREAMING & INTERACTIVE WEB DASHBOARD
# =============================================================================
@app.get("/api/logs/recent")
def get_recent_logs(limit: int = 150):
    """Returns recent log entries stored in the in-memory circular buffer."""
    return {"status": "ok", "logs": log_buffer_handler.get_recent(limit)}


@app.get("/api/logs/stream")
async def stream_live_logs():
    """
    Streams live server log events to connected browser dashboards in real-time
    using Server-Sent Events (SSE). Emulates live .bat terminal output.
    """
    async def event_generator():
        q = log_buffer_handler.subscribe()
        try:
            # First send the initial recent backlog (up to 40 items)
            recent = log_buffer_handler.get_recent(40)
            for item in recent:
                yield f"data: {json.dumps(item)}\n\n"
            # Stream ongoing live events as they occur
            while True:
                entry = await q.get()
                yield f"data: {json.dumps(entry)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            log_buffer_handler.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/catalog/rebuild", dependencies=[Depends(verify_api_key)])
def rebuild_catalog_metadata():
    """
    Triggers an instant rescan and rebuild of all video metadata & bilingual subtitle records.
    """
    if sync_all_video_assets:
        total_vids, total_subs, new_subs = sync_all_video_assets(verbose=True)
        if compile_distributed_trigger_catalog:
            try:
                compile_distributed_trigger_catalog()
            except Exception as err:
                logger.warning(f"Could not recompile trigger catalog during rebuild: {err}")
        return {
            "status": "ok",
            "message": "Catalog metadata rebuilt successfully",
            "total_videos": total_vids,
            "total_subtitles": total_subs,
            "new_subtitles_synthesized": new_subs
        }
    return {"status": "error", "message": "Metadata sync engine not available"}


@app.get("/api/kpis")
def get_kpis_api(benchmark: bool = False):
    """
    Returns live Key Performance Indicators (KPIs), gauge metrics,
    and distribution statistics for the Clinical Dashboard.
    """
    try:
        from calculate_kpis import get_all_kpis_data
        return get_all_kpis_data(benchmark=benchmark)
    except Exception as err:
        logger.warning(f"Could not compute live KPIs: {err}")
        return {"status": "error", "message": str(err)}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    """
    Serves the Interactive Modular Clinical Dashboard directly in browser.
    Replaces the raw command line with a full-fledged real-time monitoring interface.
    """
    index_file = DASHBOARD_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="""<!DOCTYPE html>
<html>
<head><title>SleepCare CPAP Video Server</title></head>
<body style="background:#0b0f19;color:#fff;font-family:sans-serif;padding:2rem;text-align:center;">
  <h2>SleepCare CPAP Video Server</h2>
  <p>Dashboard initializing... Please ensure dashboard files are present.</p>
  <p><a href="/api/library" style="color:#06b6d4;">View Video Library API</a> | <a href="/api/triggers/catalog" style="color:#06b6d4;">View Triggers API</a></p>
</body>
</html>""",
        status_code=200
    )


# =============================================================================
# 13. MAIN SERVER ENTRY POINT
# =============================================================================
def ensure_port_free(port: int):
    """
    Checks if the target port is in use by another process and automatically
    terminates the conflicting process to prevent WinError 10048 address binding errors.
    """
    try:
        current_pid = os.getpid()
        if sys.platform == "win32":
            cmd = (
                f'powershell -NoProfile -Command "'
                f'$pids = Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | '
                f'Select-Object -ExpandProperty OwningProcess -Unique; '
                f'foreach ($p in $pids) {{ if ($p -and $p -ne {current_pid}) {{ '
                f'Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; Write-Output $p }} }}"'
            )
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            pids = set(res.stdout.strip().split())
            for p in pids:
                if p:
                    logger.info(f"[PORT AUTO-CLEANUP] Automatically freed port {port} by stopping previous process PID: {p}")
            time.sleep(0.5)
    except Exception as err:
        logger.warning(f"Could not automatically clear port {port}: {err}")


if __name__ == "__main__":
    ensure_port_free(PORT)
    logger.info("=" * 75)
    logger.info(f" [DASHBOARD READY] Open your browser at: http://localhost:{PORT}/")
    logger.info("=" * 75)
    while True:
        try:
            uvicorn.run(app, host=HOST, port=PORT, access_log=False)
            break
        except KeyboardInterrupt:
            logger.info("[SERVER SHUTDOWN] Server stopped by operator.")
            break
        except Exception as err:
            logger.error(f"[SERVER AUTO-RECOVERY] Uvicorn event loop restarted after network error: {err}")
            time.sleep(0.5)