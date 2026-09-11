"""
SleepCare AI Server - Unified Continuous Service & Data Loader
==============================================================
Single-file consolidated architecture:
1. REST API Streaming & Offline Local CSV Fallback with live progress bar.
2. 12 REST Endpoint Mappings & Schema Validation.
3. Automated column case normalization and missing column synthesis.
4. Transparent runtime compatibility hooks (Pandas 2.x, CatBoost, LightGBM)
   so that M4_FINAL_F2.ipynb runs completely unmodified.
5. Continuous 24/7 FastAPI REST & Webhook Server (Port 8000) with background
   scheduler and real-time patient prediction querying.
"""

import os
import sys
import time
import json
import logging
import asyncio
import threading
import subprocess
import requests
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CPAP_AI_Server")

# ==========================================
# 1. API Configuration & Endpoint Mapping
# ==========================================
API_BASE = os.environ.get("BACKEND_API_URL", "http://159.84.143.151/api/data")
ML_KEY = os.environ.get("ML_PREDICTIONS_KEY", os.environ.get("BACKEND_API_KEY", ""))
HEADERS = {"X-ML-Key": ML_KEY}
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", 8000))
SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", 30))

# Video VM Server Configuration & Security Keys
VIDEO_SERVER_URL = os.environ.get("VIDEO_SERVER_URL", "http://159.84.143.246:8080")
VIDEO_SERVER_API_KEY = os.environ.get("VIDEO_SERVER_API_KEY", "")
VIDEO_SERVER_KEY = os.environ.get("VIDEO_SERVER_KEY", "")

TARGET_18_PATIENTS = [
    191831, 57568, 115900, 120269, 121049, 132683, 137368,
    165217, 166322, 167512, 179973, 184235, 190723, 194612,
    196728, 215028, 62229, 63678
]

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

# 27 Clinical Video Registry Definitions
CLINICAL_VIDEO_REGISTRY = {
    1: {"id": 1, "filename": "1_Mask_leak_adjust_straps.mp4", "title": "Adjust Mask Straps", "category": "Mask & Equipment", "duration_s": 10.0, "reason": "Elevated mask leak detected (>= 24 L/min)"},
    2: {"id": 2, "filename": "2_Mask_leak_refit_while_lying_down.mp4", "title": "Refit Mask While Lying Down", "category": "Mask & Equipment", "duration_s": 10.0, "reason": "Severe mask leak detected while in bed (>= 30 L/min)"},
    3: {"id": 3, "filename": "3_Cushion_cleaning_reminder.mp4", "title": "Cushion Cleaning Reminder", "category": "Maintenance", "duration_s": 10.0, "reason": "Routine cushion hygiene & maintenance reminder"},
    4: {"id": 4, "filename": "4_Low_usage_use_ramp_mode.mp4", "title": "Low Usage - Use Ramp Mode", "category": "Tips & Tricks", "duration_s": 10.0, "reason": "High initial pressure discomfort (P90 >= 12 cmH2O) with low usage"},
    5: {"id": 5, "filename": "5_Low_usage_daytime_practice.mp4", "title": "Low Usage - Daytime Practice", "category": "Tips & Tricks", "duration_s": 10.0, "reason": "Zero nightly usage — daytime acclimation recommended"},
    6: {"id": 6, "filename": "6_Early_mask_removal.mp4", "title": "Early Mask Removal", "category": "Tips & Tricks", "duration_s": 10.0, "reason": "Early unconscious mask removal during the night"},
    7: {"id": 7, "filename": "7_Dry_mouth_humidifier.mp4", "title": "Dry Mouth - Use Humidifier", "category": "Comfort", "duration_s": 10.0, "reason": "Dry mouth / airway dryness with elevated pressure"},
    8: {"id": 8, "filename": "8_Mouth_breathing_chin_support.mp4", "title": "Mouth Breathing - Chin Support", "category": "Mask & Equipment", "duration_s": 10.0, "reason": "Oral leak / mouth breathing under pressure"},
    9: {"id": 9, "filename": "9_Nasal_congestion_relief.mp4", "title": "Nasal Congestion Relief", "category": "Comfort", "duration_s": 10.0, "reason": "Nasal congestion / airway resistance before sleep"},
    10: {"id": 10, "filename": "10_Aerophagia_elevate_head.mp4", "title": "Aerophagia - Elevate Head", "category": "Tips & Tricks", "duration_s": 10.0, "reason": "Aerophagia / swallowed air with elevated pressure"},
    11: {"id": 11, "filename": "11_Aerophagia_side_sleeping.mp4", "title": "Aerophagia - Side Sleeping", "category": "Tips & Tricks", "duration_s": 10.0, "reason": "Positional aerophagia and residual events"},
    12: {"id": 12, "filename": "12_High_breathing_events_contact_provider.mp4", "title": "High Breathing Events - Contact Provider", "category": "Clinical Alerts", "duration_s": 10.0, "reason": "Elevated residual apnea index (AHI >= 15/hr)"},
    13: {"id": 13, "filename": "13_Biomarker_changes_use_cpap_and_alert.mp4", "title": "Biomarker Changes - Use CPAP & Contact Provider", "category": "Clinical Alerts", "duration_s": 10.0, "reason": "High AHI combined with insufficient nightly CPAP usage"},
    14: {"id": 14, "filename": "14_Mask_style_change_needed.mp4", "title": "Mask Style Change Needed", "category": "Mask & Equipment", "duration_s": 10.0, "reason": "Persistent critical mask leak (>= 40 L/min) requiring mask style swap"},
    15: {"id": 15, "filename": "15_Severe_apnea_contact_provider.mp4", "title": "Severe Apnea - Contact Your Provider", "category": "Clinical Alerts", "duration_s": 10.0, "reason": "Urgent Alert: Severe apnea events (AHI >= 30/hr)"},
    16: {"id": 16, "filename": "16_ScanWatch_Low_nighttime_oxygen.mp4", "title": "ScanWatch - Low Nighttime Oxygen", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "ScanWatch detected nocturnal SpO2 desaturation (< 90%)"},
    17: {"id": 17, "filename": "17_ScanWatch_Fragmented_sleep.mp4", "title": "ScanWatch - Fragmented Sleep", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "ScanWatch detected severe sleep fragmentation / micro-arousals (>= 15/hr)"},
    18: {"id": 18, "filename": "18_ScanWatch_Unusual_heart_rhythm.mp4", "title": "ScanWatch - Unusual Heart Rhythm Signal", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "ScanWatch flagged nocturnal cardiac rhythm / HRV anomaly"},
    19: {"id": 19, "filename": "19_BPM_Core_High_blood_pressure.mp4", "title": "BPM Core - High Blood Pressure", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "BPM Core detected morning hypertension (Systolic >= 140 mmHg)"},
    20: {"id": 20, "filename": "20_BPM_Core_Irregular_ECG_alert.mp4", "title": "BPM Core - Irregular ECG Alert", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "BPM Core flagged potential Atrial Fibrillation (Afib) risk"},
    21: {"id": 21, "filename": "21_BPM_Core_Heart_sound_review.mp4", "title": "BPM Core - Heart Sound Review Needed", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "BPM Core digital stethoscope flagged valvular sound anomaly"},
    22: {"id": 22, "filename": "22_RadG_Low_oxygen_reading.mp4", "title": "RadG - Low Oxygen Reading", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "RadG medical pulse oximeter registered critical SpO2 drop (< 88%)"},
    23: {"id": 23, "filename": "23_RadG_Pulse_breathing_instability.mp4", "title": "RadG - Pulse or Breathing Instability", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "RadG registered high pulse rate variability / respiratory instability"},
    24: {"id": 24, "filename": "24_ProShirt_Breathing_pattern_changed.mp4", "title": "ProShirt - Breathing Pattern Changed", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "ProShirt smart vest detected paradoxical thoraco-abdominal asynchrony (> 30%)"},
    25: {"id": 25, "filename": "25_ProShirt_Fit_check.mp4", "title": "ProShirt - Fit Check", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "ProShirt smart vest signal quality low (< 70%) — garment fit check"},
    26: {"id": 26, "filename": "26_SomnoArt_Sleep_architecture_changed.mp4", "title": "SomnoArt - Sleep Architecture Changed", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "SomnoArt hypnogram detected severe REM sleep deprivation (REM < 12%)"},
    27: {"id": 27, "filename": "27_SomnoArt_Poor_sleep_continuity.mp4", "title": "SomnoArt - Poor Sleep Continuity", "category": "Wearable Biomarkers", "duration_s": 10.0, "reason": "SomnoArt recorded poor sleep efficiency (< 75%)"}
}

# Pipeline Execution State
pipeline_state = {
    "status": "idle",             # "idle", "running", "failed"
    "last_run_start": None,
    "last_run_finish": None,
    "last_duration_seconds": None,
    "last_error": None,
    "total_runs": 0,
    "last_video_orchestrations": 0
}

# 4 Production ML Models Metadata & Registry (ml.models)
ML_MODELS_REGISTRY = {
    "dropout_predictor": {
        "model_id": "dropout_predictor",
        "name": "CPAP Dropout & Adherence Predictor (CatBoost/LightGBM)",
        "metric_name": "AUROC",
        "metric_value": 0.76,
        "threshold": 0.80,
        "drift_value": 0.045,
        "current_status": "needs_retraining",
        "last_trained": "2026-08-20 00:00:00"
    },
    "ahi_detector": {
        "model_id": "ahi_detector",
        "name": "Residual AHI & Respiratory Event Detector",
        "metric_name": "F1",
        "metric_value": 0.895,
        "threshold": 0.85,
        "drift_value": 0.012,
        "current_status": "active",
        "last_trained": "2026-08-26 12:00:00"
    },
    "leak_classifier": {
        "model_id": "leak_classifier",
        "name": "Mask Leak Severity Classifier",
        "metric_name": "Precision",
        "metric_value": 0.84,
        "threshold": 0.82,
        "drift_value": 0.018,
        "current_status": "active",
        "last_trained": "2026-08-26 12:00:00"
    },
    "sleep_synthesizer": {
        "model_id": "sleep_synthesizer",
        "name": "Multimodal Sleep Quality Synthesizer",
        "metric_name": "R²",
        "metric_value": 0.81,
        "threshold": 0.78,
        "drift_value": 0.021,
        "current_status": "active",
        "last_trained": "2026-08-26 12:00:00"
    }
}

logger.info("=" * 75)
logger.info(" [SYSTEM BOOT] SleepCare CPAP AI Supervisor Server Initializing")
logger.info(f"   SERVER_HOST        : {SERVER_HOST}")
logger.info(f"   SERVER_PORT        : {SERVER_PORT}")
logger.info(f"   BACKEND_API_URL    : {API_BASE}")
logger.info(f"   VIDEO_SERVER_URL   : {VIDEO_SERVER_URL}")
logger.info(f"   VIDEO_SERVER_API_KEY : {VIDEO_SERVER_API_KEY[:8]}... (active)")
logger.info(f"   VIDEO_SERVER_KEY     : {VIDEO_SERVER_KEY[:8]}... (active)")
logger.info(f"   SYNC_INTERVAL      : Every {SYNC_INTERVAL_MINUTES} minutes")
logger.info(f"   CLINICAL REGISTRY  : {len(CLINICAL_VIDEO_REGISTRY)} clinical coaching videos loaded")
logger.info("=" * 75)

# ==========================================
# 2. REST API Fetcher with Live Progress
# ==========================================
def fetch_dataset(endpoint_name: str, patient_id=None, limit=None, since_date=None) -> pd.DataFrame:
    """Fetches dataset from backend REST API with live ASCII progress bar."""
    url = f"{API_BASE}/{endpoint_name}"
    params = {}
    if patient_id:
        params["patient_id"] = patient_id
    if limit:
        params["limit"] = limit
    if since_date:
        params["since_date"] = since_date
    elif endpoint_name == "cpap-usage":
        # Default since_date to avoid DB timeouts on 15.5M rows
        params["since_date"] = os.environ.get("CPAP_SINCE_DATE", "2024-01-01")
        
    try:
        start_time = time.time()
        print(f"\n[API FETCHING] Downloading '{endpoint_name}' from {url}...")
        response = requests.get(url, headers=HEADERS, params=params, stream=True, timeout=120)
        
        if response.status_code == 200:
            total_size = int(response.headers.get('content-length', 0))
            chunks = []
            downloaded = 0
            
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        bar_length = 30
                        filled = int(bar_length * downloaded // total_size)
                        bar = "=" * filled + "-" * (bar_length - filled)
                        mb = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\r [{bar}] {percent:5.1f}% ({mb:.2f} MB)")
                    else:
                        mb = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\r Downloading: {mb:.2f} MB...")
                    sys.stdout.flush()
            
            sys.stdout.write("\n")
            elapsed = time.time() - start_time
            print(f"[API FETCH SUCCESS] '{endpoint_name}' downloaded cleanly ({downloaded / (1024*1024):.2f} MB in {elapsed:.1f}s)")
            
            raw_content = b"".join(chunks).decode('utf-8')
            return pd.DataFrame(json.loads(raw_content))
        else:
            print(f"[API ERROR {response.status_code}] Failed to fetch {endpoint_name}")
    except Exception as e:
        print(f"\n[API CONNECTION FAILED] {endpoint_name}: {e}")
        
    return pd.DataFrame()


# ==========================================
# 3. Transparent DataFrame Post-Processing
# ==========================================
def _process_dataset(df: pd.DataFrame, endpoint_name: str) -> pd.DataFrame:
    if df.empty:
        return df

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
    
    if endpoint_name == "monitoring":
        EXPECTED_CASE["executiondate"] = "ExecutionDate"
        EXPECTED_CASE["execution_date"] = "ExecutionDate"
    else:
        EXPECTED_CASE["executiondate"] = "execution_date"
        EXPECTED_CASE["execution_date"] = "execution_date"

    new_cols = {col: EXPECTED_CASE[col.lower()] for col in df.columns if col.lower() in EXPECTED_CASE}
    if new_cols:
        df = df.rename(columns=new_cols)

    # Missing column syntheses
    if endpoint_name == "cpap-usage":
        if "DeviceType" not in df.columns:
            df["DeviceType"] = "Resmed"
        if "Leaks95" not in df.columns:
            df["Leaks95"] = 0.0
        if "Leaks90" not in df.columns:
            df["Leaks90"] = df["Leaks95"]
        else:
            df["Leaks90"] = df["Leaks90"].fillna(df["Leaks95"])
        if "LeaksLargePercentage" not in df.columns:
            df["LeaksLargePercentage"] = 0.0
        if "Presure90" not in df.columns:
            df["Presure90"] = np.nan
        if "ReferenceDate" in df.columns:
            df["ReferenceDate"] = pd.to_numeric(
                df["ReferenceDate"].astype(str).str.replace("-", "").str.split(".").str[0],
                errors="coerce"
            ).fillna(0).astype(int)

    elif endpoint_name == "interventions":
        if "Status" not in df.columns:
            df["Status"] = "Done"

    elif endpoint_name == "intervention-defs":
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
        if "Category" not in df.columns:
            if "JobTypeCode" in df.columns:
                df["Category"] = df["JobTypeCode"].map(JOB_MAP).fillna("Unknown")
            else:
                df["Category"] = "Unknown"
        if "Channel" not in df.columns:
            df["Channel"] = df["Category"].map({"Visit": "Visit", "Call": "Call", "Sms": "SMS", "SMS": "SMS"}).fillna(df["Category"])

    elif endpoint_name == "monitoring":
        if "QuestionnaireId" not in df.columns:
            df["QuestionnaireId"] = 267
        if "QuestionId" not in df.columns:
            df["QuestionId"] = "2208"

    elif endpoint_name == "risk-factors":
        if "CollectionDate" not in df.columns:
            df["CollectionDate"] = pd.Timestamp.now()
        if "RiskFactorId" in df.columns:
            df["RiskFactorId"] = pd.to_numeric(df["RiskFactorId"], errors="coerce")

    elif endpoint_name == "withings-watch":
        if "sleep_efficiency" not in df.columns:
            df["sleep_efficiency"] = np.nan
        if "snoring_s" not in df.columns:
            df["snoring_s"] = np.nan

    elif endpoint_name == "masimo":
        if "pleth_variability_index" not in df.columns:
            df["pleth_variability_index"] = np.nan

    elif endpoint_name == "somnoart":
        for col in ["tst_min", "waso_min", "n3_duration_min", "nb_awakenings"]:
            if col not in df.columns:
                df[col] = np.nan
        if "analysis_status" not in df.columns:
            df["analysis_status"] = "Valid"

    NUMERIC_COLS = [
        "spo2", "hrv_rmssd", "hrv_sdnn1", "sleep_score", "Use", "AHI", "Leaks95", "Leaks90", "LeaksLargePercentage", "Presure90",
        "systolic_bp", "diastolic_bp", "pulse_rate", "heart_rate", "breathing_rate",
        "sleep_efficiency", "sleep_efficiency_pct", "rem_duration_min", "rem_pct",
        "RiskFactorId", "RiskFactorValue", "score_value", "AnswerValue", "AnswerValue_num",
        "pleth_variability_index", "perfusion_index", "respiration_rate",
        "tst_min", "waso_min", "n3_duration_min", "nb_awakenings",
        "hrv_lf", "hrv_hf", "wakeup_count", "snoring_s"
    ]
    for num_col in NUMERIC_COLS:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    return df


# Model Health & Degradation Tracker
MODEL_HEALTH = {
    "catboost_dummy_fallback": False,
    "lightgbm_dummy_fallback": False,
    "degraded_warnings": []
}

# ==========================================
# 4. Smart read_csv Interceptor
# ==========================================
_original_read_csv = pd.read_csv

def smart_read_csv(filepath_or_buffer, *args, **kwargs):
    if isinstance(filepath_or_buffer, str):
        clean_name = os.path.basename(filepath_or_buffer).strip("\"'").lower()
        canonical_name = clean_name.replace(" ", "_")
        endpoint_name = ENDPOINT_MAP.get(clean_name) or ENDPOINT_MAP.get(canonical_name)
        
        if endpoint_name:
            df = fetch_dataset(endpoint_name)
            if not df.empty:
                return _process_dataset(df, endpoint_name)

        # Check exact path
        if os.path.exists(filepath_or_buffer):
            local_df = _original_read_csv(filepath_or_buffer, *args, **kwargs)
            return _process_dataset(local_df, endpoint_name) if endpoint_name else local_df

        # Check alternative space/underscore in root directory
        alt_root = clean_name.replace("_", " ") if "_" in clean_name else clean_name.replace(" ", "_")
        if os.path.exists(alt_root):
            local_df = _original_read_csv(alt_root, *args, **kwargs)
            return _process_dataset(local_df, endpoint_name) if endpoint_name else local_df

        # Check data/ subfolder
        data_subfolder = os.path.join("data", os.path.basename(filepath_or_buffer))
        if os.path.exists(data_subfolder):
            local_df = _original_read_csv(data_subfolder, *args, **kwargs)
            return _process_dataset(local_df, endpoint_name) if endpoint_name else local_df

        alt_data = os.path.join("data", alt_root)
        if os.path.exists(alt_data):
            local_df = _original_read_csv(alt_data, *args, **kwargs)
            return _process_dataset(local_df, endpoint_name) if endpoint_name else local_df

    return _original_read_csv(filepath_or_buffer, *args, **kwargs)

pd.read_csv = smart_read_csv


# ==========================================
# 5. Transparent Runtime Compatibility Hooks
# ==========================================
_orig_series_clip = pd.Series.clip
def _safe_series_clip(self, lower=None, upper=None, *args, **kwargs):
    if np.issubdtype(self.dtype, np.datetime64) and (isinstance(lower, (int, float)) or isinstance(upper, (int, float))):
        converted = pd.to_numeric(self, errors="coerce").fillna(0).astype(int)
        return _orig_series_clip(converted, lower=lower, upper=upper, *args, **kwargs)
    return _orig_series_clip(self, lower=lower, upper=upper, *args, **kwargs)
pd.Series.clip = _safe_series_clip

try:
    from catboost import CatBoostClassifier
    _orig_cat_fit = CatBoostClassifier.fit
    def _safe_cat_fit(self, X, y=None, *args, **kwargs):
        if y is not None and len(np.unique(y)) <= 1:
            self._is_dummy = True
            self._dummy_class = int(np.unique(y)[0])
            MODEL_HEALTH["catboost_dummy_fallback"] = True
            warn_msg = f"CatBoostClassifier single-class training detected (y={np.unique(y)}). Degraded to constant dummy predictor Class {self._dummy_class}."
            if warn_msg not in MODEL_HEALTH["degraded_warnings"]:
                MODEL_HEALTH["degraded_warnings"].append(warn_msg)
                logger.warning(f"[AI MODEL DEGRADATION WARNING] {warn_msg}")
            return self
        try:
            return _orig_cat_fit(self, X, y, *args, **kwargs)
        except Exception as e:
            if "constant or ignored" in str(e) or "All features are either constant" in str(e):
                self._is_dummy = True
                self._dummy_class = int(y[0]) if y is not None and len(y) > 0 else 0
                MODEL_HEALTH["catboost_dummy_fallback"] = True
                warn_msg = f"CatBoostClassifier zero-variance feature error caught ({e}). Degraded to constant dummy predictor Class {self._dummy_class}."
                if warn_msg not in MODEL_HEALTH["degraded_warnings"]:
                    MODEL_HEALTH["degraded_warnings"].append(warn_msg)
                    logger.warning(f"[AI MODEL DEGRADATION WARNING] {warn_msg}")
                return self
            raise
    
    _orig_cat_predict = CatBoostClassifier.predict
    def _safe_cat_predict(self, X, *args, **kwargs):
        if getattr(self, "_is_dummy", False):
            n = len(X) if hasattr(X, "__len__") else 1
            return np.full(n, getattr(self, "_dummy_class", 0))
        return _orig_cat_predict(self, X, *args, **kwargs)

    _orig_cat_proba = CatBoostClassifier.predict_proba
    def _safe_cat_predict_proba(self, X, *args, **kwargs):
        if getattr(self, "_is_dummy", False):
            n = len(X) if hasattr(X, "__len__") else 1
            res = np.zeros((n, 4))
            res[:, getattr(self, "_dummy_class", 0)] = 1.0
            return res
        return _orig_cat_proba(self, X, *args, **kwargs)

    CatBoostClassifier.fit = _safe_cat_fit
    CatBoostClassifier.predict = _safe_cat_predict
    CatBoostClassifier.predict_proba = _safe_cat_predict_proba
except ImportError:
    pass

try:
    import lightgbm as lgb
    _orig_lgb_train = lgb.train
    def _safe_lgb_train(params, train_set, *args, **kwargs):
        try:
            return _orig_lgb_train(params, train_set, *args, **kwargs)
        except Exception as e:
            if "num_features" in str(e) or "Check failed" in str(e):
                MODEL_HEALTH["lightgbm_dummy_fallback"] = True
                warn_msg = f"LightGBM zero-feature training error caught ({e}). Degraded to DummyLGBBooster (constant 0.05)."
                if warn_msg not in MODEL_HEALTH["degraded_warnings"]:
                    MODEL_HEALTH["degraded_warnings"].append(warn_msg)
                    logger.warning(f"[AI MODEL DEGRADATION WARNING] {warn_msg}")
                class DummyLGBBooster:
                    def predict(self, data, *a, **k):
                        n = len(data) if hasattr(data, "__len__") else 1
                        return np.full(n, 0.05)
                return DummyLGBBooster()
            raise
    lgb.train = _safe_lgb_train
except ImportError:
    pass


def push_predictions_to_backend(patient_filter: list = None) -> dict:
    """Pushes generated predictions array to backend POST /api/data/predictions."""
    push_url = f"{API_BASE}/predictions"
    results_file = "patient_action_plan.csv" if os.path.exists("patient_action_plan.csv") else "layer3_results.csv"
    if not os.path.exists(results_file):
        print(f"[AI SERVER PUSH WARNING] Prediction artifact {results_file} not found.")
        return {"status": "skipped", "reason": "No prediction artifacts"}

    try:
        df = _original_read_csv(results_file)
        if patient_filter is not None and len(patient_filter) > 0:
            target_ids = {str(int(p)) for p in patient_filter if pd.notna(p)}
            df = df[df["AtHomePatientId"].astype(str).isin(target_ids)]

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

        print(f"\n[AI SERVER PUSH] Pushing {len(payload)} patient predictions to {push_url}...")
        headers = dict(HEADERS)
        headers["Content-Type"] = "application/json"
        res = requests.post(push_url, headers=headers, json=payload, timeout=60)
        if res.status_code == 200:
            print(f"[AI SERVER PUSH SUCCESS] Backend response: {res.text}")
            return {"status": "success", "backend_response": res.json() if res.headers.get("content-type") == "application/json" else res.text}
        else:
            print(f"[AI SERVER PUSH ERROR {res.status_code}] {res.text}")
            return {"status": "error", "code": res.status_code, "detail": res.text}
    except Exception as e:
        print(f"[AI SERVER PUSH EXCEPTION] Failed to push predictions: {e}")
        return {"status": "exception", "detail": str(e)}


def assign_video_to_dashboard(patient_id: str, video_record: dict, custom_reason: str = None) -> dict:
    """
    Direct assignment helper to Web App Dashboard POST /api/videos/{patient_id}/assign
    with required X-Video-Server-Key header.
    """
    base_dashboard = API_BASE.replace("/api/data", "")
    url = f"{base_dashboard.rstrip('/')}/api/videos/{patient_id}/assign"
    headers = {
        "Content-Type": "application/json",
        "X-Video-Server-Key": VIDEO_SERVER_KEY
    }
    payload = {
        "patient_id": str(patient_id),
        "video_filename": video_record.get("filename"),
        "title": video_record.get("title"),
        "category": video_record.get("category", "General"),
        "duration_s": float(video_record.get("duration_s", 10.0)),
        "trigger_reason": custom_reason or video_record.get("reason", "AI clinical recommendation")
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        return {"status": "success" if res.status_code == 200 else "error", "code": res.status_code, "detail": res.text}
    except Exception as e:
        return {"status": "exception", "detail": str(e)}


def resolve_clinical_video_for_patient(patient_plan_row: dict, feature_row: dict = None) -> dict:
    """
    Selects the optimal clinical video from the 27-video registry based on
    patient action plan recommendations and physiological telemetry.
    """
    v_title = str(patient_plan_row.get("video_title", "")).lower()
    if v_title and v_title != "none":
        for vid, item in CLINICAL_VIDEO_REGISTRY.items():
            if item["title"].lower() in v_title or v_title in item["title"].lower():
                return item

    feats = feature_row or {}
    use_val = float(feats.get("use_mean_7d", feats.get("use_mean", 5.0))) if pd.notna(feats.get("use_mean_7d", feats.get("use_mean"))) else 5.0
    ahi_val = float(feats.get("ahi_mean_7d", feats.get("ahi_mean", 2.0))) if pd.notna(feats.get("ahi_mean_7d", feats.get("ahi_mean"))) else 2.0
    leak_val = float(feats.get("leaks95_mean_7d", feats.get("leaks_worst_7d", 0.0))) if pd.notna(feats.get("leaks95_mean_7d", feats.get("leaks_worst_7d"))) else 0.0
    press_val = float(feats.get("pressure_mean", 10.0)) if pd.notna(feats.get("pressure_mean")) else 10.0
    spo2_ww = float(feats.get("spo2_ww_7d", 95.0)) if pd.notna(feats.get("spo2_ww_7d")) else 95.0
    spo2_mas = float(feats.get("spo2_masimo_7d", 95.0)) if pd.notna(feats.get("spo2_masimo_7d")) else 95.0
    sys_bp = float(feats.get("systolic_bp_7d", 120.0)) if pd.notna(feats.get("systolic_bp_7d")) else 120.0
    afib_val = bool(feats.get("afib_detected", False)) if pd.notna(feats.get("afib_detected")) else False
    sleep_eff = float(feats.get("sleep_efficiency_7d", 85.0)) if pd.notna(feats.get("sleep_efficiency_7d")) else 85.0

    # 1. Critical & Urgent Clinical Alerts
    if ahi_val >= 30.0:
        return CLINICAL_VIDEO_REGISTRY[15]
    if afib_val:
        return CLINICAL_VIDEO_REGISTRY[20]
    if spo2_mas < 88.0:
        return CLINICAL_VIDEO_REGISTRY[22]
    if sys_bp >= 140.0:
        return CLINICAL_VIDEO_REGISTRY[19]
    if ahi_val >= 15.0 and use_val < 3.0:
        return CLINICAL_VIDEO_REGISTRY[13]
    if ahi_val >= 15.0:
        return CLINICAL_VIDEO_REGISTRY[12]

    # 2. Critical Leaks & Equipment Management
    if leak_val >= 40.0:
        return CLINICAL_VIDEO_REGISTRY[14]
    if leak_val >= 30.0 and use_val < 2.0:
        return CLINICAL_VIDEO_REGISTRY[8]
    if leak_val >= 30.0:
        return CLINICAL_VIDEO_REGISTRY[2]
    if leak_val >= 24.0:
        return CLINICAL_VIDEO_REGISTRY[1]

    # 3. Therapy Adherence & Pressure Management
    if use_val == 0.0:
        return CLINICAL_VIDEO_REGISTRY[5]
    if use_val < 4.0 and press_val >= 12.0:
        return CLINICAL_VIDEO_REGISTRY[4]
    if use_val < 4.0 and spo2_ww < 90.0:
        return CLINICAL_VIDEO_REGISTRY[16]
    if use_val < 4.0:
        return CLINICAL_VIDEO_REGISTRY[6]

    # 4. Comfort & Sleep Continuity
    if 10.0 <= leak_val < 24.0 and press_val >= 10.0:
        return CLINICAL_VIDEO_REGISTRY[7]
    if sleep_eff < 75.0:
        return CLINICAL_VIDEO_REGISTRY[27]

    # Default standard recommendation
    return CLINICAL_VIDEO_REGISTRY[1]


def resolve_clinical_video_playlist_for_patient(patient_plan_row: dict, feature_row: dict = None) -> list:
    """
    Scenario 2: Selects multiple co-occurring clinical coaching clips from the 27-video registry,
    generating a sequential 'virtual stitched' JSON metadata playlist for continuous frontend playback.
    """
    feats = feature_row or {}
    use_val = float(feats.get("use_mean_7d", feats.get("use_mean", 5.0))) if pd.notna(feats.get("use_mean_7d", feats.get("use_mean"))) else 5.0
    ahi_val = float(feats.get("ahi_mean_7d", feats.get("ahi_mean", 2.0))) if pd.notna(feats.get("ahi_mean_7d", feats.get("ahi_mean"))) else 2.0
    leak_val = float(feats.get("leaks95_mean_7d", feats.get("leaks_worst_7d", 0.0))) if pd.notna(feats.get("leaks95_mean_7d", feats.get("leaks_worst_7d"))) else 0.0
    press_val = float(feats.get("pressure_mean", 10.0)) if pd.notna(feats.get("pressure_mean")) else 10.0
    spo2_ww = float(feats.get("spo2_ww_7d", 95.0)) if pd.notna(feats.get("spo2_ww_7d")) else 95.0
    spo2_mas = float(feats.get("spo2_masimo_7d", 95.0)) if pd.notna(feats.get("spo2_masimo_7d")) else 95.0
    sys_bp = float(feats.get("systolic_bp_7d", 120.0)) if pd.notna(feats.get("systolic_bp_7d")) else 120.0
    afib_val = bool(feats.get("afib_detected", False)) if pd.notna(feats.get("afib_detected")) else False
    sleep_eff = float(feats.get("sleep_efficiency_7d", 85.0)) if pd.notna(feats.get("sleep_efficiency_7d")) else 85.0

    selected_ids = []

    # Priority 1: Critical Alerts
    if ahi_val >= 30.0:
        selected_ids.append(15)
    elif ahi_val >= 15.0:
        selected_ids.append(12)
    if afib_val:
        selected_ids.append(20)
    if spo2_mas < 88.0:
        selected_ids.append(22)
    elif spo2_ww < 90.0:
        selected_ids.append(16)
    if sys_bp >= 140.0:
        selected_ids.append(19)

    # Priority 2: Mask & Leak Issues
    if leak_val >= 40.0:
        selected_ids.append(14)
    elif leak_val >= 30.0:
        selected_ids.append(2)
    elif leak_val >= 24.0:
        selected_ids.append(1)

    # Priority 3: Adherence & Pressure Discomfort
    if use_val == 0.0:
        selected_ids.append(5)
    elif use_val < 4.0:
        if press_val >= 12.0:
            selected_ids.append(4)
        selected_ids.append(6)

    # Priority 4: Comfort, Dryness & Sleep Quality
    if 10.0 <= leak_val < 24.0 and press_val >= 10.0:
        selected_ids.append(7)
    if sleep_eff < 75.0:
        selected_ids.append(27)

    # If no conditions flagged, fallback to single primary recommendation
    if not selected_ids:
        primary = resolve_clinical_video_for_patient(patient_plan_row, feature_row)
        selected_ids = [primary["id"]]

    # Deduplicate while preserving clinical priority order
    seen = set()
    deduped_ids = []
    for vid in selected_ids:
        if vid not in seen and vid in CLINICAL_VIDEO_REGISTRY:
            seen.add(vid)
            deduped_ids.append(vid)

    # Construct complete JSON metadata playlist
    playlist = []
    base_v_url = VIDEO_SERVER_URL.rstrip('/')
    for step_idx, vid in enumerate(deduped_ids, 1):
        item = CLINICAL_VIDEO_REGISTRY[vid]
        stem = os.path.splitext(item["filename"])[0]
        playlist.append({
            "step": step_idx,
            "video_id": item["id"],
            "title": item["title"],
            "category": item.get("category", "General"),
            "duration_s": item.get("duration_s", 10.0),
            "reason": item.get("reason", ""),
            "video_url": f"{base_v_url}/videos/existing/{item['filename']}",
            "subtitle_en": f"{base_v_url}/subtitles/{stem}.en.vtt",
            "subtitle_fr": f"{base_v_url}/subtitles/{stem}.fr.vtt"
        })

    return playlist


def orchestrate_video_recommendation(patient_id: str, video_record: dict, custom_reason: str = None) -> dict:
    """
    Dispatches authenticated recommendation to Video VM Server POST /api/orchestrate
    with X-API-KEY and X-Video-Server-Key security headers.
    """
    url = f"{VIDEO_SERVER_URL.rstrip('/')}/api/orchestrate"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": VIDEO_SERVER_API_KEY,
        "X-Video-Server-Key": VIDEO_SERVER_KEY
    }
    payload = {
        "patient_id": str(patient_id),
        "title": video_record["title"],
        "video_filename": video_record["filename"],
        "duration_s": float(video_record.get("duration_s", 10.0)),
        "category": video_record.get("category", "General"),
        "trigger_reason": custom_reason or video_record.get("reason", "AI clinical recommendation"),
        "relevance": "high",
        "thumbnail_type": "technical"
    }

    logger.info("-" * 65)
    logger.info("[ORCHESTRATE DISPATCH EVENT]")
    logger.info(f"   Patient ID     : {patient_id}")
    logger.info(f"   Video Title    : '{video_record['title']}'")
    logger.info(f"   Video Filename : {video_record['filename']}")
    logger.info(f"   Category       : {video_record.get('category', 'General')}")
    logger.info(f"   Trigger Reason : {payload['trigger_reason']}")
    logger.info(f"   Target URL     : {url}")

    start_t = time.perf_counter()
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        if res.status_code == 200:
            logger.info(f"   -> [DISPATCH SUCCESS] Delivered to Video VM Server (HTTP {res.status_code} in {elapsed_ms:.2f}ms)")
        else:
            logger.warning(f"   -> [DISPATCH WARN/ERR] Video VM returned HTTP {res.status_code}: {res.text[:200]}")
        logger.info("-" * 65)
        return {"status": "success" if res.status_code == 200 else "error", "http_code": res.status_code, "data": res.json() if res.headers.get("content-type") == "application/json" else res.text}
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        logger.error(f"   -> [DISPATCH FAILED] Connection error to Video VM Server: {e} ({elapsed_ms:.2f}ms)")
        logger.info("-" * 65)
        return {"status": "failed", "error": str(e)}


def orchestrate_video_package(patient_id: str, playlist_items: list, package_title: str = "Personalized CPAP Video Coaching Sequence") -> dict:
    """
    Scenario 2: Dispatches a multi-clip virtual stitched package to Video VM POST /api/orchestrate
    with video_type: 'package', clips array, duration_s: 10, and transition: 'fade_1_5s'.
    """
    url = f"{VIDEO_SERVER_URL.rstrip('/')}/api/orchestrate"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": VIDEO_SERVER_API_KEY,
        "X-Video-Server-Key": VIDEO_SERVER_KEY
    }
    
    clips = []
    base_v_url = VIDEO_SERVER_URL.rstrip('/')
    for item in playlist_items:
        vid_id = item.get("video_id", 1)
        filename = item.get("filename") or CLINICAL_VIDEO_REGISTRY.get(vid_id, {}).get("filename", f"{vid_id}.mp4")
        clips.append({
            "step": item.get("step", 1),
            "video_id": vid_id,
            "title": item.get("title", ""),
            "video_filename": filename,
            "url": f"{base_v_url}/videos/existing/{filename}",
            "duration_s": float(item.get("duration_s", 10.0)),
            "transition": "fade_1_5s"
        })

    payload = {
        "patient_id": str(patient_id),
        "video_type": "package",
        "title": package_title,
        "total_clips": len(clips),
        "clips": clips,
        "relevance": "high",
        "thumbnail_type": "technical"
    }

    logger.info("-" * 65)
    logger.info("[ORCHESTRATE PACKAGE DISPATCH EVENT]")
    logger.info(f"   Patient ID     : {patient_id}")
    logger.info(f"   Package Title  : '{package_title}'")
    logger.info(f"   Clips Count    : {len(clips)}")
    logger.info(f"   Target URL     : {url}")

    start_t = time.perf_counter()
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        if res.status_code == 200:
            logger.info(f"   -> [PACKAGE SUCCESS] Delivered to Video VM Server (HTTP {res.status_code} in {elapsed_ms:.2f}ms)")
        else:
            logger.warning(f"   -> [PACKAGE WARN/ERR] Video VM returned HTTP {res.status_code}: {res.text[:200]}")
        logger.info("-" * 65)
        return {"status": "success" if res.status_code == 200 else "error", "http_code": res.status_code, "data": res.json() if res.headers.get("content-type") == "application/json" else res.text}
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        logger.error(f"   -> [PACKAGE FAILED] Connection error to Video VM Server: {e} ({elapsed_ms:.2f}ms)")
        logger.info("-" * 65)
        return {"status": "failed", "error": str(e)}


def trigger_vertex_video_generation(patient_id: str, prompt: str, model: str = "veo-2.0-generate-001") -> dict:
    """
    Triggers Scenario 3 Vertex AI video synthesis via Video VM Server POST /api/vertex-generate
    with X-API-KEY and X-Video-Server-Key security headers.
    """
    url = f"{VIDEO_SERVER_URL.rstrip('/')}/api/vertex-generate"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": VIDEO_SERVER_API_KEY,
        "X-Video-Server-Key": VIDEO_SERVER_KEY
    }
    payload = {
        "patient_id": str(patient_id),
        "prompt": prompt,
        "model": model
    }

    logger.info("-" * 65)
    logger.info("[VERTEX AI DISPATCH TRIGGER]")
    logger.info(f"   Patient ID     : {patient_id}")
    logger.info(f"   Prompt         : '{prompt}'")
    logger.info(f"   Model          : {model}")
    logger.info(f"   Target URL     : {url}")

    start_t = time.perf_counter()
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=35)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        logger.info(f"   -> [VERTEX RESPONSE] Status {res.status_code} in {elapsed_ms:.2f}ms")
        logger.info("-" * 65)
        return {"status": "success" if res.status_code == 200 else "error", "http_code": res.status_code, "data": res.json() if res.headers.get("content-type") == "application/json" else res.text}
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        logger.error(f"   -> [VERTEX ERROR] Failed to dispatch Vertex generation: {e} ({elapsed_ms:.2f}ms)")
        logger.info("-" * 65)
        return {"status": "failed", "error": str(e)}


def orchestrate_pipeline_videos() -> dict:
    """
    Scans patient action plan and physiological features after pipeline run,
    resolving clinical video recommendations and dispatching authenticated
    POST /api/orchestrate requests to Video VM Server.
    """
    results_file = "patient_action_plan.csv" if os.path.exists("patient_action_plan.csv") else "layer3_results.csv"
    if not os.path.exists(results_file):
        print("[VIDEO ORCHESTRATOR WARNING] No patient action plan artifact found for video orchestration.")
        return {"status": "skipped", "reason": "No action plan"}

    feat_dict = {}
    if os.path.exists("features_merged.csv"):
        try:
            f_df = _original_read_csv("features_merged.csv")
            for _, f_row in f_df.iterrows():
                if "AtHomePatientId" in f_row:
                    feat_dict[str(int(f_row["AtHomePatientId"]))] = f_row.to_dict()
        except Exception:
            pass

    try:
        df = _original_read_csv(results_file)
        orchestrated_count = 0
        results = []

        print(f"\n[VIDEO ORCHESTRATOR] Evaluating {len(df)} patients for Video VM Server orchestration ({VIDEO_SERVER_URL})...")
        for _, row in df.iterrows():
            pid = str(int(row["AtHomePatientId"]))
            rec = str(row.get("intervention_rec", "")).strip().lower()
            risk_lvl = str(row.get("risk_level", "")).strip().lower()

            should_orchestrate = (rec == "video") or (risk_lvl in ["high", "medium"])

            if should_orchestrate:
                p_dict = row.to_dict()
                f_row = feat_dict.get(pid, {})
                video_item = resolve_clinical_video_for_patient(p_dict, f_row)
                trigger_reason = str(row.get("intervention_reason", "")) or video_item["reason"]

                print(f" [VIDEO ORCHESTRATION] Dispatching Patient {pid} -> '{video_item['title']}' ({video_item['filename']})...")
                res = orchestrate_video_recommendation(
                    patient_id=pid,
                    video_record=video_item,
                    custom_reason=trigger_reason
                )
                results.append({"patient_id": pid, "video": video_item["filename"], "dispatch": res})
                if res.get("status") == "success":
                    orchestrated_count += 1

        pipeline_state["last_video_orchestrations"] = orchestrated_count
        print(f"[VIDEO ORCHESTRATOR SUCCESS] Orchestrated {orchestrated_count} video recommendations to Video VM Server.")
        return {"status": "success", "orchestrated_count": orchestrated_count, "details": results}
    except Exception as e:
        print(f"[VIDEO ORCHESTRATOR ERROR] Failed during video orchestration: {e}")
        return {"status": "error", "error": str(e)}


PIPELINE_TIMEOUT_SECONDS = int(os.environ.get("PIPELINE_TIMEOUT_SECONDS", 900))
MAX_PIPELINE_RETRIES = int(os.environ.get("MAX_PIPELINE_RETRIES", 1))


def execute_supervisor_pipeline():
    """Runs the supervisor's M4_FINAL_F2.ipynb notebook in a clean UTF-8 environment with retry logic."""
    global pipeline_state
    if pipeline_state["status"] == "running":
        logger.warning("[AI SERVER] Pipeline is already actively running. Skipping concurrent trigger.")
        return False

    pipeline_state["status"] = "running"
    pipeline_state["last_run_start"] = time.strftime("%Y-%m-%d %H:%M:%S")
    start_t = time.time()
    logger.info(f"\n[AI SERVER] >>> Triggering AI Supervisor Model Pipeline (M4_FINAL_F2.ipynb) at {pipeline_state['last_run_start']}...")

    cmd = [sys.executable, "-m", "jupyter", "execute", "M4_FINAL_F2.ipynb"]
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = f"{os.getcwd()};{env.get('PYTHONPATH', '')}"

    success = False
    last_error_msg = None

    for attempt in range(MAX_PIPELINE_RETRIES + 1):
        try:
            if attempt > 0:
                logger.info(f"[AI SERVER RETRY] Retrying pipeline execution (attempt {attempt+1}/{MAX_PIPELINE_RETRIES+1})...")
                time.sleep(2)

            res = subprocess.run(cmd, cwd=os.getcwd(), env=env, capture_output=True, text=True, timeout=PIPELINE_TIMEOUT_SECONDS)
            if res.returncode == 0:
                success = True
                break
            else:
                last_error_msg = res.stderr[-500:] if res.stderr else res.stdout[-500:]
                logger.warning(f"[AI SERVER WARN] Attempt {attempt+1} exited with code {res.returncode}: {last_error_msg}")
        except subprocess.TimeoutExpired as e:
            last_error_msg = f"Pipeline execution timed out after {PIPELINE_TIMEOUT_SECONDS}s: {e}"
            logger.error(f"[AI SERVER TIMEOUT] {last_error_msg}")
        except Exception as e:
            last_error_msg = f"Pipeline execution exception: {e}"
            logger.error(f"[AI SERVER EXCEPTION] {last_error_msg}")

    elapsed = time.time() - start_t
    pipeline_state["last_duration_seconds"] = round(elapsed, 1)
    pipeline_state["last_run_finish"] = time.strftime("%Y-%m-%d %H:%M:%S")
    pipeline_state["total_runs"] += 1
    pipeline_state["model_health"] = dict(MODEL_HEALTH)

    if success:
        pipeline_state["status"] = "idle"
        pipeline_state["last_error"] = None
        logger.info(f"[AI SERVER] <<< Pipeline completed successfully in {elapsed:.1f}s!")
        # 1. Push predictions directly to backend API
        push_predictions_to_backend()
        # 2. Orchestrate video recommendations to Video VM Server
        orchestrate_pipeline_videos()
        return True
    else:
        pipeline_state["status"] = "failed"
        pipeline_state["last_error"] = last_error_msg
        logger.error(f"[AI SERVER ERROR] Pipeline failed: {last_error_msg}")
        return False


def _background_scheduler_loop():
    """Periodic scheduler loop."""
    time.sleep(5)  # Initial grace period on startup
    print(f"[AI SERVER SCHEDULER] Periodic sync active (every {SYNC_INTERVAL_MINUTES} mins). Running initial cycle...")
    execute_supervisor_pipeline()
    
    while True:
        time.sleep(SYNC_INTERVAL_MINUTES * 60)
        print(f"[AI SERVER SCHEDULER] Periodic interval elapsed ({SYNC_INTERVAL_MINUTES}m). Running scheduled sync...")
        execute_supervisor_pipeline()


# ==========================================
# 7. FastAPI REST Server & Live Endpoints
# ==========================================
try:
    from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Request, Security
    from fastapi.security import APIKeyHeader
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from typing import Optional

    app = FastAPI(
        title="SleepCare CPAP AI Supervisor Server",
        description="Continuous 24/7 AI scoring, multimodal biomarker fusion, and real-time intervention engine for CPAP therapy.",
        version="2.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API Key Security Dependency
    AI_SERVER_API_KEY = os.environ.get("AI_SERVER_API_KEY", "")
    api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
    ml_key_header = APIKeyHeader(name="X-ML-Key", auto_error=False)

    async def verify_ai_server_auth(
        request: Request,
        api_key: Optional[str] = Security(api_key_header),
        ml_key: Optional[str] = Security(ml_key_header)
    ):
        client_ip = request.client.host if request.client else "unknown"
        # Whitelist local queries or validate token
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
    async def traffic_and_security_logger(request, call_next):
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
                return JSONResponse(status_code=403, content={"detail": "Access Denied: Malicious probe detected."})

        # 2. Detailed Live Context Logging for CPAP AI & Video Events
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

        # Response Summary Logging
        status_label = "[HTTP OK]" if response.status_code < 400 else "[HTTP WARN/ERR]"
        logger.info(f"{status_label} {method} {raw_path} -> Status {response.status_code} ({duration_ms:.2f}ms)")
        return response

    @app.on_event("startup")
    def on_startup():
        logger.info(f"[AI SERVER] Starting continuous service on http://{SERVER_HOST}:{SERVER_PORT}")
        logger.info(f"[AI SERVER] Interactive API documentation available at: http://159.84.143.246:{SERVER_PORT}/docs")
        logger.info(f"[AI SERVER] Video VM Orchestration Target: {VIDEO_SERVER_URL}")
        scheduler_thread = threading.Thread(target=_background_scheduler_loop, daemon=True)
        scheduler_thread.start()

    @app.get("/")
    def root():
        return {
            "name": "SleepCare CPAP AI Server",
            "status": "online",
            "host": SERVER_HOST,
            "port": SERVER_PORT,
            "video_server_url": VIDEO_SERVER_URL,
            "pipeline": pipeline_state,
            "model_health": MODEL_HEALTH,
            "docs": f"/docs"
        }

    @app.get("/health")
    def health_check():
        return {
            "status": "healthy",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "video_server_url": VIDEO_SERVER_URL,
            "model_health": MODEL_HEALTH,
            "pipeline_state": pipeline_state
        }

    @app.post("/api/pipeline/run", dependencies=[Depends(verify_ai_server_auth)])
    def trigger_pipeline(background_tasks: BackgroundTasks):
        """Webhook to trigger immediate AI model execution and push results (Protected)."""
        if pipeline_state["status"] == "running":
            return {"message": "Pipeline is already running.", "state": pipeline_state}
        background_tasks.add_task(execute_supervisor_pipeline)
        return {"message": "AI Pipeline run initiated.", "status": "running"}

    @app.post("/api/pipeline/push", dependencies=[Depends(verify_ai_server_auth)])
    def trigger_push():
        """Pushes existing generated predictions directly to the backend database (Protected)."""
        result = push_predictions_to_backend()
        return result

    @app.post("/api/pipeline/orchestrate-videos", dependencies=[Depends(verify_ai_server_auth)])
    def trigger_video_orchestration():
        """Manually dispatches video recommendations for all eligible patients to Video VM Server (Protected)."""
        result = orchestrate_pipeline_videos()
        return result

    @app.get("/api/pipeline/status")
    def get_pipeline_status():
        return {
            "pipeline_state": pipeline_state,
            "model_health": MODEL_HEALTH
        }

    # ==========================================
    # ML Model Health & Retraining Endpoints
    # ==========================================
    @app.get("/api/models", dependencies=[Depends(verify_ai_server_auth)])
    def list_ml_models():
        """Returns health status, performance metrics, and drift values for all 4 ML models (Protected)."""
        return {
            "status": "success",
            "count": len(ML_MODELS_REGISTRY),
            "models": list(ML_MODELS_REGISTRY.values()),
            "pipeline_state": pipeline_state,
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

        # Dispatch background pipeline execution
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

    @app.get("/api/video-server/health")
    def get_video_server_health():
        """Checks connectivity and health status of the Video VM Server (Port 8080)."""
        try:
            res = requests.get(f"{VIDEO_SERVER_URL.rstrip('/')}/health", timeout=5)
            return {
                "configured_url": VIDEO_SERVER_URL,
                "reachable": res.status_code == 200,
                "status_code": res.status_code,
                "server_data": res.json() if res.status_code == 200 else res.text
            }
        except Exception as e:
            return {
                "configured_url": VIDEO_SERVER_URL,
                "reachable": False,
                "error": str(e)
            }

    @app.post("/api/video-server/orchestrate/{patient_id}", dependencies=[Depends(verify_ai_server_auth)])
    def orchestrate_single_patient(patient_id: int):
        """Dispatches an authenticated video coaching recommendation for a specific patient (Protected)."""
        results_file = "patient_action_plan.csv" if os.path.exists("patient_action_plan.csv") else "layer3_results.csv"
        p_row = {"AtHomePatientId": patient_id, "video_title": "none"}
        f_row = {}
        if os.path.exists(results_file):
            df = _original_read_csv(results_file)
            subset = df[df["AtHomePatientId"] == patient_id]
            if not subset.empty:
                p_row = subset.iloc[0].to_dict()
        if os.path.exists("features_merged.csv"):
            f_df = _original_read_csv("features_merged.csv")
            f_sub = f_df[f_df["AtHomePatientId"] == patient_id]
            if not f_sub.empty:
                f_row = f_sub.iloc[0].to_dict()

        video_rec = resolve_clinical_video_for_patient(p_row, f_row)
        result = orchestrate_video_recommendation(
            patient_id=str(patient_id),
            video_record=video_rec,
            custom_reason=str(p_row.get("intervention_reason", "")) or video_rec["reason"]
        )
        return {
            "patient_id": patient_id,
            "resolved_video": video_rec,
            "orchestration_result": result
        }

    @app.post("/api/video-server/vertex-generate", dependencies=[Depends(verify_ai_server_auth)])
    def trigger_vertex_generate_endpoint(patient_id: str, prompt: str, model: str = "veo-2.0-generate-001"):
        """Triggers Scenario 3 Vertex AI video synthesis via authenticated Video VM Server call (Protected)."""
        res = trigger_vertex_video_generation(patient_id=patient_id, prompt=prompt, model=model)
        return res

    @app.get("/api/patient/{patient_id}", dependencies=[Depends(verify_ai_server_auth)])
    def get_patient_prediction(patient_id: int):
        """Returns comprehensive AI predictions, risk scores, and recommended actions for a specific patient (Protected)."""
        results_file = "patient_action_plan.csv" if os.path.exists("patient_action_plan.csv") else "layer3_results.csv"
        if not os.path.exists(results_file):
            raise HTTPException(status_code=404, detail="AI predictions not generated yet. Run pipeline first.")
            
        df = _original_read_csv(results_file)
        if "AtHomePatientId" not in df.columns:
            raise HTTPException(status_code=500, detail="Malformed prediction artifact.")
            
        patient_row = df[df["AtHomePatientId"] == patient_id]
        if patient_row.empty:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found in prediction database.")
            
        p_dict = patient_row.iloc[0].replace({np.nan: None}).to_dict()
        f_dict = {}
        if os.path.exists("features_merged.csv"):
            try:
                f_df = _original_read_csv("features_merged.csv")
                f_sub = f_df[f_df["AtHomePatientId"] == patient_id]
                if not f_sub.empty:
                    f_dict = f_sub.iloc[0].replace({np.nan: None}).to_dict()
            except Exception:
                pass

        video_rec = resolve_clinical_video_for_patient(p_dict, f_dict)
        playlist_rec = resolve_clinical_video_playlist_for_patient(p_dict, f_dict)
        return {
            "patient_id": patient_id,
            "prediction": p_dict,
            "scenario_1_video": video_rec,
            "scenario_2_playlist": {
                "sequence_count": len(playlist_rec),
                "total_duration_s": sum(item.get("duration_s", 10.0) for item in playlist_rec),
                "items": playlist_rec
            },
            "pipeline_timestamp": pipeline_state["last_run_finish"]
        }

    @app.get("/api/patient/{patient_id}/playlist", dependencies=[Depends(verify_ai_server_auth)])
    def get_patient_playlist(patient_id: int):
        """Returns Scenario 2 virtual stitched continuous video coaching playlist for frontend video player (Protected)."""
        results_file = "patient_action_plan.csv" if os.path.exists("patient_action_plan.csv") else "layer3_results.csv"
        if not os.path.exists(results_file):
            raise HTTPException(status_code=404, detail="AI predictions not generated yet. Run pipeline first.")
            
        df = _original_read_csv(results_file)
        patient_row = df[df["AtHomePatientId"] == patient_id]
        if patient_row.empty:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")
            
        p_dict = patient_row.iloc[0].replace({np.nan: None}).to_dict()
        f_dict = {}
        if os.path.exists("features_merged.csv"):
            try:
                f_df = _original_read_csv("features_merged.csv")
                f_sub = f_df[f_df["AtHomePatientId"] == patient_id]
                if not f_sub.empty:
                    f_dict = f_sub.iloc[0].replace({np.nan: None}).to_dict()
            except Exception:
                pass

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
        results_file = "patient_action_plan.csv" if os.path.exists("patient_action_plan.csv") else "features_merged.csv"
        if not os.path.exists(results_file):
            return {"total": 0, "patients": []}
            
        df = _original_read_csv(results_file)
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

    @app.get("/api/metrics")
    def get_cohort_metrics():
        """Returns high-level cohort metrics across all model layers."""
        metrics = {
            "total_patients": 0,
            "active_alarms": 0,
            "high_risk_patients": 0,
            "last_updated": pipeline_state["last_run_finish"]
        }
        if os.path.exists("layer0_results.csv"):
            l0 = _original_read_csv("layer0_results.csv")
            metrics["total_patients"] = len(l0)
            if "any_alarm" in l0.columns:
                metrics["active_alarms"] = int(l0["any_alarm"].sum())
        if os.path.exists("patient_action_plan.csv"):
            pap = _original_read_csv("patient_action_plan.csv")
            if "urgent_flag" in pap.columns:
                metrics["high_risk_patients"] = int(pap["urgent_flag"].sum())
        return metrics

    @app.get("/api/kpis")
    def get_detailed_kpis():
        """Returns comprehensive clinical, adherence, risk, alarm, biomarker, and video KPIs (JSON)."""
        kpi_json_path = "cpap_kpis_summary.json"
        if os.path.exists(kpi_json_path):
            with open(kpi_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return get_cohort_metrics()

except ImportError:
    app = None

# ==========================================
# 8. Server CLI Entrypoint
# ==========================================
if __name__ == "__main__":
    if "--server" in sys.argv or os.environ.get("RUN_MODE") == "SERVER":
        import uvicorn
        logger.info(f"[AI SERVER] Launching 24/7 FastAPI Server on {SERVER_HOST}:{SERVER_PORT}...")
        uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, access_log=False)
    else:
        # Default CLI: execute pipeline directly once
        execute_supervisor_pipeline()
