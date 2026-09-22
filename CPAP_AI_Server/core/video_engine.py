"""
SleepCare AI Server - Multi-Scenario Clinical Video Coaching Engine
===================================================================
This module implements the 3 video coaching scenarios:
- SCENARIO 1: Single curated clinical MP4 selection (from 39 library videos: 37 curated + 2 AI-generated) dispatched to Video VM.
- SCENARIO 2: Multi-clip virtual stitched playlist with bilingual WebVTT subtitles (EN/FR).
- SCENARIO 3: Generative AI video synthesis via Google Vertex AI / Veo 3.1.
- Direct Dashboard assignment and batch pipeline orchestration.
"""

import os
import time
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Set, Tuple
import requests
import pandas as pd

from core.config import (
    API_BASE,
    VIDEO_SERVER_URL,
    VIDEO_SERVER_API_KEY,
    VIDEO_SERVER_KEY
)
from core.registry import (
    CLINICAL_VIDEO_REGISTRY,
    pipeline_state,
    state_lock,
    sync_video_catalog_from_vm,
    get_dynamic_catalog_state,
    update_catalog_from_payload
)
from core.interceptor import find_artifact_file, _original_read_csv

logger = logging.getLogger("CPAP_AI_Server")


# ==============================================================================
# 1. Unified Telemetry Feature Extractor
# ==============================================================================
def extract_telemetry_features(
    patient_plan_row: Optional[Dict[str, Any]] = None,
    feature_row: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Extracts key physiological telemetry signals from merged feature tables
    with safe clinical default fallbacks.
    """
    plan = patient_plan_row or {}
    feats = feature_row or {}

    def _val(keys: List[str], default: Any) -> Any:
        lower_feats = {str(k).lower(): v for k, v in feats.items()}
        lower_plan = {str(k).lower(): v for k, v in plan.items()}
        for k in keys:
            lk = str(k).lower()
            if lk in lower_feats and lower_feats[lk] is not None and pd.notna(lower_feats[lk]):
                return lower_feats[lk]
            if lk in lower_plan and lower_plan[lk] is not None and pd.notna(lower_plan[lk]):
                return lower_plan[lk]
        return default

    # Average nightly usage over 7 days (standard therapeutic target is >= 4.0 hours)
    use_val = float(_val(["use_mean_7d", "use_mean", "use", "usage_hours", "use_val"], 5.0))

    # Residual Apnea-Hypopnea Index (AHI events per hour)
    ahi_val = float(_val(["ahi_mean_7d", "ahi_mean", "ahi", "ahi_val"], 2.0))

    # 95th Percentile Mask Leak rate (L/min)
    leak_val = float(_val(["leaks95_mean_7d", "leaks_worst_7d", "leak_rate", "leaks95", "leak_val"], 0.0))

    # 90th percentile delivered CPAP pressure (cmH2O)
    press_val = float(_val(["pressure_mean", "pressure", "presure90", "press_val"], 10.0))

    # Oxygen saturation SpO2 from Withings ScanWatch (%)
    spo2_ww = float(_val(["spo2_ww_7d"], 95.0))

    # Oxygen saturation SpO2 from Masimo medical pulse oximeter (%)
    spo2_mas = float(_val(["spo2_masimo_7d"], 95.0))

    # Systolic blood pressure from Withings BPM Core (mmHg)
    sys_bp = float(_val(["systolic_bp_7d"], 120.0))

    # Atrial Fibrillation flag detected by BPM Core ECG
    afib_val = bool(_val(["afib_detected"], False))

    # Sleep efficiency percentage from SomnoArt EEG wearable (%)
    sleep_eff = float(_val(["sleep_efficiency_7d"], 85.0))

    # Wearable Device Alerts & Signal Quality Triggers (Videos 28-37)
    pi_val = float(_val(["perfusion_index", "pi_mean_7d", "pi_val"], 2.0))
    siq_val = float(_val(["signal_iq", "siq_mean_7d", "siq_val"], 100.0))

    hexo_ecg_alert = bool(_val(["hexoskin_ecg_alert", "hexo_ecg_alert", "electrode_alert"], False))
    hexo_motion = bool(_val(["hexoskin_motion_alert", "hexo_motion", "respiratory_motion_alert"], False))
    hexo_docking_alert = bool(_val(["hexoskin_docking_alert", "hexo_docking_alert", "docking_alert"], False))

    masimo_sensor_alert = bool(_val(["masimo_sensor_alert", "optical_misplacement", "sensor_misplacement_alert"], False))

    somnoart_ppg_alert = bool(_val(["somnoart_ppg_alert", "ppg_dropout", "somno_ppg_alert"], False))
    somnoart_calib_alert = bool(_val(["somnoart_calib_alert", "calibration_error", "somno_calib_alert"], False))
    somnoart_hygiene_alert = bool(_val(["somnoart_hygiene_alert", "sensor_impedance_alert", "somno_hygiene_alert"], False))

    co_usage_cable_alert = bool(_val(["cable_clearance_alert", "co_usage_cable_alert", "cable_entanglement_alert"], False))
    n_devices = int(_val(["n_devices", "active_device_count"], 0))

    # Extended Biomarker Telemetry Signals & Specific Conditions (Videos 28-37)
    hexoskin_ecg_quality = float(_val(["ecg_quality", "hexoskin_ecg_quality"], 100.0))
    hr_dropout_rate = float(_val(["hr_dropout", "hr_dropout_rate"], 0.0))
    thoracic_belt_shift = bool(_val(["thoracic_belt_shift", "belt_shift"], False))
    rip_artifact = float(_val(["rip_artifact", "thoracic_motion_artifact", "motion_artifact_rate"], 0.0))
    thoracic_motion_artifact = float(_val(["thoracic_motion_artifact", "rip_artifact", "motion_artifact_rate"], 0.0))
    rip_signal_loss = bool(_val(["rip_signal_loss", "rip_loss"], False))
    docking_failure = bool(_val(["docking_failure"], False))
    sync_led_unconfirmed = bool(_val(["sync_led_unconfirmed"], False))
    hexoskin_dock_status = _val(["hexoskin_dock_status", "dock_status"], True)
    battery_sync_fail = bool(_val(["battery_sync_fail", "sync_fail", "sync_led_unconfirmed"], False))
    cold_periphery_flag = bool(_val(["cold_periphery_flag", "cold_periphery"], False))
    finger_depth_misaligned = bool(_val(["finger_depth_misaligned"], False))
    nail_obstruction = bool(_val(["nail_obstruction"], False))
    optical_misalignment = bool(_val(["optical_misalignment", "optical_misplacement", "masimo_sensor_alert", "finger_depth_misaligned"], False))
    nail_polish_block = bool(_val(["nail_polish_block", "nail_polish", "nail_obstruction"], False))
    ambient_light_spike = bool(_val(["ambient_light_spike", "light_spike"], False))
    ppg_seal_loss = bool(_val(["ppg_seal_loss"], False))
    ppg_seal_quality = float(_val(["ppg_seal_quality", "somnoart_ppg_quality"], 100.0))
    optical_dropout = bool(_val(["optical_dropout", "ppg_dropout", "somnoart_ppg_alert", "ppg_seal_loss"], False))
    calibration_movement_detected = bool(_val(["calibration_movement_detected"], False))
    calibration_motion_detected = bool(_val(["calibration_motion_detected", "calibration_movement_detected", "calibration_error", "somnoart_calib_alert"], False))
    sensor_impedance_high = bool(_val(["sensor_impedance_high"], False))
    weekly_wash_reminder = bool(_val(["weekly_wash_reminder"], False))
    impedance_buildup = bool(_val(["impedance_buildup", "sensor_impedance_high", "sensor_impedance_alert", "somnoart_hygiene_alert"], False))
    cpap_tube_and_wearable_conflict = bool(_val(["cpap_tube_and_wearable_conflict"], False))
    concurrent_cpap_and_wearable_artifact = bool(_val(["concurrent_cpap_and_wearable_artifact", "cpap_tube_and_wearable_conflict", "cable_clearance_alert", "co_usage_cable_alert"], False))

    reason_str = (
        str(plan.get("intervention_reason", "")) + " " +
        str(plan.get("trigger_reason", "")) + " " +
        str(feats.get("intervention_reason", "")) + " " +
        str(feats.get("trigger_reason", ""))
    ).strip().lower()

    return {
        "video_title": str(plan.get("video_title", "")).strip().lower(),
        "reason_str": reason_str,
        "use_val": use_val,
        "ahi_val": ahi_val,
        "leak_val": leak_val,
        "press_val": press_val,
        "spo2_ww": spo2_ww,
        "spo2_mas": spo2_mas,
        "sys_bp": sys_bp,
        "afib_val": afib_val,
        "sleep_eff": sleep_eff,
        "pi_val": pi_val,
        "siq_val": siq_val,
        "hexo_ecg_alert": hexo_ecg_alert,
        "hexo_motion": hexo_motion,
        "hexo_docking_alert": hexo_docking_alert,
        "masimo_sensor_alert": masimo_sensor_alert,
        "somnoart_ppg_alert": somnoart_ppg_alert,
        "somnoart_calib_alert": somnoart_calib_alert,
        "somnoart_hygiene_alert": somnoart_hygiene_alert,
        "co_usage_cable_alert": co_usage_cable_alert,
        "n_devices": n_devices,
        "hexoskin_ecg_quality": hexoskin_ecg_quality,
        "hr_dropout_rate": hr_dropout_rate,
        "thoracic_belt_shift": thoracic_belt_shift,
        "rip_artifact": rip_artifact,
        "thoracic_motion_artifact": thoracic_motion_artifact,
        "rip_signal_loss": rip_signal_loss,
        "docking_failure": docking_failure,
        "sync_led_unconfirmed": sync_led_unconfirmed,
        "hexoskin_dock_status": hexoskin_dock_status,
        "battery_sync_fail": battery_sync_fail,
        "cold_periphery_flag": cold_periphery_flag,
        "finger_depth_misaligned": finger_depth_misaligned,
        "nail_obstruction": nail_obstruction,
        "optical_misalignment": optical_misalignment,
        "nail_polish_block": nail_polish_block,
        "ambient_light_spike": ambient_light_spike,
        "ppg_seal_loss": ppg_seal_loss,
        "ppg_seal_quality": ppg_seal_quality,
        "optical_dropout": optical_dropout,
        "calibration_movement_detected": calibration_movement_detected,
        "calibration_motion_detected": calibration_motion_detected,
        "sensor_impedance_high": sensor_impedance_high,
        "weekly_wash_reminder": weekly_wash_reminder,
        "impedance_buildup": impedance_buildup,
        "cpap_tube_and_wearable_conflict": cpap_tube_and_wearable_conflict,
        "concurrent_cpap_and_wearable_artifact": concurrent_cpap_and_wearable_artifact
    }


def evaluate_dynamic_trigger_rule(
    telemetry: Dict[str, Any],
    conditions: Dict[str, Any],
    condition_logic: str = "AND"
) -> bool:
    """
    Evaluates dynamic trigger rule conditions against patient telemetry.
    Supports explicit condition_logic:
    - 'AND': All listed metric thresholds must be breached concurrently to trigger.
    - 'OR': Any single condition breach qualifies.
    """
    if not conditions:
        return False

    logic = condition_logic.upper() if isinstance(condition_logic, str) else "AND"
    results = []

    # Normalize conditions to a list of (metric_name, op, target)
    parsed_rules = []
    if isinstance(conditions, dict):
        for metric_name, rule in conditions.items():
            if isinstance(rule, dict):
                op = rule.get("operator") or rule.get("op") or "=="
                target = rule.get("threshold") if "threshold" in rule else rule.get("value", 0.0)
            elif isinstance(rule, str):
                parts = rule.strip().split(maxsplit=1)
                if len(parts) == 2:
                    op, target = parts[0], parts[1]
                else:
                    op, target = "==", parts[0]
            else:
                op, target = "==", rule
            parsed_rules.append((metric_name, str(op), target))
    elif isinstance(conditions, (list, tuple)):
        for item in conditions:
            if isinstance(item, dict):
                metric_name = item.get("metric") or item.get("name") or item.get("key") or ""
                op = item.get("operator") or item.get("op") or "=="
                target = item.get("threshold") if "threshold" in item else item.get("value", 0.0)
                parsed_rules.append((metric_name, str(op), target))

    if not parsed_rules:
        return False

    for metric_name, op, raw_target in parsed_rules:
        mn_lower = str(metric_name).lower()
        val = None

        for k, v in telemetry.items():
            if str(k).lower() == mn_lower:
                val = v
                break

        if val is None:
            if "leak" in mn_lower:
                val = telemetry.get("leak_val") if "leak_val" in telemetry else telemetry.get("leak_rate", telemetry.get("leaks95"))
            elif "ahi" in mn_lower:
                val = telemetry.get("ahi_val") if "ahi_val" in telemetry else telemetry.get("ahi")
            elif "use" in mn_lower:
                val = telemetry.get("use_val") if "use_val" in telemetry else telemetry.get("usage_hours", telemetry.get("use"))
            elif "press" in mn_lower:
                val = telemetry.get("press_val") if "press_val" in telemetry else telemetry.get("pressure", telemetry.get("presure90"))
            elif "spo2" in mn_lower:
                val = telemetry.get("spo2_mas") or telemetry.get("spo2_ww") or telemetry.get("spo2")
            elif "bp" in mn_lower or "systolic" in mn_lower:
                val = telemetry.get("sys_bp") or telemetry.get("systolic_bp")
            elif "pi" in mn_lower:
                val = telemetry.get("pi_val") or telemetry.get("perfusion_index")
            elif "siq" in mn_lower:
                val = telemetry.get("siq_val") or telemetry.get("signal_iq")

        if val is None:
            results.append(False)
            continue

        passed = False
        try:
            target = float(raw_target)
            num_val = float(val)
            if op == ">=":
                passed = num_val >= target
            elif op == ">":
                passed = num_val > target
            elif op == "<=":
                passed = num_val <= target
            elif op == "<":
                passed = num_val < target
            elif op == "==":
                passed = abs(num_val - target) < 1e-6
            elif op == "!=":
                passed = abs(num_val - target) >= 1e-6
            else:
                passed = num_val >= target
        except Exception:
            passed = False

        results.append(passed)

    if not results:
        return False

    return any(results) if logic == "OR" else all(results)


# ==============================================================================
# 2. Scenario 1: Single Curated Video Selection
# ==============================================================================
def resolve_clinical_video_for_patient(
    patient_plan_row: Optional[Dict[str, Any]] = None,
    feature_row: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Scenario 1: Evaluates patient action plan and physiological telemetry to select
    the single most clinically relevant coaching video from the 37-video registry.
    """
    t = extract_telemetry_features(patient_plan_row, feature_row)

    # 1. Match explicit recommendation if specified by the pipeline
    if t["video_title"] and t["video_title"] != "none":
        for _, item in CLINICAL_VIDEO_REGISTRY.items():
            if item["title"].lower() in t["video_title"] or t["video_title"] in item["title"].lower():
                return item

    # 2. Critical & Urgent Clinical Alerts
    if t["ahi_val"] >= 30.0:
        return CLINICAL_VIDEO_REGISTRY[15]  # Severe Apnea - Contact Provider
    if t["afib_val"]:
        return CLINICAL_VIDEO_REGISTRY[20]  # BPM Core - Irregular ECG Alert
    if t["spo2_mas"] < 88.0:
        return CLINICAL_VIDEO_REGISTRY[22]  # RadG - Low Oxygen Reading
    if t["sys_bp"] >= 140.0:
        return CLINICAL_VIDEO_REGISTRY[19]  # BPM Core - High Blood Pressure
    if t["ahi_val"] >= 15.0 and t["use_val"] < 3.0:
        return CLINICAL_VIDEO_REGISTRY[13]  # High AHI + Low Usage
    if t["ahi_val"] >= 15.0:
        return CLINICAL_VIDEO_REGISTRY[12]  # Moderate Apnea Alert

    # 3. Mask Leaks & Fit Issues
    if t["leak_val"] >= 40.0:
        return CLINICAL_VIDEO_REGISTRY[14]  # Mask Style Change Needed
    if t["leak_val"] >= 30.0 and t["use_val"] < 2.0:
        return CLINICAL_VIDEO_REGISTRY[8]   # Mouth Breathing - Chin Support
    if t["leak_val"] >= 30.0:
        return CLINICAL_VIDEO_REGISTRY[2]   # Refit Mask While Lying Down
    if t["leak_val"] >= 24.0:
        return CLINICAL_VIDEO_REGISTRY[1]   # Adjust Mask Straps

    # 4. Adherence & Pressure Management
    if t["use_val"] == 0.0:
        return CLINICAL_VIDEO_REGISTRY[5]   # Zero usage: Daytime Practice
    if t["use_val"] < 4.0 and t["press_val"] >= 12.0:
        return CLINICAL_VIDEO_REGISTRY[4]   # High pressure discomfort: Ramp Mode
    if t["use_val"] < 4.0 and t["spo2_ww"] < 90.0:
        return CLINICAL_VIDEO_REGISTRY[16]  # Low oxygen during non-adherence
    if t["use_val"] < 4.0:
        return CLINICAL_VIDEO_REGISTRY[6]   # Early mask removal during sleep

    # 5. Multimodal Co-Usage & Wearable Sensor Alerts (Videos 28-37)
    r = t["reason_str"]

    # Co-Usage CPAP & Sensor Clearance (Video 37)
    if (
        t["cpap_tube_and_wearable_conflict"]
        or t["concurrent_cpap_and_wearable_artifact"]
        or t["co_usage_cable_alert"]
        or (t["n_devices"] >= 2 and t["leak_val"] >= 20.0)
        or any(k in r for k in ["cable", "tubing", "clearance", "entanglement", "routing", "concurrent", "conflict"])
    ):
        return CLINICAL_VIDEO_REGISTRY[37]  # Co-Usage - CPAP Tube & Wearable Cable Routing

    # Masimo MightySat (Videos 31, 33, 32)
    if t["pi_val"] < 0.5 or t["cold_periphery_flag"] or any(k in r for k in ["perfusion", "hand warming", "cold periphery"]):
        return CLINICAL_VIDEO_REGISTRY[31]  # Masimo MightySat - Low Perfusion & Hand Warming
    if t["siq_val"] < 60.0 or t["ambient_light_spike"] or any(k in r for k in ["signal iq", "light shielding", "ambient light", "siq"]):
        return CLINICAL_VIDEO_REGISTRY[33]  # Masimo MightySat - Signal IQ & Light Shielding
    if (
        t["finger_depth_misaligned"]
        or t["nail_obstruction"]
        or t["optical_misalignment"]
        or t["nail_polish_block"]
        or t["masimo_sensor_alert"]
        or any(k in r for k in ["finger depth", "nail", "optical misplacement", "nail polish", "misalignment", "obstruction"])
    ):
        return CLINICAL_VIDEO_REGISTRY[32]  # Masimo MightySat - Finger Depth & Nail Placement

    # Hexoskin Smart Garment (Videos 28, 29, 30)
    if (
        t["hexoskin_ecg_quality"] < 40.0
        or t["hr_dropout_rate"] >= 30.0
        or t["hexo_ecg_alert"]
        or any(k in r for k in ["electrode", "moistening", "skin contact", "ecg alert", "impedance", "hr dropout", "ecg quality"])
    ):
        return CLINICAL_VIDEO_REGISTRY[28]  # Hexoskin - Electrode Moistening & Skin Contact
    if (
        t["thoracic_belt_shift"]
        or t["rip_artifact"] >= 30.0
        or t["thoracic_motion_artifact"] >= 30.0
        or t["rip_signal_loss"]
        or t["hexo_motion"]
        or any(k in r for k in ["strap", "slippage", "motion artifact", "respiratory sensor slippage", "rip", "belt shift", "belt movement"])
    ):
        return CLINICAL_VIDEO_REGISTRY[29]  # Hexoskin - Dual Elastic Strap Adjustment
    if (
        t["docking_failure"]
        or t["sync_led_unconfirmed"]
        or t["hexoskin_dock_status"] is False
        or t["battery_sync_fail"]
        or t["hexo_docking_alert"]
        or any(k in r for k in ["docking", "sync unconfirmed", "recorder", "led confirmation", "not docked", "battery sync", "dock status", "docking failure", "sync led"])
    ):
        return CLINICAL_VIDEO_REGISTRY[30]  # Hexoskin - Recorder Docking & LED Confirmation

    # Somno-Art Wearable (Videos 34, 35, 36)
    if (
        t["ppg_seal_loss"]
        or t["ppg_seal_quality"] < 50.0
        or t["optical_dropout"]
        or t["somnoart_ppg_alert"]
        or any(k in r for k in ["forearm", "optical seal", "ppg", "sensor shift", "ppg dropout", "seal loss"])
    ):
        return CLINICAL_VIDEO_REGISTRY[34]  # Somno-Art - Forearm Placement & Optical Seal
    if (
        t["calibration_movement_detected"]
        or t["calibration_motion_detected"]
        or t["somnoart_calib_alert"]
        or any(k in r for k in ["calibration", "stillness", "led check", "movement during calibration", "calibration movement"])
    ):
        return CLINICAL_VIDEO_REGISTRY[35]  # Somno-Art - Calibration Stillness & LED Check
    if (
        t["sensor_impedance_high"]
        or t["weekly_wash_reminder"]
        or t["impedance_buildup"]
        or t["somnoart_hygiene_alert"]
        or any(k in r for k in ["pod care", "sleeve washing", "textile sleeve", "hygiene", "impedance", "wash reminder"])
    ):
        return CLINICAL_VIDEO_REGISTRY[36]  # Somno-Art - Pod Care & Textile Sleeve Hygiene

    # 6. Comfort, Dryness & Sleep Quality
    if 10.0 <= t["leak_val"] < 24.0 and t["press_val"] >= 10.0:
        return CLINICAL_VIDEO_REGISTRY[7]   # Dry Mouth - Use Humidifier
    if t["sleep_eff"] < 75.0:
        return CLINICAL_VIDEO_REGISTRY[27]  # SomnoArt - Poor Sleep Continuity

    # Default general coaching video
    return CLINICAL_VIDEO_REGISTRY[1]


# ==============================================================================
# 3. Scenario 2: Virtual Stitched Video Playlist
# ==============================================================================
def resolve_clinical_video_playlist_for_patient(
    patient_plan_row: Optional[Dict[str, Any]] = None,
    feature_row: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Scenario 2: Selects multiple co-occurring clinical coaching clips and generates
    a sequential 'virtual stitched' JSON metadata playlist for continuous frontend playback.
    """
    t = extract_telemetry_features(patient_plan_row, feature_row)
    selected_ids = []

    # Priority 1: Critical Alerts
    if t["ahi_val"] >= 30.0:
        selected_ids.append(15)
    elif t["ahi_val"] >= 15.0:
        selected_ids.append(12)
    if t["afib_val"]:
        selected_ids.append(20)
    if t["spo2_mas"] < 88.0:
        selected_ids.append(22)
    elif t["spo2_ww"] < 90.0:
        selected_ids.append(16)
    if t["sys_bp"] >= 140.0:
        selected_ids.append(19)

    # Priority 2: Mask & Leak Issues
    if t["leak_val"] >= 40.0:
        selected_ids.append(14)
    elif t["leak_val"] >= 30.0:
        selected_ids.append(2)
    elif t["leak_val"] >= 24.0:
        selected_ids.append(1)

    # Priority 3: Adherence & Pressure Discomfort
    if t["use_val"] == 0.0:
        selected_ids.append(5)
    elif t["use_val"] < 4.0:
        if t["press_val"] >= 12.0:
            selected_ids.append(4)
        selected_ids.append(6)

    # Priority 4: Wearable Sensor Calibration & Co-Usage Cable Clearance (Videos 28-37)
    r = t["reason_str"]

    # Multimodal Co-Usage Clearance
    if (
        t["cpap_tube_and_wearable_conflict"]
        or t["concurrent_cpap_and_wearable_artifact"]
        or t["co_usage_cable_alert"]
        or (t["n_devices"] >= 2 and t["leak_val"] >= 20.0)
        or any(k in r for k in ["cable", "tubing", "clearance", "entanglement", "routing", "concurrent", "conflict"])
    ):
        selected_ids.append(37)

    # Masimo MightySat
    if t["pi_val"] < 0.5 or t["cold_periphery_flag"] or any(k in r for k in ["perfusion", "hand warming", "cold periphery"]):
        selected_ids.append(31)
    if t["siq_val"] < 60.0 or t["ambient_light_spike"] or any(k in r for k in ["signal iq", "light shielding", "ambient light", "siq"]):
        selected_ids.append(33)
    if (
        t["finger_depth_misaligned"]
        or t["nail_obstruction"]
        or t["optical_misalignment"]
        or t["nail_polish_block"]
        or t["masimo_sensor_alert"]
        or any(k in r for k in ["finger depth", "nail", "optical misplacement", "nail polish", "misalignment", "obstruction"])
    ):
        selected_ids.append(32)

    # Hexoskin Smart Garment
    if (
        t["hexoskin_ecg_quality"] < 40.0
        or t["hr_dropout_rate"] >= 30.0
        or t["hexo_ecg_alert"]
        or any(k in r for k in ["electrode", "moistening", "skin contact", "ecg alert", "impedance", "hr dropout", "ecg quality"])
    ):
        selected_ids.append(28)
    if (
        t["thoracic_belt_shift"]
        or t["rip_artifact"] >= 30.0
        or t["thoracic_motion_artifact"] >= 30.0
        or t["rip_signal_loss"]
        or t["hexo_motion"]
        or any(k in r for k in ["strap", "slippage", "motion artifact", "respiratory sensor slippage", "rip", "belt shift", "belt movement"])
    ):
        selected_ids.append(29)
    if (
        t["docking_failure"]
        or t["sync_led_unconfirmed"]
        or t["hexoskin_dock_status"] is False
        or t["battery_sync_fail"]
        or t["hexo_docking_alert"]
        or any(k in r for k in ["docking", "sync unconfirmed", "recorder", "led confirmation", "not docked", "battery sync", "dock status", "docking failure", "sync led"])
    ):
        selected_ids.append(30)

    # Somno-Art Wearable
    if (
        t["ppg_seal_loss"]
        or t["ppg_seal_quality"] < 50.0
        or t["optical_dropout"]
        or t["somnoart_ppg_alert"]
        or any(k in r for k in ["forearm", "optical seal", "ppg", "sensor shift", "ppg dropout", "seal loss"])
    ):
        selected_ids.append(34)
    if (
        t["calibration_movement_detected"]
        or t["calibration_motion_detected"]
        or t["somnoart_calib_alert"]
        or any(k in r for k in ["calibration", "stillness", "led check", "movement during calibration", "calibration movement"])
    ):
        selected_ids.append(35)
    if (
        t["sensor_impedance_high"]
        or t["weekly_wash_reminder"]
        or t["impedance_buildup"]
        or t["somnoart_hygiene_alert"]
        or any(k in r for k in ["pod care", "sleeve washing", "textile sleeve", "hygiene", "impedance", "wash reminder"])
    ):
        selected_ids.append(36)

    # Priority 5: Comfort, Dryness & Sleep Quality
    if 10.0 <= t["leak_val"] < 24.0 and t["press_val"] >= 10.0:
        selected_ids.append(7)
    if t["sleep_eff"] < 75.0:
        selected_ids.append(27)

    # Fallback to single primary recommendation if no issues flagged
    if not selected_ids:
        primary = resolve_clinical_video_for_patient(patient_plan_row, feature_row)
        selected_ids = [primary["id"]]

    # Deduplicate while sorting by explicit clinical priority ranking:
    # critical -> high -> medium -> low -> maintenance
    priority_map = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "maintenance": 4
    }
    seen = set()
    deduped_ids = []
    for vid in selected_ids:
        if vid not in seen and vid in CLINICAL_VIDEO_REGISTRY:
            seen.add(vid)
            deduped_ids.append(vid)

    # Sequence compounding clinical clips strictly by clinical priority
    deduped_ids.sort(
        key=lambda vid: priority_map.get(
            CLINICAL_VIDEO_REGISTRY[vid].get("clinical_priority", "medium").lower(),
            2
        )
    )

    # Construct the JSON playlist with video URLs and bilingual WebVTT subtitles
    playlist = []
    base_v_url = VIDEO_SERVER_URL.rstrip("/")
    for step_idx, vid in enumerate(deduped_ids, 1):
        item = CLINICAL_VIDEO_REGISTRY[vid]
        stem = os.path.splitext(item["filename"])[0]
        playlist.append({
            "step": step_idx,
            "video_id": item["id"],
            "title": item["title"],
            "filename": item["filename"],
            "video_filename": item["filename"],
            "category": item.get("category", "General"),
            "duration_s": item.get("duration_s", 10.0),
            "condition_logic": item.get("condition_logic", "AND"),
            "clinical_priority": item.get("clinical_priority", "medium"),
            "reason": item.get("reason", ""),
            "video_url": f"{base_v_url}/videos/existing/{item['filename']}",
            "subtitle_en": f"{base_v_url}/subtitles/{stem}.en.vtt",
            "subtitle_fr": f"{base_v_url}/subtitles/{stem}.fr.vtt"
        })

    return playlist


# ==============================================================================
# 3. Persistent Video Assignment Tracker (Prevents Duplicate Assignments on Restart)
# ==============================================================================
ASSIGNMENT_TRACKER_FILE = os.path.join("artifacts", "assigned_videos_tracker.json")


class VideoAssignmentTracker:
    """
    Tracks video assignments persistently on disk across server restarts and crashes.
    Prevents duplicate coaching video dispatches to patients when the server restarts.
    """
    def __init__(self, tracker_path: str = ASSIGNMENT_TRACKER_FILE):
        self.tracker_path = tracker_path
        self.lock = threading.Lock()
        # Fast in-memory lookup sets:
        # _assigned_keys contains: (pid_str, filename_str) and (pid_str, str(video_id))
        self._assigned_keys: Set[Tuple[str, str]] = set()
        # _patient_latest maps pid_str -> latest assignment record
        self._patient_latest: Dict[str, Dict[str, Any]] = {}
        # _raw_assignments maps pid_str -> list of assignment records
        self._raw_assignments: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self):
        """Loads assignments from persistent storage (creates file if not present)."""
        with self.lock:
            self._assigned_keys.clear()
            self._patient_latest.clear()
            self._raw_assignments.clear()

            candidate_path = self.tracker_path
            if not os.path.exists(candidate_path):
                resolved = find_artifact_file(os.path.basename(self.tracker_path))
                if os.path.exists(resolved):
                    candidate_path = resolved

            if os.path.exists(candidate_path):
                for attempt in range(3):
                    try:
                        with open(candidate_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        assignments = data.get("assignments", {})
                        if isinstance(assignments, dict):
                            self._raw_assignments = assignments
                            for pid, items in assignments.items():
                                pid_str = str(pid)
                                if isinstance(items, list):
                                    for item in items:
                                        vid_fn = str(item.get("video_filename", "")).strip().lower()
                                        vid_id = item.get("video_id")
                                        if vid_fn:
                                            self._assigned_keys.add((pid_str, vid_fn))
                                        if vid_id is not None:
                                            self._assigned_keys.add((pid_str, str(vid_id)))
                                    if items:
                                        self._patient_latest[pid_str] = items[-1]
                                elif isinstance(items, dict):
                                    vid_fn = str(items.get("video_filename", "")).strip().lower()
                                    vid_id = items.get("video_id")
                                    if vid_fn:
                                        self._assigned_keys.add((pid_str, vid_fn))
                                    if vid_id is not None:
                                        self._assigned_keys.add((pid_str, str(vid_id)))
                                    self._patient_latest[pid_str] = items
                                    self._raw_assignments[pid_str] = [items]
                        logger.info(f"[VIDEO TRACKER] Loaded {len(self._assigned_keys)} tracked assignments for {len(self._patient_latest)} patients from '{candidate_path}'.")
                        break
                    except Exception as exc:
                        if attempt < 2:
                            time.sleep(0.05)
                        else:
                            logger.warning(f"[VIDEO TRACKER WARNING] Failed to parse assignment tracker file '{candidate_path}': {exc}")
            else:
                logger.info(f"[VIDEO TRACKER] Initialized new persistent tracker at '{self.tracker_path}'.")

    def is_assigned(
        self,
        patient_id: Union[str, int],
        video_id: Optional[int] = None,
        video_filename: Optional[str] = None
    ) -> bool:
        """
        Returns True if the specified video has already been assigned to this patient.
        Performs O(1) set lookup across in-memory tracking keys.
        """
        pid_str = str(patient_id)
        with self.lock:
            if video_filename:
                fn_clean = str(video_filename).strip().lower()
                if (pid_str, fn_clean) in self._assigned_keys:
                    return True
            if video_id is not None:
                if (pid_str, str(video_id)) in self._assigned_keys:
                    return True
            return False

    def get_latest_assignment(self, patient_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Returns the most recent assignment for the given patient, if any."""
        pid_str = str(patient_id)
        with self.lock:
            return self._patient_latest.get(pid_str)

    def record_assignment(
        self,
        patient_id: Union[str, int],
        video_record: Dict[str, Any],
        trigger_reason: str = "",
        event_id: Optional[str] = None,
        status: str = "success"
    ) -> Dict[str, Any]:
        """
        Records a newly dispatched video assignment in memory and flushes to disk.
        """
        pid_str = str(patient_id)
        vid_fn = str(video_record.get("filename", "")).strip()
        vid_id = video_record.get("id")
        record = {
            "patient_id": pid_str,
            "video_id": vid_id,
            "video_filename": vid_fn,
            "title": video_record.get("title", ""),
            "category": video_record.get("category", "Wearable Biomarkers"),
            "trigger_reason": trigger_reason or video_record.get("reason", ""),
            "event_id": event_id,
            "assigned_at": datetime.now().isoformat(),
            "status": status
        }

        with self.lock:
            if vid_fn:
                self._assigned_keys.add((pid_str, vid_fn.lower()))
            if vid_id is not None:
                self._assigned_keys.add((pid_str, str(vid_id)))

            if pid_str not in self._raw_assignments:
                self._raw_assignments[pid_str] = []
            self._raw_assignments[pid_str].append(record)
            self._patient_latest[pid_str] = record

            self._save_to_disk()

        return record

    def _save_to_disk(self):
        """Writes tracking state to disk atomically using a temp file."""
        try:
            target_dir = os.path.dirname(self.tracker_path) or "."
            os.makedirs(target_dir, exist_ok=True)
            data = {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "total_assigned_patients": len(self._raw_assignments),
                "total_tracked_keys": len(self._assigned_keys),
                "assignments": self._raw_assignments
            }
            tmp_path = f"{self.tracker_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if os.path.exists(self.tracker_path):
                try:
                    os.replace(tmp_path, self.tracker_path)
                except Exception:
                    os.remove(self.tracker_path)
                    os.rename(tmp_path, self.tracker_path)
            else:
                os.rename(tmp_path, self.tracker_path)
        except Exception as exc:
            logger.error(f"[VIDEO TRACKER ERROR] Failed to save tracker to '{self.tracker_path}': {exc}")

    def get_summary(self) -> Dict[str, Any]:
        """Returns high-level stats on tracked video assignments."""
        with self.lock:
            return {
                "tracker_path": self.tracker_path,
                "total_patients": len(self._raw_assignments),
                "total_assignments": sum(len(v) for v in self._raw_assignments.values()),
                "tracked_keys_count": len(self._assigned_keys)
            }

    def clear(self) -> Dict[str, Any]:
        """Clears all tracking history (used for manual administrative reset)."""
        with self.lock:
            self._assigned_keys.clear()
            self._patient_latest.clear()
            self._raw_assignments.clear()
            self._save_to_disk()
            logger.warning("[VIDEO TRACKER] All video assignments have been cleared.")
            return {"status": "success", "message": "Video assignment tracker cleared."}


# Global singleton instance of VideoAssignmentTracker
_GLOBAL_TRACKER: Optional[VideoAssignmentTracker] = None
_TRACKER_LOCK = threading.Lock()


def get_assignment_tracker() -> VideoAssignmentTracker:
    """Returns the process-wide VideoAssignmentTracker singleton."""
    global _GLOBAL_TRACKER
    if _GLOBAL_TRACKER is None:
        with _TRACKER_LOCK:
            if _GLOBAL_TRACKER is None:
                _GLOBAL_TRACKER = VideoAssignmentTracker()
    return _GLOBAL_TRACKER


def is_video_already_assigned(
    patient_id: Union[str, int],
    video_id: Optional[int] = None,
    video_filename: Optional[str] = None
) -> bool:
    """Public helper to verify if a video has already been assigned to a patient."""
    return get_assignment_tracker().is_assigned(patient_id, video_id, video_filename)


def record_video_assignment(
    patient_id: Union[str, int],
    video_record: Dict[str, Any],
    trigger_reason: str = "",
    event_id: Optional[str] = None,
    status: str = "success"
) -> Dict[str, Any]:
    """Public helper to manually record a video assignment in the persistent tracker."""
    return get_assignment_tracker().record_assignment(patient_id, video_record, trigger_reason, event_id, status)


# ==============================================================================
# 4. Dispatchers to Video VM Server (Port 8080)
# ==============================================================================
def orchestrate_video_recommendation(
    patient_id: Union[str, int],
    video_record: Dict[str, Any],
    custom_reason: Optional[str] = None,
    event_id: Optional[str] = None,
    check_duplicate: bool = True,
    force: bool = False
) -> Dict[str, Any]:
    """
    Scenario 1 Dispatcher: Sends single-clip prescription to Video VM Server POST /api/orchestrate.
    Checks persistent tracker by default to prevent duplicate assignments across restarts.
    """
    tracker = get_assignment_tracker()
    if isinstance(video_record, (int, str)):
        try:
            vid_int = int(video_record)
            video_record = CLINICAL_VIDEO_REGISTRY.get(
                vid_int,
                {"id": vid_int, "video_id": vid_int, "filename": f"{vid_int}.mp4", "title": f"Video {vid_int}"}
            )
        except (ValueError, TypeError):
            video_record = {"id": 0, "filename": str(video_record), "title": str(video_record)}

    vid_id = video_record.get("id") or video_record.get("video_id")
    vid_fn = video_record.get("filename")

    # Duplicate check against persistent storage
    if check_duplicate and not force and tracker.is_assigned(patient_id, vid_id, vid_fn):
        prev = tracker.get_latest_assignment(patient_id)
        assigned_time = prev.get("assigned_at") if prev else "previously"
        logger.info(f"[VIDEO ORCHESTRATION SKIPPED] Patient {patient_id} already assigned video '{vid_fn}' ({assigned_time}). Skipping duplicate dispatch.")
        return {
            "status": "already_assigned",
            "skipped": True,
            "duplicate_detected": True,
            "patient_id": str(patient_id),
            "video_filename": vid_fn,
            "title": video_record.get("title"),
            "message": f"Patient {patient_id} already assigned video '{vid_fn}' on {assigned_time}. Skipped duplicate dispatch.",
            "previous_assignment": prev
        }

    url = f"{VIDEO_SERVER_URL.rstrip('/')}/api/orchestrate"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": VIDEO_SERVER_API_KEY,
        "X-Video-Server-Key": VIDEO_SERVER_KEY
    }

    if not event_id:
        event_id = f"EVT_{datetime.now().strftime('%Y%m%d')}_P{patient_id}_V{video_record.get('id', 1)}"

    payload = {
        "event_id": event_id,
        "patient_id": str(patient_id),
        "video_type": "single",
        "title": video_record["title"],
        "video_filename": video_record["filename"],
        "duration_s": float(video_record.get("duration_s", 10.0)),
        "category": video_record.get("category", "General"),
        "trigger_reason": custom_reason or video_record.get("reason", "AI clinical recommendation"),
        "relevance": "high",
        "thumbnail_type": "technical"
    }

    stem = os.path.splitext(video_record["filename"])[0]
    base_v_url = VIDEO_SERVER_URL.rstrip("/")

    logger.info("-" * 75)
    logger.info("[SCENARIO 1 ACTIVE: EXISTING VIDEO SELECTION (SINGLE CLIP PRESCRIPTION)]")
    logger.info(f"   Event ID           : {event_id}")
    logger.info(f"   Patient ID         : {patient_id}")
    logger.info(f"   Clinical Topic     : '{video_record['title']}'")
    logger.info(f"   Original MP4 File  : {video_record['filename']}")
    logger.info(f"   Subtitle (English) : {stem}.en.vtt")
    logger.info(f"   Subtitle (French)  : {stem}.fr.vtt")
    logger.info(f"   Video Stream URL   : {base_v_url}/videos/existing/{video_record['filename']}")
    logger.info(f"   Target Endpoint    : POST {url}")

    start_t = time.perf_counter()
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        if res.status_code == 200:
            try:
                res_data = res.json()
            except Exception:
                res_data = {}

            if isinstance(res_data, dict) and (res_data.get("status") == "already_assigned" or res_data.get("duplicate_detected") is True):
                logger.info(f"   -> [VM4 DEDUPLICATION SHIELD] Video VM detected duplicate assignment in {elapsed_ms:.2f}ms (Fast-Path). Dashboard push safely skipped.")
                tracker.record_assignment(
                    patient_id=patient_id,
                    video_record=video_record,
                    trigger_reason=payload["trigger_reason"],
                    event_id=event_id,
                    status="already_assigned"
                )
                logger.info("-" * 75)
                return {
                    "status": "already_assigned",
                    "duplicate_detected": True,
                    "dashboard_push": "skipped_duplicate",
                    "http_code": 200,
                    "data": res_data
                }
            else:
                logger.info(f"   -> [SCENARIO 1 SUCCESS] Delivered to Video VM Server (HTTP {res.status_code} in {elapsed_ms:.2f}ms)")
                # Persist assignment immediately to disk tracker
                tracker.record_assignment(
                    patient_id=patient_id,
                    video_record=video_record,
                    trigger_reason=payload["trigger_reason"],
                    event_id=event_id,
                    status="success"
                )
        else:
            logger.warning(f"   -> [SCENARIO 1 WARN/ERR] Video VM returned HTTP {res.status_code}: {res.text[:200]}")
            try:
                res_data = res.json()
            except Exception:
                res_data = res.text
        logger.info("-" * 75)
        return {
            "status": "success" if res.status_code == 200 else "error",
            "http_code": res.status_code,
            "data": res_data
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        logger.error(f"   -> [SCENARIO 1 FAILED] Connection error to Video VM Server: {exc} ({elapsed_ms:.2f}ms)")
        logger.info("-" * 75)
        return {"status": "failed", "error": str(exc)}


def orchestrate_video_package(
    patient_id: Union[str, int],
    playlist_items: List[Dict[str, Any]],
    package_title: str = "Personalized CPAP Video Coaching Sequence",
    event_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scenario 2 Dispatcher: Sends multi-clip virtual package to Video VM Server POST /api/orchestrate.
    """
    url = f"{VIDEO_SERVER_URL.rstrip('/')}/api/orchestrate"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": VIDEO_SERVER_API_KEY,
        "X-Video-Server-Key": VIDEO_SERVER_KEY
    }

    clips = []
    base_v_url = VIDEO_SERVER_URL.rstrip("/")
    for item in playlist_items:
        vid_id = item.get("video_id", 1)
        filename = item.get("video_filename") or item.get("filename") or CLINICAL_VIDEO_REGISTRY.get(vid_id, {}).get("filename", f"{vid_id}.mp4")
        stem = os.path.splitext(filename)[0]
        clips.append({
            "step": item.get("step", len(clips) + 1),
            "video_id": vid_id,
            "title": item.get("title", ""),
            "video_filename": filename,
            "subtitle_en": f"{stem}.en.vtt",
            "subtitle_fr": f"{stem}.fr.vtt",
            "url": f"{base_v_url}/videos/existing/{filename}",
            "duration_s": float(item.get("duration_s", 10.0)),
            "transition": item.get("transition", "fade_1_5s")
        })

    if not event_id:
        event_id = f"EVT_{datetime.now().strftime('%Y%m%d')}_COMBO_{patient_id}"

    payload = {
        "event_id": event_id,
        "patient_id": str(patient_id),
        "video_type": "package",
        "scenario": "scenario_2_stitched_sequence",
        "transition_type": "fade_1_5s",
        "title": package_title,
        "total_clips": len(clips),
        "clips": clips,
        "relevance": "high",
        "thumbnail_type": "technical"
    }

    logger.info("-" * 75)
    logger.info("[SCENARIO 2 ACTIVE: VIDEOS STITCHING TOGETHER (MULTI-CLIP VIRTUAL STITCHING)]")
    logger.info(f"   Event ID           : {event_id}")
    logger.info(f"   Patient ID         : {patient_id}")
    logger.info(f"   Package Title      : '{package_title}'")
    logger.info(f"   Total Clips Count  : {len(clips)}")
    logger.info("   Transition Effect  : fade_1_5s (smooth blending)")
    logger.info(f"   Target Endpoint    : POST {url}")

    start_t = time.perf_counter()
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        if res.status_code == 200:
            try:
                res_data = res.json()
            except Exception:
                res_data = {}
            if isinstance(res_data, dict) and (res_data.get("status") == "already_assigned" or res_data.get("duplicate_detected") is True):
                logger.info(f"   -> [VM4 DEDUPLICATION SHIELD] Video VM detected duplicate package in {elapsed_ms:.2f}ms (Fast-Path). Dashboard push safely skipped.")
                logger.info("-" * 75)
                return {
                    "status": "already_assigned",
                    "duplicate_detected": True,
                    "dashboard_push": "skipped_duplicate",
                    "http_code": 200,
                    "data": res_data
                }
            else:
                logger.info(f"   -> [SCENARIO 2 SUCCESS] Delivered to Video VM Server (HTTP {res.status_code} in {elapsed_ms:.2f}ms)")
        else:
            logger.warning(f"   -> [SCENARIO 2 WARN/ERR] Video VM returned HTTP {res.status_code}: {res.text[:200]}")
            try:
                res_data = res.json()
            except Exception:
                res_data = res.text
        logger.info("-" * 75)
        return {
            "status": "success" if res.status_code == 200 else "error",
            "http_code": res.status_code,
            "data": res_data
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        logger.error(f"   -> [SCENARIO 2 FAILED] Connection error to Video VM Server: {exc} ({elapsed_ms:.2f}ms)")
        logger.info("-" * 75)
        return {"status": "failed", "error": str(exc)}


class VideoOrchestrationClient:
    """
    Lightweight client for distributed video trigger synchronization and coaching dispatch.
    Connects to the CPAP Video VM (Port 8080) to refresh triggers dynamically (Option A) and
    dispatch Scenario 1 (single-clip) and Scenario 2 (multi-clip virtual package) coaching sessions.
    """
    def __init__(self, video_vm_url: str = VIDEO_SERVER_URL, api_key: str = VIDEO_SERVER_API_KEY):
        self.base_url = video_vm_url.rstrip("/")
        self.headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        self.triggers: List[Dict[str, Any]] = []
        self.refresh_catalog()

    def refresh_catalog(self) -> Dict[str, Any]:
        """Fetches the latest dynamic video triggers from Video VM (Option A)."""
        res = sync_video_catalog_from_vm(self.base_url)
        self.triggers = get_dynamic_catalog_state().get("video_triggers", [])
        return res

    sync_catalog = refresh_catalog

    def dispatch_coaching(
        self,
        patient_id: Union[str, int],
        video_filename: Optional[str] = None,
        title: Optional[str] = None,
        trigger_reason: str = "AI clinical recommendation",
        category: Optional[str] = None,
        event_id: Optional[str] = None,
        video_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Dispatches a recommended coaching video to the Video VM and Dashboard (Scenario 1)."""
        if video_id is not None and video_id in CLINICAL_VIDEO_REGISTRY:
            reg = CLINICAL_VIDEO_REGISTRY[video_id]
            video_filename = video_filename or reg["filename"]
            title = title or reg["title"]
            category = category or reg.get("category", "Wearable Biomarkers")

        vid_record = {
            "id": video_id,
            "filename": video_filename or "",
            "title": title or "Personalized CPAP Coaching",
            "category": category or "Personalized Coaching",
            "duration_s": 10.0,
            "reason": trigger_reason
        }
        return orchestrate_video_recommendation(
            patient_id=str(patient_id),
            video_record=vid_record,
            custom_reason=trigger_reason,
            event_id=event_id
        )

    dispatch_single_recommendation = dispatch_coaching

    def dispatch_package(
        self,
        patient_id: Union[str, int],
        playlist_items: List[Dict[str, Any]],
        package_title: str = "Personalized CPAP Video Coaching Sequence",
        event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dispatches a multi-clip virtual package sequence to the Video VM (Scenario 2)."""
        return orchestrate_video_package(
            patient_id=str(patient_id),
            playlist_items=playlist_items,
            package_title=package_title,
            event_id=event_id
        )


def trigger_vertex_video_generation(
    patient_id: str,
    prompt: str,
    model: str = "veo-3.1-generate-preview"
) -> Dict[str, Any]:
    """
    Scenario 3 Dispatcher: Triggers generative AI video synthesis via Google Vertex AI / Veo 3.1
    by posting to Video VM Server POST /api/vertex-generate.
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

    logger.info("-" * 75)
    logger.info("[SCENARIO 3 ACTIVE: NEW VIDEO GENERATION (GOOGLE VERTEX AI / VEO 3.1)]")
    logger.info(f"   Patient ID         : {patient_id}")
    logger.info(f"   Synthesis Prompt   : '{prompt}'")
    logger.info(f"   Generative Model   : {model}")
    logger.info(f"   Target Endpoint    : POST {url}")

    start_t = time.perf_counter()
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=35)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        logger.info(f"   -> [SCENARIO 3 RESPONSE] Status {res.status_code} in {elapsed_ms:.2f}ms")
        logger.info("-" * 75)
        try:
            vertex_data = res.json()
        except Exception:
            vertex_data = res.text
        return {
            "status": "success" if res.status_code == 200 else "error",
            "http_code": res.status_code,
            "data": vertex_data
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        logger.error(f"   -> [SCENARIO 3 ERROR] Failed to dispatch Vertex generation: {exc} ({elapsed_ms:.2f}ms)")
        logger.info("-" * 75)
        return {"status": "failed", "error": str(exc)}


def assign_video_to_dashboard(
    patient_id: str,
    video_record: Dict[str, Any],
    custom_reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Direct assignment helper that posts to the Web App Dashboard POST /api/videos/{patient_id}/assign
    with the required X-Video-Server-Key header.
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
    except Exception as exc:
        return {"status": "exception", "detail": str(exc)}


def orchestrate_pipeline_videos(force: bool = False, max_dispatches: Optional[int] = None) -> Dict[str, Any]:
    """
    Scans the latest patient action plan artifacts after a pipeline execution,
    resolving clinical video recommendations and dispatching authenticated
    requests to the Video VM Server for all eligible patients.
    Tracks previously assigned videos persistently to prevent duplicate assignments across restarts.
    """
    results_file = find_artifact_file("patient_action_plan.csv")
    if not os.path.exists(results_file):
        results_file = find_artifact_file("layer3_results.csv")
    if not os.path.exists(results_file):
        logger.warning("[VIDEO ORCHESTRATOR WARNING] No patient action plan artifact found for video orchestration.")
        return {"status": "skipped", "reason": "No action plan"}

    feat_dict = {}
    feat_file = find_artifact_file("features_merged.csv")
    if os.path.exists(feat_file):
        try:
            f_df = _original_read_csv(feat_file)
            for _, f_row in f_df.iterrows():
                if "AtHomePatientId" in f_row and pd.notna(f_row["AtHomePatientId"]):
                    feat_dict[str(int(f_row["AtHomePatientId"]))] = f_row.to_dict()
        except Exception:
            pass

    try:
        df = _original_read_csv(results_file)
        orchestrated_count = 0
        skipped_duplicate_count = 0
        results = []

        tracker = get_assignment_tracker()
        summary = tracker.get_summary()

        if max_dispatches is None:
            env_limit = os.environ.get("MAX_VIDEO_DISPATCHES_PER_RUN", "").strip()
            max_dispatches = int(env_limit) if env_limit.isdigit() and int(env_limit) > 0 else None

        logger.info(f"\n[VIDEO ORCHESTRATOR] Evaluating {len(df)} patients for Video VM Server orchestration ({VIDEO_SERVER_URL})...")
        logger.info(f"[VIDEO ORCHESTRATOR] Persistent Tracker: {summary['total_patients']} patients currently recorded ({summary['total_assignments']} total assignments).")
        if force:
            logger.warning("[VIDEO ORCHESTRATOR] Force flag is TRUE: duplicate checking bypassed.")

        for _, row in df.iterrows():
            if max_dispatches is not None and orchestrated_count >= max_dispatches:
                logger.info(f"[VIDEO ORCHESTRATOR] Reached dispatch batch limit ({max_dispatches}) for this cycle. Remaining will be evaluated on the next run.")
                break

            if pd.isna(row.get("AtHomePatientId")):
                continue
            pid = str(int(row["AtHomePatientId"]))
            rec = str(row.get("intervention_rec", "")).strip().lower()
            risk_lvl = str(row.get("risk_level", "")).strip().lower()

            # Trigger video coaching for explicitly recommended patients or medium/high risk
            should_orchestrate = (rec == "video") or (risk_lvl in ["high", "medium"])

            if should_orchestrate:
                p_dict = row.to_dict()
                f_row = feat_dict.get(pid, {})
                video_item = resolve_clinical_video_for_patient(p_dict, f_row)

                # Fast O(1) duplicate check against persistent tracker
                if not force and tracker.is_assigned(pid, video_item.get("id"), video_item.get("filename")):
                    skipped_duplicate_count += 1
                    continue

                trigger_reason = str(row.get("intervention_reason", "")) or video_item["reason"]

                logger.info(f" [VIDEO ORCHESTRATION] Dispatching Patient {pid} -> '{video_item['title']}' ({video_item['filename']})...")
                res = orchestrate_video_recommendation(
                    patient_id=pid,
                    video_record=video_item,
                    custom_reason=trigger_reason,
                    check_duplicate=False,  # Already checked in loop
                    force=force
                )
                results.append({"patient_id": pid, "video": video_item["filename"], "dispatch": res})
                if res.get("status") == "success" and not res.get("duplicate_detected"):
                    orchestrated_count += 1
                elif res.get("status") == "already_assigned" or res.get("duplicate_detected") is True:
                    skipped_duplicate_count += 1

        with state_lock:
            pipeline_state["last_video_orchestrations"] = orchestrated_count
            pipeline_state["last_video_skipped_duplicates"] = skipped_duplicate_count

        logger.info(
            f"[VIDEO ORCHESTRATOR SUCCESS] Newly dispatched: {orchestrated_count} | "
            f"Skipped duplicates (already assigned): {skipped_duplicate_count} | "
            f"Persistent tracker total: {tracker.get_summary()['total_patients']} patients."
        )
        return {
            "status": "success",
            "orchestrated_count": orchestrated_count,
            "skipped_duplicate_count": skipped_duplicate_count,
            "total_tracked_patients": tracker.get_summary()["total_patients"],
            "details": results[:100]
        }
    except Exception as exc:
        logger.error(f"[VIDEO ORCHESTRATOR ERROR] Failed during video orchestration: {exc}")
        return {"status": "error", "error": str(exc)}
