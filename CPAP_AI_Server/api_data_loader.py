"""
SleepCare AI Server - Unified Continuous Service & Data Loader Façade
======================================================================
This module serves as the backwards-compatible front façade for the SleepCare AI Server.
It re-exports all core modular components:
1. REST API Streaming Fetcher & Offline Local CSV Fallback.
2. 12 REST Endpoint Mappings & Schema Validation.
3. Automated column case normalization and missing column synthesis.
4. Transparent runtime compatibility hooks (Pandas 2.x, CatBoost, LightGBM)
   so that M4_FINAL_F2.ipynb runs completely unmodified.
5. Multi-Scenario Clinical Video Intervention Engine (Scenarios 1, 2, 3).
6. Continuous 24/7 FastAPI REST Server (Port 8000) with background scheduler.
"""

import sys
import logging

# Set up clean application-wide logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CPAP_AI_Server")

# ==============================================================================
# 1. Re-export All Core Symbols for 100% Backwards Compatibility
# ==============================================================================
from core.config import (
    API_BASE,
    ML_KEY,
    HEADERS,
    SERVER_HOST,
    SERVER_PORT,
    WEBHOOK_PORT,
    LOCAL_CATALOG_PATH,
    SYNC_INTERVAL_MINUTES,
    PIPELINE_TIMEOUT_SECONDS,
    MAX_PIPELINE_RETRIES,
    NOTEBOOK_NAME,
    AI_SERVER_API_KEY,
    VIDEO_SERVER_URL,
    VIDEO_SERVER_API_KEY,
    VIDEO_SERVER_KEY,
    TARGET_18_PATIENTS,
    ENDPOINT_MAP,
    EXPECTED_CASE,
    JOB_MAP,
    NUMERIC_COLS
)

from core.registry import (
    CLINICAL_VIDEO_REGISTRY,
    ML_MODELS_REGISTRY,
    MODEL_HEALTH,
    pipeline_state,
    state_lock,
    get_pipeline_state_copy,
    get_model_health_copy,
    DYNAMIC_CATALOG_STATE,
    get_dynamic_catalog_state,
    update_catalog_from_payload,
    sync_video_catalog_from_vm
)

from core.data_fetcher import fetch_dataset

from core.preprocessor import (
    _process_dataset,
    normalize_column_casing,
    synthesize_missing_features,
    cast_numeric_columns
)

from core.interceptor import (
    smart_read_csv,
    find_artifact_file,
    load_cached_csv,
    apply_runtime_patches,
    _original_read_csv
)

from core.video_engine import (
    extract_telemetry_features,
    evaluate_dynamic_trigger_rule,
    resolve_clinical_video_for_patient,
    resolve_clinical_video_playlist_for_patient,
    orchestrate_video_recommendation,
    orchestrate_video_package,
    trigger_vertex_video_generation,
    assign_video_to_dashboard,
    orchestrate_pipeline_videos,
    VideoOrchestrationClient,
    VideoAssignmentTracker,
    get_assignment_tracker,
    is_video_already_assigned,
    record_video_assignment
)

from core.pipeline import (
    build_prediction_payload,
    push_predictions_to_backend,
    execute_supervisor_pipeline,
    background_scheduler_loop
)

from core.server import app, verify_ai_server_auth

# Backwards compatibility aliases
_background_scheduler_loop = background_scheduler_loop

# ==============================================================================
# 2. Transparent Runtime Initialization
# ==============================================================================
# Automatically activate pandas interception and ML model patches when imported
apply_runtime_patches()

# ==============================================================================
# 3. Server CLI Entrypoint (run_ai_server.bat integration)
# ==============================================================================
if __name__ == "__main__":
    import os

    logger.info("=" * 75)
    logger.info(" [SYSTEM BOOT] SleepCare CPAP AI Supervisor Server Starting")
    logger.info(f"   SERVER_HOST          : {SERVER_HOST}")
    logger.info(f"   SERVER_PORT          : {SERVER_PORT}")
    logger.info(f"   BACKEND_API_URL      : {API_BASE}")
    logger.info(f"   VIDEO_SERVER_URL     : {VIDEO_SERVER_URL}")
    logger.info(f"   VIDEO_SERVER_API_KEY : {VIDEO_SERVER_API_KEY[:8]}... (active)")
    logger.info(f"   VIDEO_SERVER_KEY     : {VIDEO_SERVER_KEY[:8]}... (active)")
    logger.info(f"   CLINICAL REGISTRY    : {len(CLINICAL_VIDEO_REGISTRY)} curated MP4s + {len(CLINICAL_VIDEO_REGISTRY) * 2} WebVTT Subtitles (EN/FR)")
    logger.info("   ACTIVE SCENARIOS     :")
    logger.info(f"     * SCENARIO 1: Existing Video Selection ({len(CLINICAL_VIDEO_REGISTRY)} Prescriptive Clips)")
    logger.info("     * SCENARIO 2: Videos Stitching Together (Multi-Clip Virtual Packages)")
    logger.info("     * SCENARIO 3: New Video Generation (Google Vertex AI / Veo 3.1)")
    logger.info("=" * 75)

    if "--server" in sys.argv or os.environ.get("RUN_MODE") == "SERVER":
        import uvicorn
        try:
            from scripts.clear_ports import clear_port
            clear_port(SERVER_PORT, "REST API & Dashboard")
            if WEBHOOK_PORT != SERVER_PORT:
                clear_port(WEBHOOK_PORT, "Webhook Receiver")
        except Exception:
            pass
        logger.info(f"[AI SERVER] Launching 24/7 FastAPI Server on {SERVER_HOST}:{SERVER_PORT}...")
        logger.info(f"[AI SERVER] Interactive Dashboard URL: http://localhost:{SERVER_PORT}/dashboard")
        uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, access_log=False)
    else:
        # Default CLI: execute pipeline directly once
        execute_supervisor_pipeline()
