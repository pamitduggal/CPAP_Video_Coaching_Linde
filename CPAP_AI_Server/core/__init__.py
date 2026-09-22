"""
SleepCare AI Server - Core Modular Architecture Package
========================================================
Exposes the complete AI Supervisor engine:
- Config: API_BASE, HEADERS, SERVER_HOST, SERVER_PORT, ENDPOINT_MAP
- Registry: CLINICAL_VIDEO_REGISTRY, ML_MODELS_REGISTRY, MODEL_HEALTH, pipeline_state
- Data Fetcher: fetch_dataset
- Preprocessor: _process_dataset, normalize_column_casing, synthesize_missing_features
- Interceptor: smart_read_csv, find_artifact_file, apply_runtime_patches, load_cached_csv
- Video Engine: resolve_clinical_video_for_patient, resolve_clinical_video_playlist_for_patient,
                orchestrate_video_recommendation, orchestrate_video_package, trigger_vertex_video_generation
- Pipeline: execute_supervisor_pipeline, push_predictions_to_backend, build_prediction_payload
- Server: app, verify_ai_server_auth
"""

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

__all__ = [
    "API_BASE",
    "ML_KEY",
    "HEADERS",
    "SERVER_HOST",
    "SERVER_PORT",
    "WEBHOOK_PORT",
    "LOCAL_CATALOG_PATH",
    "SYNC_INTERVAL_MINUTES",
    "PIPELINE_TIMEOUT_SECONDS",
    "MAX_PIPELINE_RETRIES",
    "NOTEBOOK_NAME",
    "AI_SERVER_API_KEY",
    "VIDEO_SERVER_URL",
    "VIDEO_SERVER_API_KEY",
    "VIDEO_SERVER_KEY",
    "TARGET_18_PATIENTS",
    "ENDPOINT_MAP",
    "EXPECTED_CASE",
    "JOB_MAP",
    "NUMERIC_COLS",
    "CLINICAL_VIDEO_REGISTRY",
    "ML_MODELS_REGISTRY",
    "MODEL_HEALTH",
    "pipeline_state",
    "state_lock",
    "get_pipeline_state_copy",
    "get_model_health_copy",
    "DYNAMIC_CATALOG_STATE",
    "get_dynamic_catalog_state",
    "update_catalog_from_payload",
    "sync_video_catalog_from_vm",
    "fetch_dataset",
    "_process_dataset",
    "normalize_column_casing",
    "synthesize_missing_features",
    "cast_numeric_columns",
    "smart_read_csv",
    "find_artifact_file",
    "load_cached_csv",
    "apply_runtime_patches",
    "_original_read_csv",
    "extract_telemetry_features",
    "evaluate_dynamic_trigger_rule",
    "resolve_clinical_video_for_patient",
    "resolve_clinical_video_playlist_for_patient",
    "orchestrate_video_recommendation",
    "orchestrate_video_package",
    "trigger_vertex_video_generation",
    "assign_video_to_dashboard",
    "orchestrate_pipeline_videos",
    "VideoOrchestrationClient",
    "VideoAssignmentTracker",
    "get_assignment_tracker",
    "is_video_already_assigned",
    "record_video_assignment",
    "build_prediction_payload",
    "push_predictions_to_backend",
    "execute_supervisor_pipeline",
    "background_scheduler_loop",
    "app",
    "verify_ai_server_auth"
]
