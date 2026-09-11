"""
SleepCare AI Server - Weekly Cohort Scoring & Prediction Dispatcher
===================================================================
Scores the 18 target patients for the weekly cohort window (2026-08-20 to 2026-08-26)
and posts the structured predictions to the central database:
  POST http://159.84.143.151/api/data/predictions
  Header: X-ML-Key: sleepcare-ml-2026
"""

import os
import sys
import json
import logging
import requests
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ScoreWeeklyCohort")

# ==========================================
# Configuration & Target Patient Cohort
# ==========================================
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://159.84.143.151/api/data")
BACKEND_API_KEY = os.environ.get("BACKEND_API_KEY", "")
PUSH_ENDPOINT = f"{BACKEND_API_URL.rstrip('/')}/predictions"

WEEK_START = "2026-08-20"
WEEK_END = "2026-08-26"

# 18 Real Target Patients for ml.patient_week
TARGET_PATIENTS = [
    191831, 57568, 115900, 120269, 121049, 132683, 137368,
    165217, 166322, 167512, 179973, 184235, 190723, 194612,
    196728, 215028, 62229, 63678
]


def load_cohort_predictions(source_csv: str = "patient_action_plan.csv") -> pd.DataFrame:
    """Loads prediction artifacts and filters strictly to the target 18 patients."""
    if not os.path.exists(source_csv):
        # Fallback to layer3_results.csv if patient_action_plan not yet generated
        fallback_csv = "layer3_results.csv"
        if os.path.exists(fallback_csv):
            source_csv = fallback_csv
        else:
            raise FileNotFoundError(f"Neither {source_csv} nor {fallback_csv} found in {os.getcwd()}")

    logger.info(f"Loading prediction artifact: {source_csv}")
    df = pd.read_csv(source_csv)

    if "AtHomePatientId" not in df.columns:
        raise ValueError(f"Missing 'AtHomePatientId' column in {source_csv}")

    # Filter to the 18 target patients
    df["AtHomePatientId"] = pd.to_numeric(df["AtHomePatientId"], errors="coerce").fillna(0).astype(int)
    filtered_df = df[df["AtHomePatientId"].isin(TARGET_PATIENTS)].copy()

    logger.info(f"Found {len(filtered_df)} of {len(TARGET_PATIENTS)} target patients in {source_csv}")
    return filtered_df


def build_prediction_payload(df: pd.DataFrame) -> list:
    """Builds the JSON payload adhering to the ml.patient_week schema."""
    payload = []
    for _, row in df.iterrows():
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


def push_predictions(payload: list) -> dict:
    """Dispatches HTTP POST to backend REST database with X-ML-Key header."""
    headers = {
        "Content-Type": "application/json",
        "X-ML-Key": BACKEND_API_KEY
    }

    logger.info("=" * 70)
    logger.info(f" [ML PIPELINE PREDICTION DISPATCH]")
    logger.info(f"   Target Endpoint  : {PUSH_ENDPOINT}")
    logger.info(f"   Coverage Window  : {WEEK_START} to {WEEK_END}")
    logger.info(f"   Patient Count    : {len(payload)} patients")
    logger.info(f"   Auth Header      : X-ML-Key: {BACKEND_API_KEY}")
    logger.info("=" * 70)

    try:
        response = requests.post(PUSH_ENDPOINT, headers=headers, json=payload, timeout=60)
        logger.info(f"HTTP Response Code: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"Predictions successfully pushed! Backend Response: {response.text}")
            return {
                "status": "success",
                "http_code": response.status_code,
                "response": response.json() if response.headers.get("content-type") == "application/json" else response.text
            }
        else:
            logger.error(f"Failed with HTTP {response.status_code}: {response.text}")
            return {
                "status": "error",
                "http_code": response.status_code,
                "detail": response.text
            }
    except Exception as e:
        logger.error(f"Connection exception during prediction push: {e}")
        return {"status": "exception", "error": str(e)}


def main():
    print("-" * 70)
    print("SLEEPCARE ML PIPELINE - WEEKLY COHORT SCORING")
    print(f"Target Cohort (18 Patients): {TARGET_PATIENTS}")
    print(f"Coverage: {WEEK_START} to {WEEK_END}")
    print("-" * 70)

    df = load_cohort_predictions()
    payload = build_prediction_payload(df)
    result = push_predictions(payload)

    print("\n" + "=" * 70)
    print(f"FINAL EXECUTION RESULT: {result['status'].upper()}")
    print("=" * 70)
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
