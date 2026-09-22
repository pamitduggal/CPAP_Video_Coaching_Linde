"""
SleepCare AI Server - Model Pipeline Runner & Prediction Dispatcher
===================================================================
This module executes the core supervisory tasks:
1. Building standardized JSON prediction payloads adhering to the backend schema.
2. Pushing patient predictions directly to the central database via REST POST.
3. Executing the M4_FINAL_F2.ipynb Jupyter pipeline via subprocess in clean UTF-8.
4. Continuous 24/7 background scheduler loop running every 30 minutes.
"""

import os
import sys
import time
import logging
import subprocess
import requests
import pandas as pd
from typing import Dict, Any, List, Optional

from core.config import (
    API_BASE,
    HEADERS,
    NOTEBOOK_NAME,
    SYNC_INTERVAL_MINUTES,
    PIPELINE_TIMEOUT_SECONDS,
    MAX_PIPELINE_RETRIES
)
from core.registry import pipeline_state, MODEL_HEALTH, state_lock
from core.interceptor import find_artifact_file, _original_read_csv
from core.video_engine import orchestrate_pipeline_videos

logger = logging.getLogger("CPAP_AI_Server")


# ==============================================================================
# 1. Prediction Payload Builder (Shared across Server & Weekly Scripts)
# ==============================================================================
def build_prediction_payload(
    df: pd.DataFrame,
    patient_filter: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
    """
    Transforms raw prediction DataFrame rows into the standardized JSON payload
    expected by the central database: POST /api/data/predictions.
    """
    if "AtHomePatientId" not in df.columns:
        return []

    target_df = df
    if patient_filter is not None and len(patient_filter) > 0:
        target_ids = {str(int(p)) for p in patient_filter if pd.notna(p)}
        target_df = df[df["AtHomePatientId"].astype(str).isin(target_ids)]

    payload = []
    for _, row in target_df.iterrows():
        if pd.isna(row.get("AtHomePatientId")):
            continue
        item = {
            "patient_id": str(int(row["AtHomePatientId"])),
            "risk_score": round(float(row["z_risk"]), 4) if pd.notna(row.get("z_risk")) else 0.0,
            "risk_tier": str(row["risk_level"]).lower() if pd.notna(row.get("risk_level")) else "low",
            "dropout_prob": round(float(row.get("p_dropout", row.get("z_risk", 0.0))), 4) if pd.notna(row.get("p_dropout", row.get("z_risk"))) else 0.0,
            "dropout_mechanism": str(row.get("dropout_mechanism", "none")),
            "action_proposal": str(row.get("intervention_rec", "None")),
            "intervention_reason": str(row.get("intervention_reason", "")),
            "event_detected": bool(row.get("event_detected", False))
        }
        if pd.notna(row.get("surveys_to_send")) and row["surveys_to_send"] != "none":
            item["surveys_to_send"] = str(row["surveys_to_send"])
        if pd.notna(row.get("event_score")):
            item["event_score"] = round(float(row["event_score"]), 4)

        payload.append(item)

    return payload


# ==============================================================================
# 2. Database Prediction Pusher
# ==============================================================================
def push_predictions_to_backend(patient_filter: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Reads the latest action plan or layer 3 predictions and pushes them
    to backend REST endpoint: POST /api/data/predictions.
    """
    push_url = f"{API_BASE}/predictions"
    results_file = find_artifact_file("patient_action_plan.csv")
    if not os.path.exists(results_file):
        results_file = find_artifact_file("layer3_results.csv")
    if not os.path.exists(results_file):
        logger.warning(f"[AI SERVER PUSH WARNING] Prediction artifact {results_file} not found.")
        return {"status": "skipped", "reason": "No prediction artifacts"}

    try:
        df = _original_read_csv(results_file)
        payload = build_prediction_payload(df, patient_filter=patient_filter)

        logger.info(f"\n[AI SERVER PUSH] Pushing {len(payload)} patient predictions to {push_url}...")
        headers = dict(HEADERS)
        headers["Content-Type"] = "application/json"

        res = requests.post(push_url, headers=headers, json=payload, timeout=60)
        if res.status_code == 200:
            logger.info(f"[AI SERVER PUSH SUCCESS] Backend response: {res.text}")
            try:
                backend_data = res.json()
            except Exception:
                backend_data = res.text
            return {
                "status": "success",
                "backend_response": backend_data
            }
        else:
            logger.error(f"[AI SERVER PUSH ERROR {res.status_code}] {res.text}")
            return {"status": "error", "code": res.status_code, "detail": res.text}
    except Exception as exc:
        logger.error(f"[AI SERVER PUSH EXCEPTION] Failed to push predictions: {exc}")
        return {"status": "exception", "detail": str(exc)}


# ==============================================================================
# 3. Model Pipeline Execution Engine
# ==============================================================================
def execute_supervisor_pipeline() -> bool:
    """
    Executes the M4_FINAL_F2.ipynb Jupyter notebook model pipeline via subprocess.
    Uses UTF-8 encoding and includes automatic retries on transient errors.
    Upon successful completion:
    1. Pushes updated predictions to the central database.
    2. Orchestrates clinical video recommendations to the Video VM Server.
    """
    with state_lock:
        if pipeline_state["status"] == "running":
            logger.warning("[AI SERVER] Pipeline is already actively running. Skipping concurrent trigger.")
            return False
        pipeline_state["status"] = "running"
        pipeline_state["last_run_start"] = time.strftime("%Y-%m-%d %H:%M:%S")

    start_t = time.time()
    logger.info(f"\n[AI SERVER] >>> Triggering AI Supervisor Model Pipeline ({NOTEBOOK_NAME}) at {pipeline_state['last_run_start']}...")

    nb_path = find_artifact_file(NOTEBOOK_NAME)
    cmd = [sys.executable, "-m", "jupyter", "execute", nb_path]
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = f"{os.getcwd()};{env.get('PYTHONPATH', '')}"

    success = False
    last_error_msg = None

    for attempt in range(MAX_PIPELINE_RETRIES + 1):
        try:
            if attempt > 0:
                logger.info(f"[AI SERVER RETRY] Retrying pipeline execution (attempt {attempt + 1}/{MAX_PIPELINE_RETRIES + 1})...")
                time.sleep(2)

            res = subprocess.run(
                cmd,
                cwd=os.getcwd(),
                env=env,
                capture_output=True,
                text=True,
                timeout=PIPELINE_TIMEOUT_SECONDS
            )

            if res.returncode == 0:
                success = True
                break
            else:
                last_error_msg = res.stderr[-500:] if res.stderr else res.stdout[-500:]
                logger.warning(f"[AI SERVER WARN] Attempt {attempt + 1} exited with code {res.returncode}: {last_error_msg}")
        except subprocess.TimeoutExpired as exc:
            last_error_msg = f"Pipeline execution timed out after {PIPELINE_TIMEOUT_SECONDS}s: {exc}"
            logger.error(f"[AI SERVER TIMEOUT] {last_error_msg}")
        except Exception as exc:
            last_error_msg = f"Pipeline execution exception: {exc}"
            logger.error(f"[AI SERVER EXCEPTION] {last_error_msg}")

    elapsed = time.time() - start_t

    with state_lock:
        pipeline_state["last_duration_seconds"] = round(elapsed, 1)
        pipeline_state["last_run_finish"] = time.strftime("%Y-%m-%d %H:%M:%S")
        pipeline_state["total_runs"] += 1
        pipeline_state["model_health"] = dict(MODEL_HEALTH)

        if success:
            pipeline_state["status"] = "idle"
            pipeline_state["last_error"] = None
        else:
            pipeline_state["status"] = "failed"
            pipeline_state["last_error"] = last_error_msg

    if success:
        logger.info(f"[AI SERVER] <<< Pipeline completed successfully in {elapsed:.1f}s!")
        # 1. Push predictions directly to backend API
        push_predictions_to_backend()
        # 2. Orchestrate video recommendations to Video VM Server
        orchestrate_pipeline_videos()
        return True
    else:
        logger.error(f"[AI SERVER ERROR] Pipeline failed: {last_error_msg}")
        return False


# ==============================================================================
# 4. Periodic Background Scheduler
# ==============================================================================
def background_scheduler_loop():
    """
    Background worker that triggers the model pipeline on startup,
    and then periodically every SYNC_INTERVAL_MINUTES.
    Dynamically synchronizes video triggers from the Video VM on each cycle.
    """
    time.sleep(5)  # Initial grace period on startup
    logger.info(f"[AI SERVER SCHEDULER] Periodic sync active (every {SYNC_INTERVAL_MINUTES} mins). Running initial cycle...")
    try:
        from core.registry import sync_video_catalog_from_vm
        sync_video_catalog_from_vm()
    except Exception as exc:
        logger.debug(f"[AI SERVER SCHEDULER] Periodic catalog sync skipped: {exc}")
    execute_supervisor_pipeline()

    while True:
        time.sleep(SYNC_INTERVAL_MINUTES * 60)
        logger.info(f"[AI SERVER SCHEDULER] Periodic interval elapsed ({SYNC_INTERVAL_MINUTES}m). Running scheduled sync...")
        try:
            from core.registry import sync_video_catalog_from_vm
            sync_video_catalog_from_vm()
        except Exception as exc:
            logger.debug(f"[AI SERVER SCHEDULER] Periodic catalog sync skipped: {exc}")
        execute_supervisor_pipeline()
