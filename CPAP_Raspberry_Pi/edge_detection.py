"""
OSA-IVC — Edge detection (CPAP Telemetry + Biomarker Sensor Threshold Logic)
-----------------------------------------------------------------------------
Takes raw CPAP / Biomarker telemetry CSV bytes or dict records, reads the latest row,
and returns single or multi-event triggers mapped across all 37 video categories,
plus conditions no library clip covers (video_id None -> scenario 3 generation).

Covers:
- CPAP Telemetry: Use, Leaks95, AHI, Presure90
- Wearable Biomarkers: ScanWatch (SpO2, MicroArousals, ECG), BPM Core (BP, ECG, Stethoscope),
  RadG (SpO2, PR), ProShirt (Asynchrony, Fit), SomnoArt (REM, Efficiency),
  and sensor set-up / care for Hexoskin, MightySat, Somno-Art and CPAP co-usage (28-37).
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

# Wearable sensor set-up / care clips 28-37. Thresholds are the Video VM
# catalog's (GET /api/triggers/catalog), which the VM team named the single
# source of truth on 2026-09-16 after their emails disagreed with it — e.g.
# SIQ is < 30, not the < 60 the first email said.
HEXOSKIN_ECG_QUALITY_LOW = 40.0      # % — video 28
HEXOSKIN_HR_DROPOUT_HIGH = 30.0      # % — video 28 (>=)
HEXOSKIN_ASYNC_HIGH = 25.0           # % — video 29 (>)
MIGHTYSAT_PI_LOW = 0.5               # % — video 31
MIGHTYSAT_SPO2_CONFIDENCE_LOW = 50.0 # % — video 31
MIGHTYSAT_SIQ_LOW = 30.0             # % — video 33
SOMNOART_LENS_TRANSMISSION_LOW = 60.0  # % — video 36
CPAP_MASK_DISLODGE_MIN = 2           # events/night — video 37 (>=)

# How each clip's two catalog conditions combine — the catalog's
# condition_logic field, confirmed by the VM team 2026-09-18.
WEARABLE_LOGIC = {28: "OR", 29: "AND", 30: "OR", 31: "OR", 32: "OR",
                  33: "AND", 34: "OR", 35: "OR", 36: "OR", 37: "AND"}


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


def _field(row, name):
    """The raw value of a catalog metric, under its catalog spelling
    (Hexoskin_ECG_Quality) or the lower snake_case the phone exports use
    (hexoskin_ecg_quality). None when neither column is populated."""
    for key in (name, name.lower()):
        v = row.get(key, None)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        if str(v).strip().lower() in ("", "nan"):
            continue
        return v
    return None


def _pct(row, name):
    """A catalog percentage as a float: accepts 35, 35.0 or "35%".
    None when absent or unparseable, so a missing sensor never fires a rule."""
    v = _field(row, name)
    if v is None:
        return None
    try:
        return float(str(v).strip().rstrip("%"))
    except ValueError:
        return None


def _is(row, name, *expected):
    """Case-insensitive match of a catalog categorical (High, Poor,
    Disconnected, ...) against the expected value(s)."""
    v = _field(row, name)
    return v is not None and str(v).strip().lower() in {e.lower() for e in expected}


def _flag(row, name):
    """A catalog boolean: True / False, or None when not reported."""
    if _field(row, name) is None:
        return None
    return _bool_flag(row, name, name.lower())


def _combine(video_id, first, second):
    """Applies WEARABLE_LOGIC[video_id] to a clip's two condition results."""
    if WEARABLE_LOGIC[video_id] == "AND":
        return bool(first and second)
    return bool(first or second)


def detect_events_from_df(row: pd.Series) -> list[dict]:
    """
    Evaluates a single telemetry row against all 37 clinical trigger conditions.
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

    def add_uncovered(trigger_type, severity, metrics_dict):
        """A detected condition the 27-clip library has no coaching video for.

        video_id is deliberately None: load_library.clip_for() then finds no
        clip, the event lands in `uncovered`, and select_video() routes it to
        SCENARIO 3 (generate a clip) instead of reusing one that does not fit.
        Every other rule here hardcodes an id 1-27, which is exactly why
        scenario 3 was unreachable before this existed.
        """
        add_evt(None, trigger_type, severity, metrics_dict)

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
    elif scanwatch_spo2 < 90.0:
        # Low nighttime oxygen while the patient IS wearing the device a full
        # night. Video 16 is the library's only answer to low SpO2 and it is
        # adherence coaching ("wear it longer") — advice this patient has
        # already followed, so no clip in the library fits. Until this rule
        # existed the case fell through every branch and produced NO event at
        # all: a hypoxaemic adherent night looked identical to a quiet one.
        # SCENARIO 3 territory — the coaching has to be generated.
        # NOTE: threshold and clinical wording need sign-off before clinical use.
        add_uncovered("nocturnal_hypoxemia_despite_adherence", "high",
                      {"scanwatch_spo2": scanwatch_spo2, "use": use})

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

    # --- 7. WEARABLE SENSOR SET-UP & CARE (clips 28-37) ---
    # Metric names and thresholds are the Video VM catalog's, verbatim. How
    # each pair of conditions combines is WEARABLE_LOGIC (the catalog's
    # condition_logic); sync_catalog.py --check flags any drift from it.
    # Every reader returns None when the column is absent, so a row from a
    # patient without that device fires nothing.
    #
    # Severities follow the VM's priority ladder (2026-09-18), on this file's
    # scale. 37 sits in the ladder's top tier WITH mask-leak clips 1/2, which
    # are "medium" here, so 37 is "medium" too — "high" would make it lead
    # clip 1, the reverse of the VM's own example (1 then 37). It is evaluated
    # FIRST in this section so that, on a severity tie, it still plays before
    # the tier-2 clips 30/31/35 (sort order is stable).

    # 37 CPAP tubing tangled with a wearable: the patient pulls the mask off
    # with the arm wearing the sensor. Costs CPAP therapy, not just data.
    dislodge = _pct(row, "CPAP_Mask_Dislodge_Events")
    if _combine(37, dislodge is not None and dislodge >= CPAP_MASK_DISLODGE_MIN,
                _is(row, "Wearable_Motion_Spikes", "High")):
        add_evt(37, "cpap_wearable_tubing_entanglement", "medium",
                {"cpap_mask_dislodge_events": dislodge,
                 "wearable_motion_spikes": _field(row, "Wearable_Motion_Spikes")})

    # 28 Hexoskin: dry electrodes -> noisy ECG / heart-rate dropouts.
    ecg_q = _pct(row, "Hexoskin_ECG_Quality")
    dropout = _pct(row, "HR_Dropout_Rate")
    if _combine(28, ecg_q is not None and ecg_q < HEXOSKIN_ECG_QUALITY_LOW,
                dropout is not None and dropout >= HEXOSKIN_HR_DROPOUT_HIGH):
        add_evt(28, "hexoskin_ecg_impedance", "low",
                {"hexoskin_ecg_quality": ecg_q, "hr_dropout_rate": dropout})

    # 29 Hexoskin: loose / twisted RIP bands.
    async_pct = _pct(row, "Hexoskin_Thorax_Abdomen_Async")
    if _combine(29, async_pct is not None and async_pct > HEXOSKIN_ASYNC_HIGH,
                _is(row, "Breathing_Signal_Noise", "High")):
        add_evt(29, "hexoskin_rip_displacement", "low",
                {"hexoskin_thorax_abdomen_async": async_pct,
                 "breathing_signal_noise": _field(row, "Breathing_Signal_Noise")})

    # 30 Hexoskin: recorder unseated or not recording -> no data at all.
    recording = _flag(row, "Recording_Active")
    if _combine(30, _is(row, "Hexoskin_Device_Status", "Disconnected"),
                recording is False):
        add_evt(30, "hexoskin_recording_inactive", "medium",
                {"hexoskin_device_status": _field(row, "Hexoskin_Device_Status"),
                 "recording_active": recording})

    # 31 MightySat: low perfusion (cold fingers).
    pi = _pct(row, "MightySat_PI")
    conf = _pct(row, "SpO2_Confidence")
    if _combine(31, pi is not None and pi < MIGHTYSAT_PI_LOW,
                conf is not None and conf < MIGHTYSAT_SPO2_CONFIDENCE_LOW):
        add_evt(31, "mightysat_low_pi", "medium",
                {"mightysat_pi": pi, "spo2_confidence": conf})

    # 32 MightySat: finger depth / nail polish blocking the optics.
    if _combine(32, _is(row, "MightySat_SpO2_Error", "Optical_Blockage"),
                _is(row, "Pulse_Waveform", "Erratic")):
        add_evt(32, "mightysat_optical_blockage", "low",
                {"mightysat_spo2_error": _field(row, "MightySat_SpO2_Error"),
                 "pulse_waveform": _field(row, "Pulse_Waveform")})

    # 33 MightySat: ambient light swamping the sensor.
    siq = _pct(row, "MightySat_SIQ")
    if _combine(33, siq is not None and siq < MIGHTYSAT_SIQ_LOW,
                _is(row, "Ambient_Light_Interference", "High")):
        add_evt(33, "mightysat_low_siq", "low",
                {"mightysat_siq": siq,
                 "ambient_light_interference": _field(row, "Ambient_Light_Interference")})

    # 34 Somno-Art: armband slipped, PPG lost contact.
    if _combine(34, _is(row, "SomnoArt_PPG_Contact", "Poor"),
                _is(row, "Optical_Baseline_Drift", "High")):
        add_evt(34, "somnoart_ppg_contact_loss", "low",
                {"somnoart_ppg_contact": _field(row, "SomnoArt_PPG_Contact"),
                 "optical_baseline_drift": _field(row, "Optical_Baseline_Drift")})

    # 35 Somno-Art: calibration failed / patient moved during the 60s baseline.
    motion = _flag(row, "Motion_During_Calibration")
    if _combine(35, _is(row, "SomnoArt_Calibration_Status", "Failed_Orange_LED"),
                motion is True):
        add_evt(35, "somnoart_calibration_failed", "medium",
                {"somnoart_calibration_status": _field(row, "SomnoArt_Calibration_Status"),
                 "motion_during_calibration": motion})

    # 36 Somno-Art: fogged lens, or the weekly sleeve wash is due.
    lens = _pct(row, "SomnoArt_Lens_Transmission")
    maint = _flag(row, "Maintenance_Due")
    if _combine(36, lens is not None and lens < SOMNOART_LENS_TRANSMISSION_LOW,
                maint is True):
        add_evt(36, "somnoart_optical_lens_fogging", "routine",
                {"somnoart_lens_transmission": lens, "maintenance_due": maint})

    # Hexoskin clips replace the generic ProShirt ones (VM rule, 2026-09-18):
    # never 28 with 25, nor 29 with 24, on the same night.
    fired = {e["video_id"] for e in events}
    suppressed = {25} if 28 in fired else set()
    suppressed |= {24} if 29 in fired else set()
    events[:] = [e for e in events if e["video_id"] not in suppressed]

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
