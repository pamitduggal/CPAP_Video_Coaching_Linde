"""
SleepCare AI Server - Weekly Cohort Scoring & Prediction Dispatcher
===================================================================
Scores the 18 target patients for the weekly cohort window
and posts the structured predictions to the central database:
  POST http://159.84.143.151/api/data/predictions
  Header: X-ML-Key: <BACKEND_API_KEY>
"""

import os
import sys
import logging
import requests
import pandas as pd

# Add parent directory to sys.path to allow imports from core
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.config import (
    API_BASE,
    HEADERS,
    TARGET_18_PATIENTS
)
from core.interceptor import find_artifact_file, _original_read_csv
from core.pipeline import build_prediction_payload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ScoreWeeklyCohort")

# Target Push Endpoint and active evaluation week
PUSH_ENDPOINT = f"{API_BASE.rstrip('/')}/predictions"
WEEK_START = "2026-08-20"
WEEK_END = "2026-08-26"
TARGET_PATIENTS = TARGET_18_PATIENTS


def load_cohort_predictions(source_csv: str = "patient_action_plan.csv") -> pd.DataFrame:
    """Loads prediction artifacts and filters strictly to the target 18 patients."""
    resolved_path = find_artifact_file(source_csv)
    if not os.path.exists(resolved_path):
        resolved_path = find_artifact_file("layer3_results.csv")
    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Neither {source_csv} nor layer3_results.csv found.")

    logger.info(f"Loading prediction artifact: {resolved_path}")
    df = _original_read_csv(resolved_path)

    if "AtHomePatientId" not in df.columns:
        raise ValueError(f"Missing 'AtHomePatientId' column in {resolved_path}")

    # Filter strictly to the 18 target benchmark patients
    df["AtHomePatientId"] = pd.to_numeric(df["AtHomePatientId"], errors="coerce").fillna(0).astype(int)
    filtered_df = df[df["AtHomePatientId"].isin(TARGET_PATIENTS)].copy()

    logger.info(f"Found {len(filtered_df)} of {len(TARGET_PATIENTS)} target patients in {resolved_path}")
    return filtered_df


def push_predictions(payload: list) -> dict:
    """Dispatches HTTP POST to backend REST database with X-ML-Key header."""
    headers = dict(HEADERS)
    headers["Content-Type"] = "application/json"

    logger.info("=" * 70)
    logger.info(f" [ML PIPELINE PREDICTION DISPATCH]")
    logger.info(f"   Target Endpoint  : {PUSH_ENDPOINT}")
    logger.info(f"   Coverage Window  : {WEEK_START} to {WEEK_END}")
    logger.info(f"   Patient Count    : {len(payload)} patients")
    logger.info(f"   Auth Header      : X-ML-Key: {headers.get('X-ML-Key', '')[:8]}...")
    logger.info("=" * 70)

    try:
        response = requests.post(PUSH_ENDPOINT, headers=headers, json=payload, timeout=60)
        logger.info(f"HTTP Response Code: {response.status_code}")

        if response.status_code == 200:
            logger.info(f"Predictions successfully pushed! Backend Response: {response.text}")
            try:
                resp_data = response.json()
            except Exception:
                resp_data = response.text
            return {
                "status": "success",
                "http_code": response.status_code,
                "response": resp_data
            }
        else:
            logger.error(f"Failed with HTTP {response.status_code}: {response.text}")
            return {
                "status": "error",
                "http_code": response.status_code,
                "detail": response.text
            }
    except Exception as exc:
        logger.error(f"Connection exception during prediction push: {exc}")
        return {"status": "exception", "error": str(exc)}


def main():
    print("-" * 70)
    print("SLEEPCARE ML PIPELINE - WEEKLY COHORT SCORING")
    print(f"Target Cohort (18 Patients): {TARGET_PATIENTS}")
    print(f"Coverage: {WEEK_START} to {WEEK_END}")
    print("-" * 70)

    df = load_cohort_predictions()
    payload = build_prediction_payload(df, patient_filter=TARGET_PATIENTS)
    result = push_predictions(payload)

    print("\n" + "=" * 70)
    print(f"FINAL EXECUTION RESULT: {result['status'].upper()}")
    print("=" * 70)
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
