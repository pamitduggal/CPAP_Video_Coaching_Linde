"""
SleepCare AI Server - System Configuration & Global Settings
============================================================
This module loads all environment variables, connection URLs, security keys,
and data mapping tables used across the AI Server.
"""

import os

# ==============================================================================
# 1. Backend REST API & Authentication Settings
# ==============================================================================
# Base URL for the clinical database backend (stores CPAP usage, interventions, etc.)
API_BASE = os.environ.get("BACKEND_API_URL", "http://159.84.143.151/api/data")

# API key required to access the backend REST API
ML_KEY = os.environ.get("ML_PREDICTIONS_KEY", os.environ.get("BACKEND_API_KEY", ""))
BACKEND_API_KEY = ML_KEY

# Standard HTTP headers sent with every backend request
HEADERS = {"X-ML-Key": ML_KEY}

# ==============================================================================
# 2. Local AI Server Host & Scheduling Configuration
# ==============================================================================
# Network host address (0.0.0.0 allows connections from all network interfaces)
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")

# HTTP port where the AI supervisor server runs (default: 8000)
SERVER_PORT = int(os.environ.get("SERVER_PORT", 8000))

# Secondary HTTP port for automated catalog push webhooks from Video VM (default: 8001)
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", 8001))

# Local filesystem path for cached distributed trigger catalog
LOCAL_CATALOG_PATH = os.environ.get("LOCAL_CATALOG_PATH", "distributed_trigger_catalog.json")

# How often (in minutes) the background scheduler re-runs the model pipeline (default: 30 mins)
SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", 30))

# Maximum seconds to wait for a notebook pipeline run before timing out (default: 15 mins)
PIPELINE_TIMEOUT_SECONDS = int(os.environ.get("PIPELINE_TIMEOUT_SECONDS", 900))

# Number of automatic retry attempts if the notebook pipeline fails (default: 1 retry)
MAX_PIPELINE_RETRIES = int(os.environ.get("MAX_PIPELINE_RETRIES", 1))

# Notebook file to execute for model predictions
NOTEBOOK_NAME = os.environ.get("NOTEBOOK_NAME", "M4_FINAL_F2.ipynb")

# Internal API key required by clients to call protected AI Server endpoints
AI_SERVER_API_KEY = os.environ.get("AI_SERVER_API_KEY", "")

# ==============================================================================
# 3. Video VM Server Configuration & Security Keys (Port 8080)
# ==============================================================================
# Video Virtual Machine server URL (hosts curated coaching clips and WebVTT subtitles)
VIDEO_SERVER_URL = os.environ.get("VIDEO_SERVER_URL", "http://159.84.143.246:8080")

# Bearer API key for authenticating requests to the Video VM
VIDEO_SERVER_API_KEY = os.environ.get("VIDEO_SERVER_API_KEY", "")

# Shared HMAC secret key between Video VM, AI Server, and Dashboard
VIDEO_SERVER_KEY = os.environ.get("VIDEO_SERVER_KEY", "")

# ==============================================================================
# 4. Target Cohort Patient IDs
# ==============================================================================
# Active benchmark cohort of 18 patients monitored for weekly scoring
TARGET_18_PATIENTS = [
    191831, 57568, 115900, 120269, 121049, 132683, 137368,
    165217, 166322, 167512, 179973, 184235, 190723, 194612,
    196728, 215028, 62229, 63678
]

# ==============================================================================
# 5. Endpoint Mapping: CSV Filenames to REST Endpoints
# ==============================================================================
# When code requests a CSV file by name (e.g. pd.read_csv("Usage3.csv")),
# this dictionary maps that file to its corresponding REST endpoint on the backend.
ENDPOINT_MAP = {
    "usage3.csv": "cpap-usage",
    "intervention3.csv": "interventions",
    "interventiondefinition.csv": "intervention-defs",
    "monitoring3.csv": "monitoring",
    "db_surveys_medical_connected.csv": "medical-surveys",
    "rf.csv": "risk-factors",
    "biomarker_enrollment_mapping.csv": "biomarker-enrollment",
    "db_withings_watch_connected.csv": "withings-watch",
    "db_withings_bpm_core_connected.csv": "withings-bpm",
    "db_masimo_connected.csv": "masimo",
    "db_hexoskin_connected.csv": "hexoskin",
    "db_somnoart_connected.csv": "somnoart"
}

# Canonical case map for standardizing column names across different data sources
EXPECTED_CASE = {
    "jobtypecode": "JobTypeCode",
    "category": "Category",
    "channel": "Channel",
    "athomepatientid": "AtHomePatientId",
    "referencedate": "ReferenceDate",
    "reference_date": "ReferenceDate",
    "status": "Status",
    "s": "Status",
    "use": "Use",
    "ahi": "AHI",
    "leaks95": "Leaks95",
    "leaks90": "Leaks90",
    "leakslargepercentage": "LeaksLargePercentage",
    "devicetype": "DeviceType",
    "presure90": "Presure90",
    "answervalue": "AnswerValue",
    "answer_value": "AnswerValue",
    "questionnaireid": "QuestionnaireId",
    "questionnaire_id": "QuestionnaireId",
    "questionid": "QuestionId",
    "question_id": "QuestionId",
    "riskfactorid": "RiskFactorId",
    "risk_factor_id": "RiskFactorId",
    "riskfactorvalue": "RiskFactorValue",
    "risk_factor_value": "RiskFactorValue",
    "collectiondate": "CollectionDate",
    "collection_date": "CollectionDate",
    "surveyname": "survey_name",
    "scorevalue": "score_value"
}

# Authoritative clinical category mapping for the 73 JobTypeCode entries
# Used when processing Interventiondefinition.csv so the models have valid Category and Channel fields
JOB_MAP = {
    "AD": "Visit", "AW": "Call", "CA": "Visit", "ED": "Visit", "EM": "Visit",
    "LI": "Call", "AP": "Call", "CC": "Call", "AM": "Visit", "MV": "Not Defined",
    "O6": "Visit", "O9": "Visit", "OL": "Visit", "OP": "Visit", "CM": "Visit",
    "OR": "Visit", "EX": "Visit", "HL": "Call", "CZ": "Visit", "T5": "Visit",
    "IH": "Visit", "T7": "Visit", "LU": "Not Defined", "TA": "Visit", "O4": "Call",
    "O7": "Visit", "VA": "Visit", "PI": "Call", "VF": "Visit", "SA": "Call",
    "T9": "SMS", "VD": "Visit", "VH": "Visit", "VK": "Visit", "VR": "Visit",
    "VM": "Visit", "ID": "Call", "WA": "Call", "WS": "Call", "IU": "Visit",
    "MI": "Not Defined", "NC": "Visit", "NJ": "Call", "O1": "SMS", "O2": "Call",
    "O5": "Call", "PG": "Visit", "PH": "Not Defined", "PT": "Visit", "SC": "Visit",
    "SUPPORT_TICKET": "Patient Self-Report", "T1": "Visit", "T2": "Visit", "T3": "Visit",
    "T4": "Visit", "WC": "Call", "WK": "Call", "ED-VID": "Video Coaching", "ET": "Not Defined",
    "FO": "Visit", "LC": "Visit", "MG": "Not Defined", "O3": "Call", "OA": "Visit",
    "PW": "Call", "WM": "Call", "RC": "Visit", "T6": "Visit", "TR": "Visit",
    "TT": "Visit", "V9": "Visit", "VS": "Visit"
}

# List of numerical columns that should be safely cast to floats/ints in Pandas
NUMERIC_COLS = [
    "spo2", "hrv_rmssd", "hrv_sdnn1", "sleep_score", "Use", "AHI", "Leaks95", "Leaks90",
    "LeaksLargePercentage", "Presure90", "systolic_bp", "diastolic_bp", "pulse_rate",
    "heart_rate", "breathing_rate", "sleep_efficiency", "sleep_efficiency_pct",
    "rem_duration_min", "rem_pct", "RiskFactorId", "RiskFactorValue", "score_value",
    "AnswerValue", "AnswerValue_num", "pleth_variability_index", "perfusion_index",
    "respiration_rate", "tst_min", "waso_min", "n3_duration_min", "nb_awakenings",
    "hrv_lf", "hrv_hf", "wakeup_count", "snoring_s"
]
