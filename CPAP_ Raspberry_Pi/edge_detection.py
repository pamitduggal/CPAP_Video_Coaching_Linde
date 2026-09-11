"""
OSA-IVC — Edge detection (CPAP Telemetry + Biomarker Sensor Threshold Logic)
-----------------------------------------------------------------------------
Takes raw CPAP / Biomarker telemetry CSV bytes or dict records, reads the latest row,
and returns single or multi-event triggers mapped across all 27 video categories.

Covers:
- CPAP Telemetry: Use, Leaks95, AHI, Presure90
- Wearable Biomarkers: ScanWatch (SpO2, MicroArousals, ECG), BPM Core (BP, ECG, Stethoscope),
  RadG (SpO2, PR), ProShirt (Asynchrony, Fit), SomnoArt (REM, Efficiency).
"""

import io
import pandas as pd

# --- Threshold Constants ---
LEAK_CRITICAL = 40.0
LEAK_SEVERE = 30.0
LEAK_MODERATE = 24.0
LEAK_MILD = 10.0

AHI_CRITICAL = 30.0
AHI_ELEVATED = 15.0
AHI_MILD = 5.0

USAGE_FULL = 4.0
USAGE_LOW = 3.0

PRESSURE_HIGH = 13.0
PRESSURE_MODERATE = 12.0
PRESSURE_ELEVATED = 10.0

# minute_ventilation (L/min) is a surrogate for asynchrony — no direct
# metric exists in the Hexoskin export. Normal resting range is ~5-8 L/min;
# this is a placeholder for "elevated," on minute_ventilation's real scale
# (the old threshold of 30.0 was calibrated for a 0-100 asynchrony score,
# an entirely different metric — needs clinical validation either way).
PROSHIRT_ASYNCHRONY_HIGH = 20.0


def _num(row, key, default=0.0):
    """Safe float read: missing / blank / NaN -> default"""
    try:
        v = float(row.get(key, default))
        return default if pd.isna(v) else v
    except (TypeError, ValueError):
        return default


def _num_or_none(row, key):
    """Float read that distinguishes 'not populated' from a real 0.0 —
    needed to tell which vendor/device a row's data actually came from."""
    v = row.get(key, None)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _bool_flag(row, *keys, default=False):
    """Robust boolean read across possible column names. Handles numbers,
    "True"/"False" strings, and NaN/blank correctly — a plain
    `str(value) not in [...]` string check breaks the moment pandas infers a
    mostly-blank numeric column as float64: "0" becomes 0.0, and str(0.0) is
    "0.0", which never matches "0" -> a false positive."""
    for key in keys:
        v = row.get(key, None)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        s = str(v).strip().lower()
        if s in ("", "nan"):
            continue
        return s not in ("0", "false")
    return default


def detect_events_from_df(row: pd.Series) -> list[dict]:
    """
    Evaluates a single telemetry row against all 27 clinical trigger conditions.
    Supports exact column names from DISP / Linde HomeCare datasets:
    Usage3.csv, db_withings_watch_connected.csv, db_withings_bpm_core_connected.csv,
    db_masimo_connected.csv, db_hexoskin_connected.csv, db_somnoart_connected.csv.
    """
    patient_id = str(row.get("AtHomePatientId", row.get("patient_id", "P001")))

    # CPAP Metrics (Usage3.csv)
    use = _num(row, "Use", _num(row, "usage_hours", 0.0))
    ahi = _num(row, "AHI", _num(row, "ahi", 0.0))
    pressure = _num(row, "Presure90", _num(row, "pressure", 0.0))

    # Vendor-split leak reporting: ResMed/Lowenstein report Leaks95 (95th
    # percentile, L/min); Philips/SEFAM instead report leaks0 (average leak,
    # same L/min scale) and leave Leaks95 blank. Falling back to leaks0
    # closes the gap where a Philips/SEFAM leak previously always read as
    # 0.0 and fell through to "no issue found".
    leak = _num_or_none(row, "Leaks95")
    if leak is None:
        leak = _num_or_none(row, "leaks95")
    if leak is None:
        leak = _num_or_none(row, "leaks0")
    if leak is None:
        leak = 0.0

    # ScanWatch Metrics (db_withings_watch_connected.csv). "spo2"/"afib_result"
    # are the real column names in the ScanWatch export, but BPM Core and
    # RadG's own exports use the SAME bare names — if a merged row ever
    # combines multiple devices, per-device-prefixed columns (checked first
    # below) are needed to tell them apart; the bare name is only a fallback
    # for single-device rows, where there's no ambiguity to resolve.
    scanwatch_spo2 = _num(row, "scanwatch_spo2", _num(row, "spo2", _num(row, "ScanWatch_SpO2", 98.0)))
    scanwatch_arousals = _num(row, "wakeup_count", _num(row, "ScanWatch_MicroArousals", 0.0))
    scanwatch_ecg_anomaly = _bool_flag(row, "scanwatch_afib_result", "afib_result", "ScanWatch_ECG_Anomaly")

    # BPM Core Metrics (db_withings_bpm_core_connected.csv)
    bpm_systolic = _num(row, "systolic_bp", _num(row, "BPMCore_Systolic", 120.0))
    bpm_ecg_afib = _bool_flag(row, "bpm_afib_result", "afib_result", "BPMCore_ECG_Status")
    bpm_stethoscope = str(row.get("comment", row.get("BPMCore_Stethoscope", ""))).lower() == "review_required"

    # Masimo RadG Metrics (db_masimo_connected.csv)
    radg_spo2 = _num(row, "radg_spo2", _num(row, "spo2", _num(row, "RadG_SpO2", 98.0)))
    radg_pr_var = _num(row, "pleth_variability_index", 0.0) >= 15.0 or str(row.get("RadG_PR_Variability", "")).lower() == "high"

    # Hexoskin ProShirt Metrics (db_hexoskin_connected.csv) — minute_ventilation
    # is a surrogate for a true asynchrony score (no direct metric exists in
    # this export); PROSHIRT_ASYNCHRONY_HIGH below is a placeholder tuned to
    # minute_ventilation's actual L/min scale, not the old 0-100 score scale.
    proshirt_asynchrony = _num(row, "minute_ventilation", 0.0)
    proshirt_signal = _num(row, "ecg_quality_flag", 100.0)

    # SomnoArt Metrics (db_somnoart_connected.csv) — prefer rem_pct (a real
    # column in this export, same percentage scale the 12.0 threshold below
    # was calibrated for); rem_duration_min is minutes, a different scale,
    # and is only a last-resort fallback if no percentage field exists.
    somnoart_rem = _num(row, "rem_pct", _num(row, "SomnoArt_REM_Pct", None))
    if somnoart_rem is None:
        somnoart_rem = _num(row, "rem_duration_min", 20.0)
    somnoart_efficiency = _num(row, "sleep_efficiency_pct", _num(row, "SomnoArt_SleepEfficiency", 85.0))

    events = []

    # Helper to add event
    def add_evt(vid_id, trigger_type, severity, metrics_dict):
        events.append({
            "video_id": vid_id,
            "trigger_type": trigger_type,
            "severity": severity,
            "patient_id": patient_id,
            "metrics": metrics_dict
        })

    # --- 1. CRITICAL CLINICAL ALERTS ---
    if ahi >= AHI_CRITICAL:
        add_evt(15, "severe_apnea", "critical", {"ahi": ahi})
    elif ahi >= AHI_ELEVATED and use < USAGE_LOW:
        add_evt(13, "biomarker_changes", "critical", {"ahi": ahi, "use": use})
    elif ahi >= AHI_ELEVATED:
        add_evt(12, "high_breathing_events", "high", {"ahi": ahi})

    # --- 2. MASK & EQUIPMENT LEAKS ---
    if leak >= LEAK_CRITICAL:
        add_evt(14, "mask_style_change", "high", {"leak": leak})
    elif leak >= LEAK_SEVERE:
        if use >= 2.0:
            add_evt(2, "refit_mask_lying_down", "medium", {"leak": leak, "use": use})
        else:
            add_evt(8, "mouth_breathing_chin_support", "high", {"leak": leak, "use": use})
    elif leak >= LEAK_MODERATE:
        add_evt(1, "adjust_mask_straps", "medium", {"leak": leak})

    # --- 3. LOW USAGE & ADHERENCE ---
    if 0 < use < USAGE_FULL:
        if pressure >= PRESSURE_MODERATE:
            add_evt(4, "low_usage_ramp_mode", "medium", {"use": use, "pressure": pressure})
        else:
            add_evt(6, "early_mask_removal", "medium", {"use": use})
    elif use == 0.0:
        add_evt(5, "low_usage_daytime_practice", "high", {"use": use})

    # --- 4. AEROPHAGIA (AIR SWALLOWING) ---
    if pressure >= PRESSURE_HIGH and leak < LEAK_MILD:
        if ahi >= AHI_MILD:
            add_evt(11, "aerophagia_side_sleeping", "medium", {"pressure": pressure, "ahi": ahi})
        else:
            add_evt(10, "aerophagia_elevate_head", "medium", {"pressure": pressure})

    # --- 5. COMFORT & MAINTENANCE ---
    if LEAK_MILD <= leak < LEAK_MODERATE:
        if pressure >= PRESSURE_ELEVATED:
            add_evt(7, "dry_mouth_humidifier", "low", {"leak": leak, "pressure": pressure})
        else:
            add_evt(9, "nasal_congestion_relief", "low", {"leak": leak, "pressure": pressure})

    if use >= USAGE_FULL and leak < LEAK_MILD and ahi < AHI_MILD and len(events) == 0:
        add_evt(3, "cushion_cleaning", "routine", {"use": use, "leak": leak, "ahi": ahi})

    # --- 6. WEARABLE BIOMARKERS ---
    if scanwatch_spo2 < 90.0 and use < USAGE_FULL:
        add_evt(16, "scanwatch_low_oxygen", "high", {"scanwatch_spo2": scanwatch_spo2, "use": use})

    if scanwatch_arousals >= 15.0:
        add_evt(17, "scanwatch_fragmented_sleep", "medium", {"scanwatch_arousals": scanwatch_arousals})

    if scanwatch_ecg_anomaly:
        add_evt(18, "scanwatch_heart_rhythm_signal", "high", {"scanwatch_ecg_anomaly": True})

    if bpm_systolic >= 140.0:
        add_evt(19, "bpm_core_high_bp", "high", {"bpm_systolic": bpm_systolic})

    if bpm_ecg_afib:
        add_evt(20, "bpm_core_irregular_ecg", "critical", {"bpm_ecg_afib": True})

    if bpm_stethoscope:
        add_evt(21, "bpm_core_stethoscope_review", "medium", {"bpm_stethoscope": True})

    if radg_spo2 < 88.0:
        add_evt(22, "radg_low_oxygen", "critical", {"radg_spo2": radg_spo2})

    if radg_pr_var:
        add_evt(23, "radg_pulse_instability", "high", {"radg_pr_var": True})

    if proshirt_asynchrony > PROSHIRT_ASYNCHRONY_HIGH:
        add_evt(24, "proshirt_breathing_pattern", "medium", {"proshirt_asynchrony": proshirt_asynchrony})

    if proshirt_signal < 70.0:
        add_evt(25, "proshirt_fit_check", "low", {"proshirt_signal": proshirt_signal})

    if somnoart_rem < 12.0:
        add_evt(26, "somnoart_sleep_architecture", "medium", {"somnoart_rem": somnoart_rem})

    if somnoart_efficiency < 75.0:
        add_evt(27, "somnoart_poor_continuity", "medium", {"somnoart_efficiency": somnoart_efficiency})

    return events


# Date columns to resolve "most recent" against, best first. reference_date
# is the night the reading describes; created_at is only the moment the file
# was exported (identical on every row), so it's a weak last resort.
DATE_COLUMNS = ("reference_date", "created_at", "date")


def latest_row(df: pd.DataFrame) -> pd.Series:
    """The row for the most recent night — the one that caused the event.

    Exports have so far always arrived sorted oldest-first, which made a
    positional df.iloc[-1] correct by luck rather than by construction.
    Resolving the max of the actual date column instead means an export
    that ever arrives unsorted still gets analysed on its newest night
    rather than on whatever row happened to land last in the file.
    Ties keep the last occurrence, matching the previous behaviour.
    """
    df = df.reset_index(drop=True)
    for col in DATE_COLUMNS:
        if col not in df.columns:
            continue
        dates = pd.to_datetime(df[col], errors="coerce", utc=True, format="mixed")
        if not dates.notna().any():
            continue
        newest = dates.max()
        if (dates == newest).sum() == len(df):
            break  # column is constant (e.g. export timestamp) — no signal
        return df.iloc[int(dates[dates == newest].index[-1])]
    return df.iloc[-1]


def detect_event(csv_bytes: bytes) -> dict | None:
    """
    Main ingestion point for CSV bytes. Returns primary event dict or multi-event payload.
    """
    df = pd.read_csv(io.BytesIO(csv_bytes))
    if df.empty:
        return None

    events = detect_events_from_df(latest_row(df))
    
    if not events:
        return None
        
    # Return highest severity event as primary, with all events attached.
    # primary must be a COPY of events[0], not the same object — otherwise
    # primary["all_events"][0] IS primary itself, a circular reference that
    # crashes json.dumps() (used for logging/HTTP responses) every time.
    events.sort(key=lambda e: {"critical": 4, "high": 3, "medium": 2, "low": 1, "routine": 0}.get(e["severity"], 0), reverse=True)

    primary = dict(events[0])
    primary["all_events"] = events
    return primary
