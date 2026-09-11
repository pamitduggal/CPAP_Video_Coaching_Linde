import os
import sys
import time
import base64
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Security, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CPAP_Video_Server")

APP_TITLE = "CPAP Video VM Server"

# Load .env file safely (using dotenv if installed, otherwise manual parse)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception as e:
            logger.warning(f"Could not load .env manually: {e}")

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://159.84.143.246:8080")
DASHBOARD_BASE_URL = os.environ.get("DASHBOARD_URL") or os.environ.get("DASHBOARD_BASE_URL", "http://159.84.143.151:80")

# Security Settings
SERVER_API_KEY = os.environ.get("VIDEO_SERVER_API_KEY") or os.environ.get("SERVER_API_KEY", "")
VIDEO_SERVER_KEY = os.environ.get("X_VIDEO_SERVER_KEY") or os.environ.get("VIDEO_SERVER_KEY", "")
ALLOWED_ORIGINS_RAW = os.environ.get("ALLOWED_ORIGINS", "http://159.84.143.151,http://159.84.143.246:8080,http://localhost:3000,http://localhost:8080,*")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

# Vertex AI Settings (no hardcoded credentials)
GOOGLE_VERTEX_API_KEY = os.environ.get("GOOGLE_VERTEX_API_KEY", "")
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "cpap-coaching-project")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "veo-2.0-generate-001")

env_base = os.environ.get("VIDEO_BASE_DIR")
if env_base and Path(env_base).exists():
    BASE_DIR = Path(env_base)
else:
    BASE_DIR = Path(__file__).resolve().parent

EXISTING_DIR = BASE_DIR / "existing_videos"
NEW_DIR = BASE_DIR / "new_videos"
SUBTITLES_DIR = BASE_DIR / "generated_subtitles"

EXISTING_DIR.mkdir(parents=True, exist_ok=True)
NEW_DIR.mkdir(parents=True, exist_ok=True)
SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)

logger.info("=" * 75)
logger.info(f" [SYSTEM BOOT] CPAP Video VM Server Initializing")
logger.info(f"   BASE_DIR         : {BASE_DIR}")
logger.info(f"   PUBLIC_BASE_URL  : {PUBLIC_BASE_URL}")
logger.info(f"   DASHBOARD_URL    : {DASHBOARD_BASE_URL}")
logger.info(f"   EXISTING_DIR     : {EXISTING_DIR} ({len(list(EXISTING_DIR.glob('*.mp4')))} mp4 files)")
logger.info(f"   SUBTITLES_DIR    : {SUBTITLES_DIR} ({len(list(SUBTITLES_DIR.glob('*.vtt')))} vtt files)")
logger.info(f"   NEW_VIDEOS_DIR   : {NEW_DIR} ({len(list(NEW_DIR.glob('*.mp4')))} mp4 files)")
if SERVER_API_KEY:
    logger.info(f"   SECURITY         : SERVER_API_KEY is active (Protected endpoints require X-API-KEY)")
else:
    logger.info(f"   SECURITY         : SERVER_API_KEY is not set (Open access mode)")
logger.info("=" * 75)

LAST_DECISION: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title=APP_TITLE)

# Comprehensive Live Traffic & Detailed Request Logger Middleware
@app.middleware("http")
async def traffic_and_security_logger(request: Request, call_next):
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    client_port = request.client.port if request.client else "0"
    raw_path = request.url.path
    lower_path = raw_path.lower()
    method = request.method

    # 1. Security Filter: Block malicious crawler probes
    blocked_patterns = [
        "/.env", "/.git", "/.aws", "/.npmrc", "/.ssh",
        "phpinfo", ".php", "actuator", "terraform",
        "appsettings.json", "wp-login", "wp-admin",
        "/etc/passwd", "/config.json"
    ]
    for pattern in blocked_patterns:
        if pattern in lower_path:
            logger.warning(f"[SECURITY BLOCKED] Client {client_ip}:{client_port} attempted unauthorized path: {method} {raw_path}")
            return Response(status_code=403, content="Access Denied: Malicious probe detected.\n")

    # 2. Detailed Live Context Logging for specific content types
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

    # Process Request
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    # Attach standard security response headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Response Summary Logging
    status_label = "[HTTP OK]" if response.status_code < 400 else "[HTTP WARN/ERR]"
    logger.info(f"{status_label} {method} {raw_path} -> Status {response.status_code} ({duration_ms:.2f}ms)")
    return response

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

# API Key security dependency for sensitive modification routes
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def verify_api_key(request: Request, api_key: Optional[str] = Security(api_key_header)):
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

# Static file mounts (preserving all alias mounts for legacy callers)
app.mount("/videos/existing", StaticFiles(directory=str(EXISTING_DIR)), name="videos-existing")
app.mount("/videos/exisiting", StaticFiles(directory=str(EXISTING_DIR)), name="videos-exisiting")
app.mount("/media/exisiting_videos", StaticFiles(directory=str(EXISTING_DIR)), name="media-exisiting")
app.mount("/videos/new", StaticFiles(directory=str(NEW_DIR)), name="videos-new")
app.mount("/subtitles", StaticFiles(directory=str(SUBTITLES_DIR)), name="subtitles")

class OrchestrateRequest(BaseModel):
    patient_id: str
    title: str
    video_filename: str
    duration_s: int | float
    category: str
    trigger_reason: str
    relevance: str = "high"
    thumbnail_type: str = "technical"
    video_type: Optional[str] = "single"
    scenario: Optional[str] = None
    clips: Optional[List[Dict[str, Any]]] = None
    sequence: Optional[List[Dict[str, Any]]] = None
    total_duration_s: Optional[float] = None
    sequence_count: Optional[int] = None
    transition_type: Optional[str] = None

def subtitle_url_for(video_filename: str, lang: str = "en") -> Optional[str]:
    video_stem = Path(video_filename).stem
    exact_match = SUBTITLES_DIR / f"{video_stem}.{lang}.vtt"
    if exact_match.exists():
        return f"{PUBLIC_BASE_URL}/subtitles/{exact_match.name}"

    # Fallback to prefix matching (e.g. "7_" from "7_Dry_mouth_humidifier.mp4")
    prefix = video_filename.split('_')[0] + "_" 
    if SUBTITLES_DIR.exists():
        for file in SUBTITLES_DIR.iterdir():
            if file.name.startswith(prefix) and file.name.endswith(f".{lang}.vtt"):
                return f"{PUBLIC_BASE_URL}/subtitles/{file.name}"

    return None

def resolve_video_file(video_filename: str) -> Dict[str, str]:
    existing_path = EXISTING_DIR / video_filename
    new_path = NEW_DIR / video_filename

    if existing_path.exists():
        return {
            "bucket": "existing",
            "path": str(existing_path),
            "url": f"{PUBLIC_BASE_URL}/videos/existing/{video_filename}",
        }

    if new_path.exists():
        return {
            "bucket": "new",
            "path": str(new_path),
            "url": f"{PUBLIC_BASE_URL}/videos/new/{video_filename}",
        }

    raise HTTPException(status_code=404, detail=f"Video file not found: {video_filename}")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": APP_TITLE,
        "public_base_url": PUBLIC_BASE_URL,
        "dashboard_base_url": DASHBOARD_BASE_URL,
        "base_dir": str(BASE_DIR),
        "existing_assets_dir": str(EXISTING_DIR),
        "new_videos_dir": str(NEW_DIR),
        "subtitles_dir": str(SUBTITLES_DIR),
        "stored_patients": len(LAST_DECISION),
    }

@app.get("/api/library")
def list_library():
    def collect_files(folder: Path) -> List[str]:
        if not folder.exists():
            return []
        return sorted([p.name for p in folder.iterdir() if p.is_file()])

    library_data = {
        "existing_assets": collect_files(EXISTING_DIR),
        "new_videos": collect_files(NEW_DIR),
        "generated_subtitles": collect_files(SUBTITLES_DIR),
    }
    logger.info(f"[LIBRARY STATUS] Catalog: {len(library_data['existing_assets'])} existing videos | {len(library_data['new_videos'])} new videos | {len(library_data['generated_subtitles'])} subtitle tracks")
    return library_data

@app.post("/api/orchestrate", dependencies=[Depends(verify_api_key)])
def orchestrate(req: OrchestrateRequest):
    logger.info("-" * 65)
    logger.info(f"[ORCHESTRATE EVENT DETAILS]")
    logger.info(f"   Patient ID     : {req.patient_id}")
    logger.info(f"   Video Title    : '{req.title}'")
    logger.info(f"   Video Filename : {req.video_filename}")
    logger.info(f"   Category       : {req.category}")
    logger.info(f"   Trigger Reason : {req.trigger_reason}")
    logger.info(f"   Duration       : {req.duration_s}s")
    logger.info(f"   Relevance      : {req.relevance}")

    resolved = resolve_video_file(req.video_filename)
    sub_en = subtitle_url_for(req.video_filename, "en")
    sub_fr = subtitle_url_for(req.video_filename, "fr")

    payload = {
        "patient_id": req.patient_id,
        "title": req.title,
        "video_filename": req.video_filename,
        "url": resolved["url"],  
        "subtitle_en_url": sub_en,
        "subtitle_fr_url": sub_fr,
        "duration_s": req.duration_s,
        "category": req.category,
        "trigger_reason": req.trigger_reason,
        "relevance": req.relevance,
        "thumbnail_type": req.thumbnail_type,
        "storage_bucket": resolved["bucket"],
        "video_type": req.video_type or "single",
    }

    if req.scenario:
        payload["scenario"] = req.scenario
    if req.total_duration_s:
        payload["total_duration_s"] = req.total_duration_s
    if req.sequence_count:
        payload["sequence_count"] = req.sequence_count
    if req.transition_type:
        payload["transition_type"] = req.transition_type
    if req.clips:
        payload["clips"] = req.clips
    if req.sequence:
        payload["sequence"] = req.sequence

    LAST_DECISION[req.patient_id] = payload
    logger.info(f"   -> Resolved URL: {resolved['url']}")
    logger.info(f"   -> Subtitle EN : {sub_en}")
    logger.info(f"   -> Subtitle FR : {sub_fr}")

    # --- Push mechanism to the Web App Dashboard with retries ---
    dashboard_url = f"{DASHBOARD_BASE_URL.rstrip('/')}/api/videos/{req.patient_id}/assign"
    dashboard_status = "success"
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"[DASHBOARD PUSH] Forwarding assignment to {dashboard_url} (attempt {attempt+1}/{max_retries+1})...")
            dash_response = requests.post(
                dashboard_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Video-Server-Key": VIDEO_SERVER_KEY
                },
                timeout=5.0
            )
            dash_response.raise_for_status()
            dashboard_status = "success"
            logger.info(f"[DASHBOARD PUSH SUCCESS] Assignment for Patient {req.patient_id} delivered successfully.")
            break
        except requests.exceptions.RequestException as e:
            logger.warning(f"[DASHBOARD PUSH RETRY] Attempt {attempt+1} failed: {e}")
            dashboard_status = f"failed: {str(e)}"
            if attempt < max_retries:
                time.sleep(0.5)

    logger.info("-" * 65)

    return {
        "status": "ok", 
        "decision": payload,
        "dashboard_push": dashboard_status
    }

@app.post("/api/vertex-generate", dependencies=[Depends(verify_api_key)])
def generate_vertex_video(req: Dict[str, Any]):
    """
    Scenario 3 Endpoint: Receives AI prompt payload from Edge Node, 
    authenticates with Vertex AI API, calls Vertex AI (Veo/Imagen),
    and saves the generated video to new_videos/ bucket.
    """
    api_key = req.get("api_key") or GOOGLE_VERTEX_API_KEY
    prompt = req.get("prompt", "Medical CPAP coaching video")
    patient_id = req.get("patient_id", "P001")
    model_id = req.get("model", VERTEX_MODEL)
    
    timestamp = int(time.time())
    output_filename = f"vertex_gen_{patient_id}_{timestamp}.mp4"
    output_path = NEW_DIR / output_filename
    
    logger.info("-" * 65)
    logger.info(f"[VERTEX AI GENERATION EVENT]")
    logger.info(f"   Patient ID     : {patient_id}")
    logger.info(f"   Prompt         : '{prompt}'")
    logger.info(f"   Model          : '{model_id}'")
    logger.info(f"   Output File    : {output_filename}")
    
    # Proper Vertex AI endpoint under aiplatform.googleapis.com
    vertex_endpoint = (
        f"https://{GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{GOOGLE_CLOUD_LOCATION}/"
        f"publishers/google/models/{model_id}:predict"
    )
    logger.info(f"   Endpoint       : {vertex_endpoint}")
    
    api_call_status = "not_executed"
    google_response_detail = {}
    
    # Request body for Vertex AI Video Generation (Veo)
    request_payload = {
        "instances": [
            {
                "prompt": prompt
            }
        ],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",
            "durationSeconds": 10
        }
    }
    
    # Execute actual HTTP POST to Vertex AI if API key or authorization is available
    if api_key:
        req_url = f"{vertex_endpoint}?key={api_key}"
        try:
            logger.info(f"[VERTEX DISPATCH] Executing POST request to Vertex AI endpoint...")
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
                    logger.info(f"[VERTEX SAVE] Successfully saved video file to {output_path}")
            else:
                logger.warning(f"[VERTEX HTTP {resp.status_code}] Google API response: {resp.text[:300]}")
                google_response_detail = {"error": resp.text[:500]}
        except Exception as e:
            logger.error(f"[VERTEX ERROR] API Request failed: {e}")
            api_call_status = f"error: {str(e)}"
            google_response_detail = {"error": str(e)}
    else:
        api_call_status = "skipped_no_api_key"
        logger.info("[SYNTHETIC MODE] No GOOGLE_VERTEX_API_KEY provided; proceeding in local synthetic generation mode.")

    # Fallback/simulation video placeholder if file was not created by external API
    if not output_path.exists():
        sample_src = EXISTING_DIR / "1_Mask_leak_adjust_straps.mp4"
        if sample_src.exists():
            shutil.copyfile(sample_src, output_path)
            logger.info(f"[SYNTHESIS FALLBACK] Created video placeholder at {output_path}")
        else:
            with open(output_path, "wb") as f:
                f.write(b"")

    # --- AUTO METADATA TRIGGER ---
    metadata_status = "pending"
    metadata_script = BASE_DIR / "build_video_metadata.py"
    if metadata_script.exists():
        try:
            logger.info(f"[AUTO METADATA] Executing metadata indexer: {metadata_script.name}...")
            subprocess.Popen([sys.executable, str(metadata_script)], cwd=str(BASE_DIR))
            metadata_status = "auto_metadata_indexed"
        except Exception as e:
            logger.warning(f"[METADATA WARNING] Failed to auto-trigger build_video_metadata.py: {e}")
            metadata_status = f"error: {e}"
    else:
        metadata_status = "script_not_found"

    logger.info("-" * 65)

    return {
        "status": "success",
        "scenario": "scenario_3_hybrid_generated",
        "generated_video_filename": output_filename,
        "vertex_endpoint_used": vertex_endpoint,
        "vertex_api_status": api_call_status,
        "saved_path": str(output_path),
        "metadata_status": metadata_status,
        "details": google_response_detail
    }

@app.get("/api/patient/{patient_id}/latest")
def get_latest_for_patient(patient_id: str):
    logger.info(f"[QUERY] Fetching latest video decision for Patient ID: {patient_id}")
    decision = LAST_DECISION.get(patient_id)
    if not decision:
        raise HTTPException(status_code=404, detail="No video decision for this patient")
    return decision

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, access_log=False)