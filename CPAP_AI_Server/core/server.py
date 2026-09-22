"""
SleepCare AI Server - FastAPI Application & Live REST Endpoints
===============================================================
This module serves the 24/7 web API on Port 8000:
- Pipeline execution & database synchronization webhooks.
- ML model health, drift monitoring, and asynchronous retraining.
- Clinical video orchestration for Scenarios 1, 2, and 3.
- Real-time patient prediction queries and virtual stitched video playlists.
- Cohort telemetry metrics and 30+ KPI reporting endpoints.
"""

import os
import time
import json
import logging
import threading
import requests
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, List
from collections import deque
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Request, Security, Query, Header
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse, Response

from core.config import (
    SERVER_HOST,
    SERVER_PORT,
    WEBHOOK_PORT,
    VIDEO_SERVER_URL,
    VIDEO_SERVER_API_KEY,
    AI_SERVER_API_KEY,
    HEADERS
)
from core.registry import (
    pipeline_state,
    MODEL_HEALTH,
    ML_MODELS_REGISTRY,
    CLINICAL_VIDEO_REGISTRY,
    get_pipeline_state_copy,
    get_model_health_copy,
    get_dynamic_catalog_state,
    update_catalog_from_payload,
    sync_video_catalog_from_vm
)
from core.interceptor import (
    find_artifact_file,
    load_cached_csv,
    _original_read_csv
)
from core.video_engine import (
    resolve_clinical_video_for_patient,
    resolve_clinical_video_playlist_for_patient,
    orchestrate_video_recommendation,
    orchestrate_video_package,
    trigger_vertex_video_generation,
    orchestrate_pipeline_videos,
    VideoOrchestrationClient,
    get_assignment_tracker
)
from core.pipeline import (
    execute_supervisor_pipeline,
    push_predictions_to_backend,
    background_scheduler_loop
)
from core.dashboard_view import get_dashboard_html

logger = logging.getLogger("CPAP_AI_Server")


# ==============================================================================
# In-Memory Ring Buffer Logging Handler (Feeds Real-Time Dashboard Terminal)
# ==============================================================================
class LogRingBuffer(logging.Handler):
    """
    Thread-safe in-memory ring buffer holding recent log entries for real-time
    streaming and dashboard terminal monitoring.
    """
    def __init__(self, maxlen: int = 1000):
        super().__init__()
        self.buffer = deque(maxlen=maxlen)
        self._buf_lock = threading.RLock()
        self.counter = 0

    def emit(self, record):
        try:
            msg = self.format(record)
            with self._buf_lock:
                self.counter += 1
                self.buffer.append({
                    "id": self.counter,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": msg
                })
        except Exception:
            self.handleError(record)

    def get_logs(self, since_id: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        with self._buf_lock:
            if since_id <= 0:
                return list(self.buffer)[-limit:]
            return [log for log in self.buffer if log["id"] > since_id][-limit:]

    def clear(self):
        with self._buf_lock:
            self.buffer.clear()


log_ring_buffer = LogRingBuffer(maxlen=1000)
log_ring_buffer.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log_ring_buffer.setFormatter(formatter)

logger.setLevel(logging.INFO)
logger.addHandler(log_ring_buffer)

for name in ["ai_server.registry", "ai_server.pipeline", "uvicorn", "uvicorn.access"]:
    sub_l = logging.getLogger(name)
    sub_l.setLevel(logging.INFO)
    sub_l.addHandler(log_ring_buffer)


# ==============================================================================
# 1. Pydantic Request Models
# ==============================================================================
class PipelinePushRequest(BaseModel):
    layer: Optional[str] = Field(default="all", description="Target layer name or 'all'")
    athome_patient_id: Optional[int] = Field(default=None, description="Optional specific patient ID")


class VertexGenerateRequest(BaseModel):
    patient_id: str = Field(..., description="Patient Identifier")
    prompt: str = Field(..., description="Clinical prompt describing scenario")
    model: str = Field(default="veo-3.1-generate-preview", description="Generative model name")


# Startup state flags to prevent duplicate or recursive thread execution across workers
_scheduler_started = False
_companion_listener_started = False
_startup_lock = threading.Lock()


# ==============================================================================
# 2. FastAPI Lifespan & Background Worker Thread
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts the 30-minute background supervisor pipeline scheduler, port 8001 webhook listener, and dynamic catalog sync on server boot."""
    global _scheduler_started, _companion_listener_started

    logger.info(f"[AI SERVER] Starting continuous service on http://{SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"[AI SERVER] Interactive API documentation available at: http://159.84.143.246:{SERVER_PORT}/docs")
    logger.info(f"[AI SERVER] Interactive Web Dashboard available at: http://localhost:{SERVER_PORT}/dashboard")
    logger.info(f"[AI SERVER] Video VM Orchestration Target: {VIDEO_SERVER_URL}")

    with _startup_lock:
        # Launch background scheduler in a daemon thread so it runs independently and terminates on server exit
        if not _scheduler_started:
            _scheduler_started = True
            scheduler_thread = threading.Thread(target=background_scheduler_loop, daemon=True, name="pipeline_scheduler")
            scheduler_thread.start()

        # Launch companion webhook listener on port 8001 if different from SERVER_PORT
        if WEBHOOK_PORT != SERVER_PORT and not _companion_listener_started:
            _companion_listener_started = True

            def _run_companion_listener():
                try:
                    import uvicorn
                    logger.info(f"[WEBHOOK LISTENER] Starting active trigger sync listener on http://{SERVER_HOST}:{WEBHOOK_PORT}")
                    u_cfg = uvicorn.Config(
                        app=app,
                        host=SERVER_HOST,
                        port=WEBHOOK_PORT,
                        lifespan="off",
                        log_level="warning",
                        access_log=False
                    )
                    u_srv = uvicorn.Server(u_cfg)
                    u_srv.install_signal_handlers = lambda: None
                    u_srv.run()
                except Exception as exc:
                    logger.warning(f"[WEBHOOK LISTENER WARNING] Could not bind companion listener on port {WEBHOOK_PORT}: {exc}")

            webhook_thread = threading.Thread(target=_run_companion_listener, daemon=True, name="webhook_listener_8001")
            webhook_thread.start()
            logger.info(f"[WEBHOOK LISTENER ACTIVE] Listening for VM4 trigger catalog sync on http://{SERVER_HOST}:{WEBHOOK_PORT}/api/triggers/sync")

    yield


app = FastAPI(
    title="SleepCare CPAP AI Supervisor Server",
    description="Continuous 24/7 AI scoring, multimodal biomarker fusion, and real-time intervention engine for CPAP therapy.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for dashboard web applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# 3. Security Dependencies & Traffic Logging Middleware
# ==============================================================================
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
ml_key_header = APIKeyHeader(name="X-ML-Key", auto_error=False)


async def verify_ai_server_auth(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    ml_key: Optional[str] = Security(ml_key_header)
):
    """
    Protects clinical endpoints.
    Allows loopback / local queries (127.0.0.1, localhost) or validates against
    configured server keys (X-API-KEY or X-ML-Key).
    """
    client_ip = request.client.host if request.client else "unknown"
    if client_ip in ["127.0.0.1", "localhost", "::1", "testclient"]:
        return True

    token = api_key or ml_key
    if not token or (token != AI_SERVER_API_KEY and token != HEADERS.get("X-ML-Key")):
        logger.warning(f"[AUTH REJECTED] Client {client_ip} unauthorized access attempt on {request.url.path}")
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid or missing X-API-KEY or X-ML-Key header."
        )
    return True


@app.middleware("http")
async def traffic_and_security_logger(request: Request, call_next):
    """
    Inspects inbound HTTP traffic:
    1. Blocks malicious scanner probes (e.g. .env, .git, php).
    2. Logs structured clinical context for incoming requests.
    3. Adds standard defense-in-depth security response headers.
    """
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    client_port = request.client.port if request.client else "0"
    raw_path = request.url.path
    lower_path = raw_path.lower()
    method = request.method

    # 1. Block unauthorized probes
    blocked_patterns = [
        "/.env", "/.git", "/.aws", "/.npmrc", "/.ssh",
        "phpinfo", ".php", "actuator", "terraform",
        "appsettings.json", "wp-login", "wp-admin",
        "/etc/passwd", "/config.json"
    ]
    for pattern in blocked_patterns:
        if pattern in lower_path:
            logger.warning(f"[SECURITY BLOCKED] Client {client_ip}:{client_port} attempted unauthorized path: {method} {raw_path}")
            return JSONResponse(status_code=403, content={"detail": "Access Denied: Malicious probe detected."})

    # 2. Contextual logging
    if raw_path.startswith("/api/patient/"):
        patient_id = raw_path.split("/")[-1]
        logger.info(f"[PATIENT QUERY] Patient {patient_id} AI evaluation request from {client_ip}")
    elif raw_path == "/api/patients":
        logger.info(f"[COHORT QUERY] Patient cohort listing query from {client_ip}")
    elif raw_path == "/api/metrics":
        logger.info(f"[METRICS QUERY] Cohort telemetry & risk metrics query from {client_ip}")
    elif raw_path == "/api/pipeline/run":
        logger.info(f"[PIPELINE TRIGGER INBOUND] AI model supervisor pipeline execution requested by {client_ip}")
    elif raw_path == "/api/pipeline/push":
        logger.info(f"[PUSH TRIGGER INBOUND] Database prediction sync requested by {client_ip}")
    elif raw_path == "/api/pipeline/orchestrate-videos":
        logger.info(f"[VIDEO BATCH DISPATCH] Batch clinical video orchestration triggered by {client_ip}")
    elif raw_path.startswith("/api/video-server/orchestrate/"):
        patient_id = raw_path.split("/")[-1]
        logger.info(f"[VIDEO DIRECT DISPATCH] Video recommendation dispatch for Patient {patient_id} from {client_ip}")
    elif raw_path == "/api/video-server/vertex-generate":
        logger.info(f"[VERTEX DISPATCH] Scenario 3 AI video generation trigger from {client_ip}")
    elif raw_path == "/api/video-server/health":
        logger.info(f"[VIDEO SERVER PING] Video VM Server health status check from {client_ip}")
    elif raw_path == "/health":
        logger.info(f"[HEALTH CHECK] Health ping from {client_ip}")
    else:
        logger.info(f"[HTTP REQUEST] {client_ip}:{client_port} -> {method} {raw_path}")

    # Process Request
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    # Attach standard security response headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    status_label = "[HTTP OK]" if response.status_code < 400 else "[HTTP WARN/ERR]"
    logger.info(f"{status_label} {method} {raw_path} -> Status {response.status_code} ({duration_ms:.2f}ms)")
    return response


# ==============================================================================
# 4. System Health & Status Endpoints
# ==============================================================================
@app.get("/")
def root(request: Request):
    """Returns interactive dashboard for web browsers or JSON status for API clients."""
    accept_header = request.headers.get("accept", "").lower()
    if "text/html" in accept_header and "application/json" not in accept_header:
        return HTMLResponse(content=get_dashboard_html(), status_code=200)

    return {
        "name": "SleepCare CPAP AI Server",
        "status": "online",
        "host": SERVER_HOST,
        "port": SERVER_PORT,
        "video_server_url": VIDEO_SERVER_URL,
        "pipeline": get_pipeline_state_copy(),
        "model_health": get_model_health_copy(),
        "dashboard": "/dashboard",
        "docs": "/docs"
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_view():
    """Serves the rich interactive modular HTML control center."""
    return HTMLResponse(content=get_dashboard_html(), status_code=200)


@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    """Aggregates all live server telemetry, tracker state, and video catalogs for the dashboard."""
    tracker = get_assignment_tracker()
    return {
        "config": {
            "name": "SleepCare CPAP AI Server",
            "host": SERVER_HOST,
            "port": SERVER_PORT,
            "webhook_port": WEBHOOK_PORT,
            "webhook_active": True,
            "sync_interval_mins": 30,
            "video_vm_url": VIDEO_SERVER_URL,
            "backend_url": "http://159.84.143.151/api/data",
            "timeout_seconds": 900
        },
        "pipeline": get_pipeline_state_copy(),
        "tracker": tracker.get_summary(),
        "model_health": get_model_health_copy(),
        "catalog": {
            "total_curated_videos": get_dynamic_catalog_state().get("summary", {}).get("total_curated_videos", 37),
            "total_library_videos": get_dynamic_catalog_state().get("summary", {}).get("total_library_videos", len(CLINICAL_VIDEO_REGISTRY)),
            "total_subtitles": len(CLINICAL_VIDEO_REGISTRY) * 2,
            "experimental_clips": 0,
            "last_sync": get_dynamic_catalog_state().get("last_synced")
        },
        "kpis": load_kpis_summary()
    }


def load_kpis_summary() -> Dict[str, Any]:
    """Loads precomputed clinical and operational KPIs from reports/cpap_kpis_summary.json."""
    kpi_paths = [
        os.path.join(os.getcwd(), "reports", "cpap_kpis_summary.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "cpap_kpis_summary.json")
    ]
    for p in kpi_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading KPI report from {p}: {e}")
    return {}


@app.get("/api/dashboard/kpis")
def get_dashboard_kpis():
    """Returns clinical, adherence, risk and alarm KPI metrics computed across the cohort."""
    return load_kpis_summary()


@app.get("/api/server/logs")
def get_server_logs(since_id: int = Query(0, description="Log ID cursor"), limit: int = Query(100, description="Max logs")):
    """Returns recent log messages from the in-memory ring buffer for live streaming."""
    s_id = int(getattr(since_id, "default", since_id) if hasattr(since_id, "default") else since_id)
    lim = int(getattr(limit, "default", limit) if hasattr(limit, "default") else limit)
    return log_ring_buffer.get_logs(since_id=s_id, limit=lim)


@app.get("/health")
def health_check():
    """Standard health endpoint for load balancers and system supervisors."""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video_server_url": VIDEO_SERVER_URL,
        "model_health": get_model_health_copy(),
        "pipeline_state": get_pipeline_state_copy()
    }


# ==============================================================================
# 5. Pipeline Execution & Synchronization Webhooks
# ==============================================================================
@app.post("/api/pipeline/run", dependencies=[Depends(verify_ai_server_auth)])
@app.post("/api/pipeline/run-now", dependencies=[Depends(verify_ai_server_auth)])
def trigger_pipeline(background_tasks: BackgroundTasks):
    """Webhook to trigger immediate AI model execution in the background (Protected)."""
    current_state = get_pipeline_state_copy()
    if current_state["status"] == "running":
        return {"message": "Pipeline is already running.", "state": current_state}
    background_tasks.add_task(execute_supervisor_pipeline)
    return {"message": "AI Pipeline run initiated.", "status": "running"}


@app.post("/api/pipeline/push", dependencies=[Depends(verify_ai_server_auth)])
def trigger_push():
    """Pushes existing generated predictions directly to backend REST storage (Protected)."""
    return push_predictions_to_backend()


@app.post("/api/pipeline/orchestrate-videos", dependencies=[Depends(verify_ai_server_auth)])
def trigger_video_orchestration(force: bool = Query(False, description="Bypass duplicate assignment check and force re-dispatch")):
    """Manually dispatches video recommendations for all eligible patients to Video VM Server (Protected)."""
    return orchestrate_pipeline_videos(force=force)


@app.get("/api/pipeline/status")
def get_pipeline_status():
    """Returns the current execution state and degradation health of the ML pipeline."""
    return {
        "pipeline_state": get_pipeline_state_copy(),
        "model_health": get_model_health_copy()
    }


# ==============================================================================
# 6. ML Model Health & Retraining Endpoints
# ==============================================================================
@app.get("/api/models", dependencies=[Depends(verify_ai_server_auth)])
def list_ml_models():
    """Returns health status, performance metrics, and drift values for all 4 ML models (Protected)."""
    return {
        "status": "success",
        "count": len(ML_MODELS_REGISTRY),
        "models": list(ML_MODELS_REGISTRY.values()),
        "pipeline_state": get_pipeline_state_copy(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/api/models/{model_id}", dependencies=[Depends(verify_ai_server_auth)])
def get_single_ml_model(model_id: str):
    """Returns current health status and metrics for a specific ML model (Protected)."""
    if model_id not in ML_MODELS_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_id}' not found. Available models: {list(ML_MODELS_REGISTRY.keys())}"
        )
    return {
        "status": "success",
        "model": ML_MODELS_REGISTRY[model_id],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@app.post("/api/models/{model_id}/retrain", status_code=202, dependencies=[Depends(verify_ai_server_auth)])
def trigger_model_retrain(model_id: str, background_tasks: BackgroundTasks):
    """
    Triggers an asynchronous retraining job for a specific ML model or all models.
    Returns HTTP 202 Accepted with job_id (Protected).
    """
    valid_models = list(ML_MODELS_REGISTRY.keys()) + ["all"]
    if model_id not in valid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model_id '{model_id}'. Expected one of: {valid_models}"
        )

    job_id = f"job_retrain_{model_id}_{int(time.time())}"
    logger.info(f"[RETRAINING INBOUND] Retraining initiated for model '{model_id}' (Job ID: {job_id})")

    if model_id in ML_MODELS_REGISTRY:
        ML_MODELS_REGISTRY[model_id]["current_status"] = "training"

    background_tasks.add_task(execute_supervisor_pipeline)

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "job_id": job_id,
            "model_id": model_id,
            "message": f"Retraining job queued and executing in background for {model_id}.",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    )


# ==============================================================================
# 7. Video VM Server Interaction Endpoints (Port 8080)
# ==============================================================================
@app.get("/api/video-server/health")
def get_video_server_health():
    """Checks connectivity and health status of the Video VM Server (Port 8080)."""
    import requests
    try:
        res = requests.get(f"{VIDEO_SERVER_URL.rstrip('/')}/health", timeout=5)
        return {
            "configured_url": VIDEO_SERVER_URL,
            "reachable": res.status_code == 200,
            "status_code": res.status_code,
            "server_data": res.json() if res.status_code == 200 else res.text
        }
    except Exception as exc:
        return {
            "configured_url": VIDEO_SERVER_URL,
            "reachable": False,
            "error": str(exc)
        }


# Dynamic Video Catalog & Distributed Trigger Synchronization Endpoints
@app.get("/api/triggers/catalog")
@app.get("/api/catalog/sync")
def get_triggers_catalog_endpoint(refresh: bool = False):
    """
    Option A Catalog Endpoint: Returns the active clinical triggers catalog.
    If refresh=True or if the catalog has not yet been fetched from the Video VM,
    it dynamically syncs with the Video VM (Port 8080).
    """
    state = get_dynamic_catalog_state()
    if refresh or not state.get("video_triggers"):
        sync_res = sync_video_catalog_from_vm()
        state = get_dynamic_catalog_state()
        state["sync_operation"] = sync_res

    return {
        "event": "clinical_video_catalog_update",
        "sync_timestamp": state["last_synced"],
        "source": state["source"],
        "summary": state["summary"],
        "video_triggers": state["video_triggers"]
    }


@app.post("/api/triggers/sync")
@app.post("/api/ai/sync-catalog")
async def receive_trigger_sync_webhook(
    request: Request,
    x_ml_key: Optional[str] = Header(None, alias="X-ML-Key"),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
):
    """
    Option B Webhook Receiver: Inbound webhook receiver that accepts automated video catalog
    updates broadcast by the Video VM whenever new videos or trigger rules are deployed.
    Authenticated via X-ML-Key header or X-API-KEY.
    """
    client_ip = request.client.host if request.client else "unknown"
    valid_keys = {k for k in (HEADERS.get("X-ML-Key"), AI_SERVER_API_KEY, VIDEO_SERVER_API_KEY) if k}
    authorized = (not valid_keys) or (x_ml_key in valid_keys) or (x_api_key in valid_keys)
    if not authorized:
        logger.warning(f"[WEBHOOK AUTH REJECTED] Unauthorized trigger sync attempt from {client_ip}")
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing X-ML-Key / X-API-KEY.")

    try:
        payload = await request.json()
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {err}")

    sync_res = update_catalog_from_payload(payload)
    logger.info(f"[WEBHOOK SUCCESS] Inbound video catalog broadcast processed: {sync_res['updated_count']} triggers updated.")
    return {
        "status": "success",
        "event": "catalog_sync_acknowledged",
        "synced_triggers": sync_res.get("updated_count", 0),
        "sync_result": sync_res
    }


@app.post("/api/video-server/sync-catalog", dependencies=[Depends(verify_ai_server_auth)])
def trigger_manual_catalog_sync():
    """Manually triggers dynamic synchronization with the Video VM Server (Protected)."""
    return sync_video_catalog_from_vm()


@app.post("/api/video-server/orchestrate/{patient_id}", dependencies=[Depends(verify_ai_server_auth)])
def orchestrate_single_patient(
    patient_id: int,
    force: bool = Query(False, description="Bypass duplicate assignment check and force re-dispatch")
):
    """Dispatches an authenticated video coaching recommendation for a specific patient (Protected)."""
    pap_df = load_cached_csv("patient_action_plan.csv")
    if pap_df.empty:
        pap_df = load_cached_csv("layer3_results.csv")

    p_row = {"AtHomePatientId": patient_id, "video_title": "none"}
    if not pap_df.empty and "AtHomePatientId" in pap_df.columns:
        subset = pap_df[pap_df["AtHomePatientId"] == patient_id]
        if not subset.empty:
            p_row = subset.iloc[0].to_dict()

    feat_df = load_cached_csv("features_merged.csv")
    f_row = {}
    if not feat_df.empty and "AtHomePatientId" in feat_df.columns:
        f_sub = feat_df[feat_df["AtHomePatientId"] == patient_id]
        if not f_sub.empty:
            f_row = f_sub.iloc[0].to_dict()

    video_rec = resolve_clinical_video_for_patient(p_row, f_row)
    custom_reason = str(p_row.get("intervention_reason", "")) or video_rec["reason"]
    result = orchestrate_video_recommendation(
        patient_id=str(patient_id),
        video_record=video_rec,
        custom_reason=custom_reason,
        force=force
    )
    return {
        "patient_id": patient_id,
        "resolved_video": video_rec,
        "orchestration_result": result
    }


@app.get("/api/video-server/assigned-tracker", dependencies=[Depends(verify_ai_server_auth)])
def get_assigned_videos_tracker(include_details: bool = Query(False, description="Include detailed per-patient assignment logs")):
    """Returns status and statistics of tracked video assignments to prevent duplicates across restarts."""
    tracker = get_assignment_tracker()
    summary = tracker.get_summary()
    if include_details:
        summary["assignments"] = tracker._raw_assignments
    return summary


@app.post("/api/video-server/assigned-tracker/clear", dependencies=[Depends(verify_ai_server_auth)])
def clear_assigned_videos_tracker():
    """Resets all tracked video assignments, allowing subsequent runs to assign from scratch (Protected)."""
    tracker = get_assignment_tracker()
    return tracker.clear()


@app.post("/api/video-server/vertex-generate", dependencies=[Depends(verify_ai_server_auth)])
def trigger_vertex_generate_endpoint(
    request_body: Optional[VertexGenerateRequest] = None,
    patient_id: Optional[str] = Query(None),
    prompt: Optional[str] = Query(None),
    model: Optional[str] = Query("veo-3.1-generate-preview")
):
    """
    Triggers Scenario 3 Vertex AI video synthesis.
    Supports both Pydantic JSON body and URL query parameters for full backward compatibility (Protected).
    """
    pid = request_body.patient_id if request_body else patient_id
    prm = request_body.prompt if request_body else prompt
    mdl = (request_body.model if request_body else model) or "veo-3.1-generate-preview"

    if not pid or not prm:
        raise HTTPException(status_code=400, detail="Missing required parameters: patient_id and prompt.")

    return trigger_vertex_video_generation(patient_id=pid, prompt=prm, model=mdl)


# ==============================================================================
# 7.1 Video VM Direct Proxy Endpoints (Ensures Reliable Playback & Subtitle Access)
# ==============================================================================
@app.get("/api/proxy/video/{filename}")
def proxy_video_stream(filename: str, request: Request):
    """
    Proxies video streaming from the Video VM (Port 8080) through the AI Server (Port 8000).
    Ensures seamless playback even when the client browser is connecting via localhost, SSH tunnel,
    or internal network without direct access to port 8080.
    Supports HTTP 206 Partial Content and Range headers for video seeking.
    """
    clean_fn = os.path.basename(filename)
    target_url = f"{VIDEO_SERVER_URL}/videos/existing/{clean_fn}"
    headers = {}
    range_header = request.headers.get("range")
    if range_header:
        headers["range"] = range_header

    try:
        req = requests.get(target_url, headers=headers, stream=True, timeout=15)
        response_headers = {
            "Content-Type": req.headers.get("Content-Type", "video/mp4"),
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
        }
        if "Content-Length" in req.headers:
            response_headers["Content-Length"] = req.headers["Content-Length"]
        if "Content-Range" in req.headers:
            response_headers["Content-Range"] = req.headers["Content-Range"]

        return StreamingResponse(
            req.iter_content(chunk_size=128 * 1024),
            status_code=req.status_code,
            headers=response_headers
        )
    except Exception as exc:
        logger.warning(f"[VIDEO PROXY ERROR] Failed to stream video {clean_fn} from {target_url}: {exc}")
        raise HTTPException(status_code=502, detail=f"Failed to stream video from Video VM: {exc}")


@app.get("/api/proxy/subtitle/{filename}")
def proxy_subtitle_stream(filename: str):
    """
    Proxies WebVTT subtitles (.en.vtt, .fr.vtt) from the Video VM through the AI Server.
    Ensures subtitles render properly on HTML5 video tracks without CORS issues.
    """
    clean_fn = os.path.basename(filename)
    target_url = f"{VIDEO_SERVER_URL}/subtitles/{clean_fn}"
    try:
        res = requests.get(target_url, timeout=10)
        if res.status_code == 200:
            return Response(
                content=res.text,
                media_type="text/vtt; charset=utf-8",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600"
                }
            )
        logger.warning(f"[SUBTITLE PROXY] Subtitle {clean_fn} returned status {res.status_code}")
        raise HTTPException(status_code=res.status_code, detail="Subtitle not found on Video VM")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"[SUBTITLE PROXY ERROR] Failed to fetch subtitle {clean_fn}: {exc}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch subtitle: {exc}")


# ==============================================================================
# 8. Patient Prediction & Playlist Endpoints
# ==============================================================================
@app.get("/api/patient/{patient_id}", dependencies=[Depends(verify_ai_server_auth)])
def get_patient_prediction(patient_id: int):
    """Returns comprehensive AI predictions, risk scores, and recommended actions for a specific patient (Protected)."""
    pap_df = load_cached_csv("patient_action_plan.csv")
    if pap_df.empty:
        pap_df = load_cached_csv("layer3_results.csv")
    if pap_df.empty or "AtHomePatientId" not in pap_df.columns:
        raise HTTPException(status_code=404, detail="AI predictions not generated yet. Run pipeline first.")

    patient_row = pap_df[pap_df["AtHomePatientId"] == patient_id]
    if patient_row.empty:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found in prediction database.")

    p_dict = patient_row.iloc[0].replace({np.nan: None}).to_dict()

    feat_df = load_cached_csv("features_merged.csv")
    f_dict = {}
    if not feat_df.empty and "AtHomePatientId" in feat_df.columns:
        f_sub = feat_df[feat_df["AtHomePatientId"] == patient_id]
        if not f_sub.empty:
            f_dict = f_sub.iloc[0].replace({np.nan: None}).to_dict()

    video_rec = resolve_clinical_video_for_patient(p_dict, f_dict)
    playlist_rec = resolve_clinical_video_playlist_for_patient(p_dict, f_dict)

    current_state = get_pipeline_state_copy()
    return {
        "patient_id": patient_id,
        "prediction": p_dict,
        "scenario_1_video": video_rec,
        "scenario_2_playlist": {
            "sequence_count": len(playlist_rec),
            "total_duration_s": sum(item.get("duration_s", 10.0) for item in playlist_rec),
            "items": playlist_rec
        },
        "pipeline_timestamp": current_state["last_run_finish"]
    }


@app.get("/api/patient/{patient_id}/playlist", dependencies=[Depends(verify_ai_server_auth)])
def get_patient_playlist(patient_id: int):
    """Returns Scenario 2 virtual stitched continuous video coaching playlist for frontend playback (Protected)."""
    pap_df = load_cached_csv("patient_action_plan.csv")
    if pap_df.empty:
        pap_df = load_cached_csv("layer3_results.csv")
    if pap_df.empty or "AtHomePatientId" not in pap_df.columns:
        raise HTTPException(status_code=404, detail="AI predictions not generated yet. Run pipeline first.")

    patient_row = pap_df[pap_df["AtHomePatientId"] == patient_id]
    if patient_row.empty:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    p_dict = patient_row.iloc[0].replace({np.nan: None}).to_dict()

    feat_df = load_cached_csv("features_merged.csv")
    f_dict = {}
    if not feat_df.empty and "AtHomePatientId" in feat_df.columns:
        f_sub = feat_df[feat_df["AtHomePatientId"] == patient_id]
        if not f_sub.empty:
            f_dict = f_sub.iloc[0].replace({np.nan: None}).to_dict()

    playlist = resolve_clinical_video_playlist_for_patient(p_dict, f_dict)
    return {
        "patient_id": patient_id,
        "scenario": "scenario_2_virtual_stitched_playlist",
        "sequence_count": len(playlist),
        "total_duration_s": sum(item.get("duration_s", 10.0) for item in playlist),
        "playlist": playlist
    }


@app.get("/api/patients", dependencies=[Depends(verify_ai_server_auth)])
def list_patients(limit: int = 50, offset: int = 0, high_risk_only: bool = False):
    """Lists patient predictions with pagination and risk filtering (Protected)."""
    pap_df = load_cached_csv("patient_action_plan.csv")
    if pap_df.empty:
        pap_df = load_cached_csv("features_merged.csv")
    if pap_df.empty:
        return {"total": 0, "patients": []}

    df = pap_df
    if high_risk_only and "urgent_flag" in df.columns:
        df = df[df["urgent_flag"] == 1]

    total = len(df)
    subset = df.iloc[offset:offset + limit].replace({np.nan: None}).to_dict(orient="records")
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "patients": subset
    }


# ==============================================================================
# 9. Cohort Metrics & KPI Endpoints
# ==============================================================================
@app.get("/api/metrics")
def get_cohort_metrics():
    """Returns high-level cohort metrics across all model layers."""
    current_state = get_pipeline_state_copy()
    metrics = {
        "total_patients": 0,
        "active_alarms": 0,
        "high_risk_patients": 0,
        "last_updated": current_state["last_run_finish"]
    }

    l0_df = load_cached_csv("layer0_results.csv")
    if not l0_df.empty:
        metrics["total_patients"] = len(l0_df)
        if "any_alarm" in l0_df.columns:
            metrics["active_alarms"] = int(l0_df["any_alarm"].sum())

    pap_df = load_cached_csv("patient_action_plan.csv")
    if not pap_df.empty and "urgent_flag" in pap_df.columns:
        metrics["high_risk_patients"] = int(pap_df["urgent_flag"].sum())

    return metrics


@app.get("/api/kpis")
def get_detailed_kpis():
    """Returns comprehensive clinical, adherence, risk, alarm, biomarker, and video KPIs (JSON)."""
    kpis = load_kpis_summary()
    if kpis:
        return kpis
    return get_cohort_metrics()
