"""
SleepCare AI Server - Model, Video & State Registries
=====================================================
This module manages:
1. The 37-item Clinical Video Registry (used for Scenarios 1 & 2 video coaching).
2. The 4 Machine Learning Production Models Registry.
3. Thread-safe execution states for background pipelines and model health.
"""

import os
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import requests

from core.config import VIDEO_SERVER_URL, LOCAL_CATALOG_PATH

logger = logging.getLogger("ai_server.registry")

# Mutex lock to prevent race conditions when background threads update state
state_lock = threading.Lock()

# ==============================================================================
# 1. Clinical Video Registry (37 Prescriptive Coaching Videos)
# ==============================================================================
# Each video maps directly to clinical criteria (e.g. high leak, low usage, SpO2 drops).
# Video files reside on the Video VM (Port 8080) with matching .en.vtt and .fr.vtt subtitles.
CLINICAL_VIDEO_REGISTRY: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "filename": "1_Mask_leak_adjust_straps.mp4",
        "title": "Adjust Mask Straps",
        "category": "Mask & Equipment",
        "duration_s": 10.0,
        "reason": "Elevated mask leak detected (>= 24 L/min)"
    },
    2: {
        "id": 2,
        "filename": "2_Mask_leak_refit_while_lying_down.mp4",
        "title": "Refit Mask While Lying Down",
        "category": "Mask & Equipment",
        "duration_s": 10.0,
        "reason": "Severe mask leak detected while in bed (>= 30 L/min)"
    },
    3: {
        "id": 3,
        "filename": "3_Cushion_cleaning_reminder.mp4",
        "title": "Cushion Cleaning Reminder",
        "category": "Maintenance",
        "duration_s": 10.0,
        "reason": "Routine cushion hygiene & maintenance reminder"
    },
    4: {
        "id": 4,
        "filename": "4_Low_usage_use_ramp_mode.mp4",
        "title": "Low Usage - Use Ramp Mode",
        "category": "Tips & Tricks",
        "duration_s": 10.0,
        "reason": "High initial pressure discomfort (P90 >= 12 cmH2O) with low usage"
    },
    5: {
        "id": 5,
        "filename": "5_Low_usage_daytime_practice.mp4",
        "title": "Low Usage - Daytime Practice",
        "category": "Tips & Tricks",
        "duration_s": 10.0,
        "reason": "Zero nightly usage — daytime acclimation recommended"
    },
    6: {
        "id": 6,
        "filename": "6_Early_mask_removal.mp4",
        "title": "Early Mask Removal",
        "category": "Tips & Tricks",
        "duration_s": 10.0,
        "reason": "Early unconscious mask removal during the night"
    },
    7: {
        "id": 7,
        "filename": "7_Dry_mouth_humidifier.mp4",
        "title": "Dry Mouth - Use Humidifier",
        "category": "Comfort",
        "duration_s": 10.0,
        "reason": "Dry mouth / airway dryness with elevated pressure"
    },
    8: {
        "id": 8,
        "filename": "8_Mouth_breathing_chin_support.mp4",
        "title": "Mouth Breathing - Chin Support",
        "category": "Mask & Equipment",
        "duration_s": 10.0,
        "reason": "Oral leak / mouth breathing under pressure"
    },
    9: {
        "id": 9,
        "filename": "9_Nasal_congestion_relief.mp4",
        "title": "Nasal Congestion Relief",
        "category": "Comfort",
        "duration_s": 10.0,
        "reason": "Nasal congestion / airway resistance before sleep"
    },
    10: {
        "id": 10,
        "filename": "10_Aerophagia_elevate_head.mp4",
        "title": "Aerophagia - Elevate Head",
        "category": "Tips & Tricks",
        "duration_s": 10.0,
        "reason": "Aerophagia / swallowed air with elevated pressure"
    },
    11: {
        "id": 11,
        "filename": "11_Aerophagia_side_sleeping.mp4",
        "title": "Aerophagia - Side Sleeping",
        "category": "Tips & Tricks",
        "duration_s": 10.0,
        "reason": "Positional aerophagia and residual events"
    },
    12: {
        "id": 12,
        "filename": "12_High_breathing_events_contact_provider.mp4",
        "title": "High Breathing Events - Contact Provider",
        "category": "Clinical Alerts",
        "duration_s": 10.0,
        "reason": "Elevated residual apnea index (AHI >= 15/hr)"
    },
    13: {
        "id": 13,
        "filename": "13_Biomarker_changes_use_cpap_and_alert.mp4",
        "title": "Biomarker Changes - Use CPAP & Contact Provider",
        "category": "Clinical Alerts",
        "duration_s": 10.0,
        "reason": "High AHI combined with insufficient nightly CPAP usage"
    },
    14: {
        "id": 14,
        "filename": "14_Mask_style_change_needed.mp4",
        "title": "Mask Style Change Needed",
        "category": "Mask & Equipment",
        "duration_s": 10.0,
        "reason": "Persistent critical mask leak (>= 40 L/min) requiring mask style swap"
    },
    15: {
        "id": 15,
        "filename": "15_Severe_apnea_contact_provider.mp4",
        "title": "Severe Apnea - Contact Your Provider",
        "category": "Clinical Alerts",
        "duration_s": 10.0,
        "reason": "Urgent Alert: Severe apnea events (AHI >= 30/hr)"
    },
    16: {
        "id": 16,
        "filename": "16_ScanWatch_Low_nighttime_oxygen.mp4",
        "title": "ScanWatch - Low Nighttime Oxygen",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "ScanWatch detected nocturnal SpO2 desaturation (< 90%)"
    },
    17: {
        "id": 17,
        "filename": "17_ScanWatch_Fragmented_sleep.mp4",
        "title": "ScanWatch - Fragmented Sleep",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "ScanWatch detected severe sleep fragmentation / micro-arousals (>= 15/hr)"
    },
    18: {
        "id": 18,
        "filename": "18_ScanWatch_Unusual_heart_rhythm.mp4",
        "title": "ScanWatch - Unusual Heart Rhythm Signal",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "ScanWatch flagged nocturnal cardiac rhythm / HRV anomaly"
    },
    19: {
        "id": 19,
        "filename": "19_BPM_Core_High_blood_pressure.mp4",
        "title": "BPM Core - High Blood Pressure",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "BPM Core detected morning hypertension (Systolic >= 140 mmHg)"
    },
    20: {
        "id": 20,
        "filename": "20_BPM_Core_Irregular_ECG_alert.mp4",
        "title": "BPM Core - Irregular ECG Alert",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "BPM Core flagged potential Atrial Fibrillation (Afib) risk"
    },
    21: {
        "id": 21,
        "filename": "21_BPM_Core_Heart_sound_review.mp4",
        "title": "BPM Core - Heart Sound Review Needed",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "BPM Core digital stethoscope flagged valvular sound anomaly"
    },
    22: {
        "id": 22,
        "filename": "22_RadG_Low_oxygen_reading.mp4",
        "title": "RadG - Low Oxygen Reading",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "RadG medical pulse oximeter registered critical SpO2 drop (< 88%)"
    },
    23: {
        "id": 23,
        "filename": "23_RadG_Pulse_breathing_instability.mp4",
        "title": "RadG - Pulse or Breathing Instability",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "RadG registered high pulse rate variability / respiratory instability"
    },
    24: {
        "id": 24,
        "filename": "24_ProShirt_Breathing_pattern_changed.mp4",
        "title": "ProShirt - Breathing Pattern Changed",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "ProShirt smart vest detected paradoxical thoraco-abdominal asynchrony (> 30%)"
    },
    25: {
        "id": 25,
        "filename": "25_ProShirt_Fit_check.mp4",
        "title": "ProShirt - Fit Check",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "ProShirt smart vest signal quality low (< 70%) — garment fit check"
    },
    26: {
        "id": 26,
        "filename": "26_SomnoArt_Sleep_architecture_changed.mp4",
        "title": "SomnoArt - Sleep Architecture Changed",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "SomnoArt hypnogram detected severe REM sleep deprivation (REM < 12%)"
    },
    27: {
        "id": 27,
        "filename": "27_SomnoArt_Poor_sleep_continuity.mp4",
        "title": "SomnoArt - Poor Sleep Continuity",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "SomnoArt recorded poor sleep efficiency (< 75%)"
    },
    28: {
        "id": 28,
        "filename": "28_Hexoskin_Electrode_moistening_prep.mp4",
        "title": "Hexoskin: Electrode Moistening & Skin Contact",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "Low ECG/cardiac amplitude or electrode impedance alert"
    },
    29: {
        "id": 29,
        "filename": "29_Hexoskin_Elastic_strap_adjustment.mp4",
        "title": "Hexoskin: Dual Elastic Strap Adjustment",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "Thoracic/abdominal respiratory sensor slippage or motion artifacts"
    },
    30: {
        "id": 30,
        "filename": "30_Hexoskin_Recorder_docking_led_check.mp4",
        "title": "Hexoskin: Device Docking & LED Confirmation",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "Recording device not docked or battery/data sync unconfirmed"
    },
    31: {
        "id": 31,
        "filename": "31_MightySat_Low_perfusion_hand_warming.mp4",
        "title": "Masimo MightySat: Low Perfusion & Hand Warming",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "Low Perfusion Index (PI < 0.5%) or cold periphery signal loss"
    },
    32: {
        "id": 32,
        "filename": "32_MightySat_Finger_depth_nail_prep.mp4",
        "title": "Masimo MightySat: Finger Depth & Nail Placement",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "Optical sensor misplacement or nail polish optical blockage"
    },
    33: {
        "id": 33,
        "filename": "33_MightySat_Signal_iq_light_shielding.mp4",
        "title": "Masimo MightySat: Signal IQ & Light Shielding",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "High ambient light interference or low Signal IQ (SIQ < 60%)"
    },
    34: {
        "id": 34,
        "filename": "34_SomnoArt_Forearm_positioning_ppg_seal.mp4",
        "title": "Somno-Art: Forearm Placement & Optical Seal",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "PPG signal dropout or wrist/forearm sensor shift"
    },
    35: {
        "id": 35,
        "filename": "35_SomnoArt_Calibration_stillness_led_check.mp4",
        "title": "Somno-Art: Calibration Stillness & LED Check",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "Calibration interrupted by patient movement or LED sync error"
    },
    36: {
        "id": 36,
        "filename": "36_SomnoArt_Pod_care_sleeve_washing.mp4",
        "title": "Somno-Art: Pod Care & Textile Sleeve Hygiene",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "reason": "Sensor impedance due to skin oil buildup or hygiene interval"
    },
    37: {
        "id": 37,
        "filename": "37_CoUsage_CPAP_tubing_sensor_clearance.mp4",
        "title": "Co-Usage: CPAP Tube & Wearable Cable Routing",
        "category": "Wearable Biomarkers",
        "duration_s": 10.0,
        "condition_logic": "AND",
        "clinical_priority": "high",
        "reason": "CPAP air hose entanglement with wearable sensor cables"
    },
    38: {
        "id": 38,
        "filename": "38_Create_A_Clinical_Instructional_Animation_Showing.mp4",
        "title": "Clinical Instructional Mask Seal Animation",
        "category": "Generative AI",
        "bucket": "generated",
        "duration_s": 10.0,
        "condition_logic": "AND",
        "clinical_priority": "high",
        "reason": "AI generative coaching for complex mask seal and headgear fit"
    },
    39: {
        "id": 39,
        "filename": "39_Humidifier_Tube_Adjustment_Animation.mp4",
        "title": "Humidifier Tube Adjustment Animation",
        "category": "Generative AI",
        "bucket": "generated",
        "duration_s": 10.0,
        "condition_logic": "OR",
        "clinical_priority": "medium",
        "reason": "AI generative coaching for heated tube condensation and temperature tuning"
    }
}

# ==============================================================================
# 2. Production ML Models Registry
# ==============================================================================
# Tracks the 4 core machine learning models, validation scores, and drift thresholds.
ML_MODELS_REGISTRY: Dict[str, Dict[str, Any]] = {
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

# ==============================================================================
# 3. Model Health & Pipeline Execution State
# ==============================================================================
# Tracks runtime degradations (e.g. if CatBoost or LightGBM fell back to safe dummy modes)
MODEL_HEALTH: Dict[str, Any] = {
    "catboost_dummy_fallback": False,
    "lightgbm_dummy_fallback": False,
    "degraded_warnings": []
}

# Live state of the 30-minute periodic model pipeline runner
pipeline_state: Dict[str, Any] = {
    "status": "idle",             # Can be "idle", "running", or "failed"
    "last_run_start": None,
    "last_run_finish": None,
    "last_duration_seconds": None,
    "last_error": None,
    "total_runs": 0,
    "last_video_orchestrations": 0,
    "last_video_skipped_duplicates": 0
}


def get_pipeline_state_copy() -> Dict[str, Any]:
    """Returns a thread-safe snapshot of the current pipeline state."""
    with state_lock:
        return dict(pipeline_state)


def get_model_health_copy() -> Dict[str, Any]:
    """Returns a thread-safe snapshot of the current model health status."""
    with state_lock:
        return {
            "catboost_dummy_fallback": MODEL_HEALTH["catboost_dummy_fallback"],
            "lightgbm_dummy_fallback": MODEL_HEALTH["lightgbm_dummy_fallback"],
            "degraded_warnings": list(MODEL_HEALTH["degraded_warnings"])
        }


# ==============================================================================
# 4. Dynamic Video Catalog & Distributed Trigger Synchronization
# ==============================================================================
# Tracks live catalog metadata dynamically synced from the Video VM (Port 8080)
DYNAMIC_CATALOG_STATE: Dict[str, Any] = {
    "last_synced": None,
    "source": "static_baseline",
    "summary": {
        "total_curated_videos": 37,
        "total_ai_videos": 2,
        "total_library_videos": 39,
        "total_subtitle_tracks": 78,
        "total_indexed_triggers": 39
    },
    "video_triggers": []
}


def get_dynamic_catalog_state() -> Dict[str, Any]:
    """Returns a thread-safe copy of the dynamic video triggers catalog state."""
    with state_lock:
        return {
            "last_synced": DYNAMIC_CATALOG_STATE["last_synced"],
            "source": DYNAMIC_CATALOG_STATE["source"],
            "summary": dict(DYNAMIC_CATALOG_STATE["summary"]),
            "video_triggers": list(DYNAMIC_CATALOG_STATE["video_triggers"]),
            "total_curated_videos": DYNAMIC_CATALOG_STATE["summary"].get("total_curated_videos", len(CLINICAL_VIDEO_REGISTRY)),
            "total_library_videos": DYNAMIC_CATALOG_STATE["summary"].get("total_library_videos", len(CLINICAL_VIDEO_REGISTRY))
        }


def save_local_catalog_cache(payload: Dict[str, Any]):
    """Persists the live catalog payload atomically to distributed_trigger_catalog.json."""
    target_path = LOCAL_CATALOG_PATH
    try:
        parent_dir = os.path.dirname(target_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        tmp_path = f"{target_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        if os.path.exists(target_path):
            os.replace(tmp_path, target_path)
        else:
            os.rename(tmp_path, target_path)
    except Exception as exc:
        logger.debug(f"[REGISTRY] Could not persist local catalog cache to '{target_path}': {exc}")


def load_local_catalog_cache(filepath: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads distributed trigger catalog from local filesystem cache if present.
    Enforces explicit boolean logic (AND/OR) and clinical priority ranking.
    """
    candidate_paths = [
        p for p in [filepath, LOCAL_CATALOG_PATH, os.path.join("artifacts", "distributed_trigger_catalog.json")]
        if p
    ]
    for cp in candidate_paths:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                res = update_catalog_from_payload(data, persist=False, source="local_distributed_cache")
                logger.info(f"[AI SERVER] Loaded {res['updated_count']} triggers from local catalog cache '{cp}'.")
                return res
            except Exception as exc:
                logger.warning(f"[AI SERVER WARN] Could not read local catalog cache '{cp}': {exc}")
    return {"status": "none", "updated_count": 0}


def update_catalog_from_payload(
    payload: Dict[str, Any],
    persist: bool = True,
    source: str = "video_vm_sync"
) -> Dict[str, Any]:
    """
    Updates the in-memory video registry and dynamic catalog cache from a Video VM payload.
    Supports explicit condition logic ("AND" | "OR") and clinical priority ranking.
    """
    with state_lock:
        if isinstance(payload, list):
            triggers = payload
        elif isinstance(payload, dict):
            triggers = payload.get("video_triggers") or payload.get("triggers") or []
        else:
            triggers = []

        if not triggers:
            logger.warning("[REGISTRY] Payload contains 0 triggers; skipping catalog overwrite.")
            return {
                "status": "ignored_empty",
                "updated_count": 0,
                "total_library_videos": len(CLINICAL_VIDEO_REGISTRY),
                "message": "Payload contained no triggers; catalog preserved."
            }

        updated_ids = []
        for t in triggers:
            vid = t.get("video_id") or t.get("id")
            if not vid:
                continue
            updated_ids.append(vid)
            existing = CLINICAL_VIDEO_REGISTRY.get(vid, {})
            CLINICAL_VIDEO_REGISTRY[vid] = {
                "id": vid,
                "video_id": vid,
                "filename": t.get("filename", existing.get("filename", f"{vid}.mp4")),
                "title": t.get("title", existing.get("title", f"Video {vid}")),
                "category": t.get("category", existing.get("category", "General")),
                "subtopic": t.get("subtopic", existing.get("subtopic", "")),
                "duration_s": float(t.get("duration_s", existing.get("duration_s", 10.0))),
                "condition_logic": t.get("condition_logic", existing.get("condition_logic", "AND")).upper(),
                "clinical_priority": t.get("clinical_priority", existing.get("clinical_priority", "medium")).lower(),
                "reason": existing.get("reason", t.get("trigger_type", "AI clinical coaching")),
                "trigger_type": t.get("trigger_type", existing.get("trigger_type", "")),
                "trigger_conditions": t.get("trigger_conditions", existing.get("trigger_conditions", {})),
                "tags": t.get("tags", existing.get("tags", {})),
                "urls": t.get("urls", existing.get("urls", {})),
                "composability": t.get("composability", existing.get("composability", {})),
                "bucket": t.get("bucket", existing.get("bucket", "existing"))
            }

        DYNAMIC_CATALOG_STATE["last_synced"] = datetime.now(timezone.utc).isoformat()
        DYNAMIC_CATALOG_STATE["source"] = source
        if isinstance(payload, dict) and "summary" in payload and isinstance(payload["summary"], dict):
            DYNAMIC_CATALOG_STATE["summary"] = payload["summary"]
        else:
            DYNAMIC_CATALOG_STATE["summary"] = {
                "total_curated_videos": sum(1 for v in CLINICAL_VIDEO_REGISTRY.values() if v.get("bucket") != "generated"),
                "total_ai_videos": sum(1 for v in CLINICAL_VIDEO_REGISTRY.values() if v.get("bucket") == "generated"),
                "total_library_videos": len(CLINICAL_VIDEO_REGISTRY),
                "total_subtitle_tracks": len(CLINICAL_VIDEO_REGISTRY) * 2,
                "total_indexed_triggers": len(CLINICAL_VIDEO_REGISTRY)
            }
        DYNAMIC_CATALOG_STATE["video_triggers"] = triggers

        if persist and updated_ids:
            if isinstance(payload, dict) and ("triggers" in payload or "video_triggers" in payload):
                save_local_catalog_cache(payload)
            else:
                full_payload = {
                    "event": "clinical_video_catalog_update",
                    "sync_timestamp": DYNAMIC_CATALOG_STATE["last_synced"],
                    "summary": DYNAMIC_CATALOG_STATE["summary"],
                    "triggers": list(CLINICAL_VIDEO_REGISTRY.values())
                }
                save_local_catalog_cache(full_payload)

        logger.info(
            f"[AI SERVER] Updated video catalog: {len(updated_ids)} triggers updated, "
            f"{len(CLINICAL_VIDEO_REGISTRY)} total videos active in registry (source: {source})."
        )

        return {
            "status": "success",
            "updated_count": len(updated_ids),
            "total_curated_videos": DYNAMIC_CATALOG_STATE["summary"].get("total_curated_videos", len(CLINICAL_VIDEO_REGISTRY)),
            "total_library_videos": DYNAMIC_CATALOG_STATE["summary"].get("total_library_videos", len(CLINICAL_VIDEO_REGISTRY)),
            "sync_timestamp": DYNAMIC_CATALOG_STATE["last_synced"],
            "source": source
        }


def sync_video_catalog_from_vm(vm_url: Optional[str] = None, timeout: float = 3.0) -> Dict[str, Any]:
    """
    Option A: Dynamically fetches the latest trigger rules, metric thresholds,
    and video stream URLs from the Video VM Server (GET /api/triggers/catalog or /api/catalog/sync).
    Gracefully falls back to local distributed_trigger_catalog.json or static baseline registry.
    """
    target_base = (vm_url or VIDEO_SERVER_URL).rstrip("/")
    endpoints = [f"{target_base}/api/triggers/catalog", f"{target_base}/api/catalog/sync"]

    for ep in endpoints:
        try:
            resp = requests.get(ep, timeout=timeout)
            if resp.status_code == 200:
                payload = resp.json()
                res = update_catalog_from_payload(payload, persist=True, source="video_vm_sync")
                res["endpoint_used"] = ep
                logger.info(f"[AI SERVER] Successfully synced {res['updated_count']} triggers from Video VM via {ep}")
                return res
        except Exception as exc:
            logger.debug(f"[AI SERVER] Could not sync triggers from {ep}: {exc}")

    # Fallback to local distributed catalog cache if available
    local_res = load_local_catalog_cache()
    if local_res.get("updated_count", 0) > 0:
        logger.info("[AI SERVER] Video VM unreachable; loaded cached triggers from local distributed_trigger_catalog.json.")
        return {
            "status": "cached_fallback",
            "message": "Video VM unreachable; used local distributed trigger catalog cache.",
            "updated_count": local_res["updated_count"],
            "total_library_videos": DYNAMIC_CATALOG_STATE["summary"].get("total_library_videos", len(CLINICAL_VIDEO_REGISTRY)),
            "last_synced": DYNAMIC_CATALOG_STATE["last_synced"]
        }

    logger.warning("[AI SERVER WARN] Video VM unreachable and no local cache found; retaining static baseline registry.")
    return {
        "status": "fallback",
        "message": "Video VM unreachable; using local baseline registry.",
        "total_curated_videos": DYNAMIC_CATALOG_STATE["summary"].get("total_curated_videos", len(CLINICAL_VIDEO_REGISTRY)),
        "last_synced": DYNAMIC_CATALOG_STATE["last_synced"]
    }


# Automatically load cached distributed trigger catalog if present on disk
try:
    load_local_catalog_cache()
except Exception:
    pass


def get_clinical_video_catalog() -> list:
    """Return all clinical videos in registry as a list."""
    return list(CLINICAL_VIDEO_REGISTRY.values())


