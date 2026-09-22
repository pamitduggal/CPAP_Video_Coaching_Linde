"""
SleepCare AI Server - DataFrame Preprocessing & Schema Normalizer
=================================================================
This module standardizes raw clinical DataFrames whether loaded from the
backend REST API or read from local CSV files:
1. Normalizes column name casing (e.g. 'athomepatientid' -> 'AtHomePatientId').
2. Synthesizes required missing columns expected by ML models (e.g. Category in Intervention definitions).
3. Safely casts numerical telemetry columns to standard float/integer types.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

from core.config import EXPECTED_CASE, JOB_MAP, NUMERIC_COLS


def normalize_column_casing(df: pd.DataFrame, endpoint_name: str) -> pd.DataFrame:
    """
    Renames lowercase or mismatched column names to the exact casing expected
    by the M4 AI pipeline models.
    """
    case_map = dict(EXPECTED_CASE)

    # Special handling for execution date field:
    # Monitoring table expects 'ExecutionDate' (CamelCase),
    # while other biomarker tables use 'execution_date' (snake_case).
    if endpoint_name == "monitoring":
        case_map["executiondate"] = "ExecutionDate"
        case_map["execution_date"] = "ExecutionDate"
    else:
        case_map["executiondate"] = "execution_date"
        case_map["execution_date"] = "execution_date"

    new_cols = {col: case_map[col.lower()] for col in df.columns if col.lower() in case_map}
    if new_cols:
        df = df.rename(columns=new_cols)

    return df


def synthesize_missing_features(df: pd.DataFrame, endpoint_name: str) -> pd.DataFrame:
    """
    Fills in missing or null columns with standard clinical defaults so downstream
    feature engineering in the Jupyter notebook won't crash with KeyErrors.
    """
    # 1. CPAP Usage Table Defaults
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
            # Converts ISO dates like '2025-01-01' to integer timestamps like 20250101
            df["ReferenceDate"] = pd.to_numeric(
                df["ReferenceDate"].astype(str).str.replace("-", "").str.split(".").str[0],
                errors="coerce"
            ).fillna(0).astype(int)

    # 2. Interventions Table Defaults
    elif endpoint_name == "interventions":
        if "Status" not in df.columns:
            df["Status"] = "Done"

    # 3. Intervention Definition Table Defaults
    # Essential fix: Maps 73 JobTypeCodes to Category (Visit/Call/SMS) and Channel
    elif endpoint_name == "intervention-defs":
        if "Category" not in df.columns:
            if "JobTypeCode" in df.columns:
                df["Category"] = df["JobTypeCode"].map(JOB_MAP).fillna("Unknown")
            else:
                df["Category"] = "Unknown"
        if "Channel" not in df.columns:
            channel_mapping = {"Visit": "Visit", "Call": "Call", "Sms": "SMS", "SMS": "SMS"}
            df["Channel"] = df["Category"].map(channel_mapping).fillna(df["Category"])

    # 4. Questionnaires & Tele-monitoring Defaults
    elif endpoint_name == "monitoring":
        if "QuestionnaireId" not in df.columns:
            df["QuestionnaireId"] = 267
        if "QuestionId" not in df.columns:
            df["QuestionId"] = "2208"

    # 5. Patient Risk Factors Defaults
    elif endpoint_name == "risk-factors":
        if "CollectionDate" not in df.columns:
            df["CollectionDate"] = pd.Timestamp.now()
        if "RiskFactorId" in df.columns:
            df["RiskFactorId"] = pd.to_numeric(df["RiskFactorId"], errors="coerce")

    # 6. Withings Smartwatch Defaults
    elif endpoint_name == "withings-watch":
        if "sleep_efficiency" not in df.columns:
            df["sleep_efficiency"] = np.nan
        if "snoring_s" not in df.columns:
            df["snoring_s"] = np.nan

    # 7. Masimo Pulse Oximeter Defaults
    elif endpoint_name == "masimo":
        if "pleth_variability_index" not in df.columns:
            df["pleth_variability_index"] = np.nan

    # 8. SomnoArt Sleep EEG Wearable Defaults
    elif endpoint_name == "somnoart":
        for col in ["tst_min", "waso_min", "n3_duration_min", "nb_awakenings"]:
            if col not in df.columns:
                df[col] = np.nan
        if "analysis_status" not in df.columns:
            df["analysis_status"] = "Valid"

    return df


def cast_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Safely converts recognized numerical fields to numeric types (floats/ints),
    coercing strings or corrupted values to NaN.
    """
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _process_dataset(df: pd.DataFrame, endpoint_name: str) -> pd.DataFrame:
    """
    Master post-processing pipeline for any DataFrame:
    1. Check for empty data.
    2. Normalize column casing.
    3. Synthesize missing domain features.
    4. Cast numeric columns safely.
    """
    if df.empty:
        return df

    df = normalize_column_casing(df, endpoint_name)
    df = synthesize_missing_features(df, endpoint_name)
    df = cast_numeric_columns(df)
    return df
