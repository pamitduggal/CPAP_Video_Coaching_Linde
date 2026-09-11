import os
import json
import re
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import whisper
except ImportError:
    whisper = None

BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "existing_videos"
NEW_VIDEOS_DIR = BASE_DIR / "new_videos"
SUBTITLES_DIR = BASE_DIR / "generated_subtitles"
OUTPUT_DIR = BASE_DIR / "metadata"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Complete Clinical Registry for all 27 Videos
CLINICAL_REGISTRY = {
    1: {
        "title": "Adjust Mask Straps",
        "topic": "Mask & Equipment",
        "subtopic": "Strap Adjustment",
        "clinical_tags": ["mask_leak", "strap_adjustment", "air_leakage"],
        "biomarker_tags": ["cpap_leak"],
        "symptom_tags": ["air_hissing", "eye_irritation"],
        "trigger_conditions": {"CPAP_Leaks95": ">= 24.0", "CPAP_Leaks95_max": "< 30.0"},
        "visual_summary": "Patient sitting up tightening side mask straps evenly to reduce air leakage.",
        "start_scene": "Identifies mask leak issue and air escaping around cushion.",
        "core_scene": "Demonstrates pulling top and bottom headgear straps evenly.",
        "end_scene": "Shows properly fitted mask with comfortable seal.",
        "can_follow": [],
        "can_precede": [2, 3, 14],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    2: {
        "title": "Refit Mask While Lying Down",
        "topic": "Mask & Equipment",
        "subtopic": "Lying Down Refit",
        "clinical_tags": ["mask_leak", "lying_down_fit", "facial_contour"],
        "biomarker_tags": ["cpap_leak"],
        "symptom_tags": ["air_leak_in_bed"],
        "trigger_conditions": {"CPAP_Leaks95": ">= 30.0", "CPAP_Use": ">= 2.0"},
        "visual_summary": "Patient lying in bed refitting mask cushion to align with reclined facial contours.",
        "start_scene": "Shows patient in bed experiencing leak while lying down.",
        "core_scene": "Demonstrates unseating cushion and gently reseating while reclined.",
        "end_scene": "Confirms leak-free seal in actual sleeping posture.",
        "can_follow": [1, 3],
        "can_precede": [8, 14],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    3: {
        "title": "Cushion Cleaning Reminder",
        "topic": "Maintenance",
        "subtopic": "Cushion Hygiene",
        "clinical_tags": ["hygiene", "cushion_care", "facial_oils"],
        "biomarker_tags": ["cpap_adherence_good"],
        "symptom_tags": ["mask_slippage", "skin_redness"],
        "trigger_conditions": {"CPAP_Use": ">= 4.0", "CPAP_Leaks95": "< 10.0", "CPAP_AHI": "< 5.0"},
        "visual_summary": "Hand washing silicone mask cushion with mild soap and warm water.",
        "start_scene": "Displays facial oil buildup on mask cushion.",
        "core_scene": "Washing silicone cushion using warm water and gentle soap.",
        "end_scene": "Rinsing and wiping clean for optimal seal performance.",
        "can_follow": [1, 2],
        "can_precede": [],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    4: {
        "title": "Low Usage - Use Ramp Mode",
        "topic": "Tips & Tricks",
        "subtopic": "Pressure Ramp Feature",
        "clinical_tags": ["low_usage", "high_pressure_discomfort", "ramp_feature"],
        "biomarker_tags": ["cpap_use_low", "cpap_pressure_high"],
        "symptom_tags": ["unable_to_fall_asleep", "high_pressure_sensation"],
        "trigger_conditions": {"CPAP_Use": "> 0", "CPAP_Use_max": "< 4.0", "CPAP_Presure90": ">= 12.0"},
        "visual_summary": "Demonstrates pressing Ramp button on CPAP device to start therapy at lower initial pressure.",
        "start_scene": "Shows patient struggling with high initial airflow pressure.",
        "core_scene": "Pressing Ramp button on CPAP machine panel.",
        "end_scene": "Pressure gradually increases while patient comfortably falls asleep.",
        "can_follow": [5],
        "can_precede": [7, 9],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    5: {
        "title": "Low Usage - Daytime Practice",
        "topic": "Tips & Tricks",
        "subtopic": "Desensitization",
        "clinical_tags": ["zero_usage", "desensitization", "claustrophobia"],
        "biomarker_tags": ["cpap_use_zero"],
        "symptom_tags": ["anxiety", "mask_aversion"],
        "trigger_conditions": {"CPAP_Use": "== 0.0"},
        "visual_summary": "Patient sitting awake reading a book while wearing CPAP mask to acclimate.",
        "start_scene": "Introduces daytime desensitization strategy while awake.",
        "core_scene": "Wearing mask while watching TV or reading for 20-30 minutes.",
        "end_scene": "Builds familiarity and reduces nighttime anxiety.",
        "can_follow": [],
        "can_precede": [4, 6],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    6: {
        "title": "Early Mask Removal",
        "topic": "Tips & Tricks",
        "subtopic": "Sleep Continuity",
        "clinical_tags": ["early_removal", "unconscious_removal", "sleep_fragmentation"],
        "biomarker_tags": ["cpap_use_low"],
        "symptom_tags": ["waking_up_without_mask"],
        "trigger_conditions": {"CPAP_Use": "> 0", "CPAP_Use_max": "< 4.0", "CPAP_Presure90": "< 12.0"},
        "visual_summary": "Addresses taking mask off mid-night and tips to keep it on longer.",
        "start_scene": "Illustrates waking up in middle of night and taking off mask.",
        "core_scene": "Setting an alarm to re-fit mask or putting tape on headgear straps.",
        "end_scene": "Extending therapy duration past 4-hour clinical threshold.",
        "can_follow": [5],
        "can_precede": [17, 27],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    7: {
        "title": "Dry Mouth - Use Humidifier",
        "topic": "Comfort",
        "subtopic": "Heated Humidification",
        "clinical_tags": ["dry_mouth", "humidifier_setting", "airway_dryness"],
        "biomarker_tags": ["cpap_leak_mild"],
        "symptom_tags": ["dry_throat", "parched_mouth"],
        "trigger_conditions": {"CPAP_Leaks95": ">= 10.0", "CPAP_Leaks95_max": "< 24.0", "CPAP_Presure90": ">= 10.0"},
        "visual_summary": "Filling CPAP water chamber with distilled water and raising humidity level.",
        "start_scene": "Patient experiencing dry mouth upon waking.",
        "core_scene": "Filling humidifier tub with distilled water and increasing heat setting.",
        "end_scene": "Moisturized air delivery preventing throat dryness.",
        "can_follow": [4, 8, 9],
        "can_precede": [8],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    8: {
        "title": "Mouth Breathing - Chin Support",
        "topic": "Mask & Equipment",
        "subtopic": "Mouth Leak Control",
        "clinical_tags": ["mouth_breathing", "chin_strap", "oral_leak"],
        "biomarker_tags": ["cpap_leak_severe"],
        "symptom_tags": ["open_mouth_sleeping", "dry_mouth"],
        "trigger_conditions": {"CPAP_Leaks95": ">= 30.0", "CPAP_Use": "< 2.0"},
        "visual_summary": "Fitting a soft chin strap or full face mask to prevent open-mouth air escaping.",
        "start_scene": "Shows mouth dropping open under CPAP pressure.",
        "core_scene": "Applying a chin strap or switching to a full face mask.",
        "end_scene": "Keeps mouth closed to maintain therapeutic pressure.",
        "can_follow": [1, 2, 7],
        "can_precede": [14],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    9: {
        "title": "Nasal Congestion Relief",
        "topic": "Comfort",
        "subtopic": "Nasal Hygiene",
        "clinical_tags": ["nasal_congestion", "saline_spray", "resistance"],
        "biomarker_tags": ["cpap_leak_mild"],
        "symptom_tags": ["stuffy_nose", "nasal_blockage"],
        "trigger_conditions": {"CPAP_Leaks95": ">= 10.0", "CPAP_Leaks95_max": "< 24.0", "CPAP_Presure90": "< 10.0"},
        "visual_summary": "Using saline spray before bedtime to clear nasal passages before CPAP therapy.",
        "start_scene": "Patient suffering from blocked nose before sleep.",
        "core_scene": "Using sterile saline nasal spray to clear nasal airways.",
        "end_scene": "Clear nasal breathing with comfortable CPAP air flow.",
        "can_follow": [4, 5],
        "can_precede": [7],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    10: {
        "title": "Aerophagia - Elevate Head",
        "topic": "Tips & Tricks",
        "subtopic": "Sleeping Position",
        "clinical_tags": ["aerophagia", "air_swallowing", "head_elevation"],
        "biomarker_tags": ["cpap_pressure_high"],
        "symptom_tags": ["stomach_bloating", "gas", "abdominal_discomfort"],
        "trigger_conditions": {"CPAP_Presure90": ">= 13.0", "CPAP_Leaks95": "< 10.0", "CPAP_AHI": "< 5.0"},
        "visual_summary": "Elevating head with extra pillow or wedge to prevent air entering stomach.",
        "start_scene": "Patient waking with stomach bloating due to swallowed air.",
        "core_scene": "Adjusting pillow to elevate head and upper torso 30 degrees.",
        "end_scene": "Aligns esophagus and airway to prevent aerophagia.",
        "can_follow": [4],
        "can_precede": [11],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    11: {
        "title": "Aerophagia - Side Sleeping",
        "topic": "Tips & Tricks",
        "subtopic": "Side Sleeping Posture",
        "clinical_tags": ["aerophagia", "side_sleeping", "positional_therapy"],
        "biomarker_tags": ["cpap_pressure_high", "cpap_ahi_elevated"],
        "symptom_tags": ["bloating", "gas", "air_swallowing"],
        "trigger_conditions": {"CPAP_Presure90": ">= 13.0", "CPAP_Leaks95": "< 10.0", "CPAP_AHI": ">= 5.0"},
        "visual_summary": "Rolling onto side with body pillow to lower required pressure and swallow less air.",
        "start_scene": "Shows back sleeping position causing airway collapse and high pressure.",
        "core_scene": "Transitioning to side sleeping position supported by pillow.",
        "end_scene": "Reduces airway obstruction and air swallowing.",
        "can_follow": [10],
        "can_precede": [12],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    12: {
        "title": "High Breathing Events - Contact Provider",
        "topic": "Clinical Alerts",
        "subtopic": "Apnea Index Elevation",
        "clinical_tags": ["high_ahi", "residual_apnea", "clinical_escalation"],
        "biomarker_tags": ["cpap_ahi_high"],
        "symptom_tags": ["gasping", "daytime_fatigue"],
        "trigger_conditions": {"CPAP_AHI": ">= 15.0", "CPAP_Use": ">= 3.0"},
        "visual_summary": "High AHI alert screen recommending consultation with healthcare provider for pressure adjustment.",
        "start_scene": "Alert displaying elevated Apnea-Hypopnea Index count.",
        "core_scene": "Explains residual apnea events despite wearing mask.",
        "end_scene": "Prompts patient to contact sleep doctor or homecare technician.",
        "can_follow": [1, 2, 11],
        "can_precede": [13, 15],
        "transition_type": "fade_1_5s",
        "safety_level": "clinical_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    13: {
        "title": "Biomarker Changes - Use CPAP & Contact Provider",
        "topic": "Clinical Alerts",
        "subtopic": "Biomarker Anomaly",
        "clinical_tags": ["biomarker_anomaly", "poor_adherence", "high_ahi"],
        "biomarker_tags": ["cpap_ahi_high", "cpap_use_low"],
        "symptom_tags": ["severe_exhaustion", "morning_headache"],
        "trigger_conditions": {"CPAP_AHI": ">= 15.0", "CPAP_Use": "< 3.0"},
        "visual_summary": "Dual warning for high AHI combined with low usage, urging consistent CPAP therapy.",
        "start_scene": "Highlights combined high AHI and insufficient nightly usage.",
        "core_scene": "Emphasizes health risk of untreated sleep apnea.",
        "end_scene": "Directs patient to wear mask full night and call homecare provider.",
        "can_follow": [5, 6, 12],
        "can_precede": [15, 16, 19],
        "transition_type": "fade_1_5s",
        "safety_level": "clinical_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2", "existing_plus_generated"]
    },
    14: {
        "title": "Mask Style Change Needed",
        "topic": "Mask & Equipment",
        "subtopic": "Alternative Mask Fit",
        "clinical_tags": ["unresolved_leak", "mask_type_change", "nasal_vs_fullface"],
        "biomarker_tags": ["cpap_leak_critical"],
        "symptom_tags": ["persistent_leak", "facial_soreness"],
        "trigger_conditions": {"CPAP_Leaks95": ">= 40.0"},
        "visual_summary": "Comparing nasal pillow, nasal mask, and full face mask options for severe leak cases.",
        "start_scene": "Displays extreme leak warning despite strap adjustments.",
        "core_scene": "Reviewing alternative mask styles (nasal vs full-face).",
        "end_scene": "Recommends contacting homecare clinician for mask swap.",
        "can_follow": [1, 2, 8],
        "can_precede": [15],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    15: {
        "title": "Severe Apnea - Contact Your Provider",
        "topic": "Clinical Alerts",
        "subtopic": "Urgent Clinical Escalation",
        "clinical_tags": ["critical_ahi", "urgent_care", "physician_review"],
        "biomarker_tags": ["cpap_ahi_critical"],
        "symptom_tags": ["extreme_hypoxia", "severe_gasping"],
        "trigger_conditions": {"CPAP_AHI": ">= 30.0"},
        "visual_summary": "Urgent Red Alert urging immediate consultation with clinical physician.",
        "start_scene": "Red alert banner indicating severe apnea index level (AHI >= 30).",
        "core_scene": "Stresses importance of medical consultation for safety.",
        "end_scene": "Displays direct provider contact button and emergency phone line.",
        "can_follow": [12, 13, 14, 16, 19, 22],
        "can_precede": [],
        "transition_type": "fade_1_5s",
        "safety_level": "critical_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    16: {
        "title": "ScanWatch - Low Nighttime Oxygen",
        "topic": "Wearable Biomarkers",
        "subtopic": "Nocturnal Hypoxemia (ScanWatch)",
        "clinical_tags": ["scanwatch", "spo2_drop", "nocturnal_hypoxemia"],
        "biomarker_tags": ["scanwatch_spo2_low", "cpap_use_low"],
        "symptom_tags": ["morning_fog", "shortness_of_breath"],
        "trigger_conditions": {"ScanWatch_SpO2": "< 90.0", "CPAP_Use": "< 4.0"},
        "visual_summary": "ScanWatch smartwatch graph showing nighttime SpO2 drops below normal range.",
        "start_scene": "ScanWatch display showing nocturnal SpO2 dips below 90%.",
        "core_scene": "Explains link between missing CPAP hours and oxygen desaturation.",
        "end_scene": "Advises wearing CPAP continuously to stabilize oxygen.",
        "can_follow": [1, 4, 6],
        "can_precede": [12, 13, 15, 22],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2", "existing_plus_generated"]
    },
    17: {
        "title": "ScanWatch - Fragmented Sleep",
        "topic": "Wearable Biomarkers",
        "subtopic": "Sleep Micro-arousals (ScanWatch)",
        "clinical_tags": ["scanwatch", "sleep_fragmentation", "arousals"],
        "biomarker_tags": ["scanwatch_fragmentation_high"],
        "symptom_tags": ["restless_sleep", "frequent_waking"],
        "trigger_conditions": {"ScanWatch_MicroArousals": ">= 15/hr"},
        "visual_summary": "Sleep timeline showing repeated night awakenings and restless sleep movement.",
        "start_scene": "ScanWatch hypnogram showing frequent nighttime awakenings.",
        "core_scene": "Shows how mask leaks or high pressure trigger micro-arousals.",
        "end_scene": "Suggests checking mask fit and bedroom sleep hygiene.",
        "can_follow": [1, 6],
        "can_precede": [26, 27],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    18: {
        "title": "ScanWatch - Unusual Heart Rhythm Signal",
        "topic": "Wearable Biomarkers",
        "subtopic": "Cardiac Rhythm Anomaly (ScanWatch)",
        "clinical_tags": ["scanwatch", "heart_rate_variability", "arrhythmia_signal"],
        "biomarker_tags": ["scanwatch_hrv_anomaly"],
        "symptom_tags": ["palpitations", "chest_flutter"],
        "trigger_conditions": {"ScanWatch_ECG_Anomaly": "True"},
        "visual_summary": "Smartwatch ECG trace flagging pulse irregular intervals during sleep.",
        "start_scene": "ScanWatch notification showing irregular heart rhythm signal.",
        "core_scene": "Illustrates how sleep apnea stresses cardiovascular system.",
        "end_scene": "Recommends sharing watch ECG recording with physician.",
        "can_follow": [16, 17],
        "can_precede": [19, 20, 21],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2", "existing_plus_generated"]
    },
    19: {
        "title": "BPM Core - High Blood Pressure",
        "topic": "Wearable Biomarkers",
        "subtopic": "Hypertension Warning (BPM Core)",
        "clinical_tags": ["bpm_core", "hypertension", "blood_pressure"],
        "biomarker_tags": ["bpm_core_sys_high"],
        "symptom_tags": ["morning_headache", "chest_tightness"],
        "trigger_conditions": {"BPMCore_Systolic": ">= 140.0"},
        "visual_summary": "Withings BPM Core device displaying high blood pressure reading after waking.",
        "start_scene": "BPM Core monitor displaying elevated blood pressure (>=140 mmHg).",
        "core_scene": "Correlates untreated sleep apnea with morning hypertension.",
        "end_scene": "Encourages daily BP logging and strict CPAP compliance.",
        "can_follow": [4, 6, 13, 16],
        "can_precede": [15, 20, 21],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    20: {
        "title": "BPM Core - Irregular ECG Alert",
        "topic": "Wearable Biomarkers",
        "subtopic": "Electrocardiogram Anomaly (BPM Core)",
        "clinical_tags": ["bpm_core", "ecg_irregular", "atrial_fibrillation_risk"],
        "biomarker_tags": ["bpm_core_ecg_afib"],
        "symptom_tags": ["racing_heart", "dizziness"],
        "trigger_conditions": {"BPMCore_ECG_Status": "Afib_Risk"},
        "visual_summary": "BPM Core ECG waveform highlighting irregular rhythm detection.",
        "start_scene": "BPM Core digital display alerting irregular ECG rhythm.",
        "core_scene": "Shows 3-lead ECG wave recording with fluctuating intervals.",
        "end_scene": "Advises sending ECG PDF report to cardiologist.",
        "can_follow": [18, 19],
        "can_precede": [15, 21],
        "transition_type": "fade_1_5s",
        "safety_level": "critical_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    21: {
        "title": "BPM Core - Heart Sound Review Needed",
        "topic": "Wearable Biomarkers",
        "subtopic": "Digital Stethoscope Assessment (BPM Core)",
        "clinical_tags": ["bpm_core", "valvular_sound", "digital_stethoscope"],
        "biomarker_tags": ["bpm_core_stethoscope_alert"],
        "symptom_tags": ["heart_murmur_signal", "fatigue"],
        "trigger_conditions": {"BPMCore_Stethoscope": "Review_Required"},
        "visual_summary": "Digital stethoscope icon on BPM Core indicating heart sound analysis complete.",
        "start_scene": "Stethoscope indicator flashing on BPM Core device.",
        "core_scene": "Explains acoustic sensor listening to heart valve sound patterns.",
        "end_scene": "Prompts user to sync device with clinical portal for physician review.",
        "can_follow": [19, 20],
        "can_precede": [15],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    22: {
        "title": "RadG - Low Oxygen Reading",
        "topic": "Wearable Biomarkers",
        "subtopic": "Pulse Oximetry Alert (RadG)",
        "clinical_tags": ["radg", "pulse_oximetry", "spo2_low"],
        "biomarker_tags": ["radg_spo2_low"],
        "symptom_tags": ["cyanosis_risk", "shortness_of_breath"],
        "trigger_conditions": {"RadG_SpO2": "< 88.0"},
        "visual_summary": "RadG medical pulse oximeter sensor showing low SpO2 percentage reading.",
        "start_scene": "RadG bedside monitor showing SpO2 reading dropping below 88%.",
        "core_scene": "Demonstrates continuous real-time blood oxygen monitoring.",
        "end_scene": "Recommends verifying sensor placement and ensuring CPAP airflow.",
        "can_follow": [1, 2, 16],
        "can_precede": [15, 23],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2", "existing_plus_generated"]
    },
    23: {
        "title": "RadG - Pulse or Breathing Instability",
        "topic": "Wearable Biomarkers",
        "subtopic": "Hemodynamic Instability (RadG)",
        "clinical_tags": ["radg", "pulse_variability", "respiratory_instability"],
        "biomarker_tags": ["radg_pr_instability"],
        "symptom_tags": ["rapid_pulse", "irregular_breathing"],
        "trigger_conditions": {"RadG_PR_Variability": "High"},
        "visual_summary": "RadG screen displaying fluctuating pulse rate and respiration graphs.",
        "start_scene": "RadG graph displaying erratic pulse rate spikes.",
        "core_scene": "Correlates pulse instability with obstructive apnea events.",
        "end_scene": "Advises patient to rest and notify homecare manager.",
        "can_follow": [22],
        "can_precede": [12, 15],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    24: {
        "title": "ProShirt - Breathing Pattern Changed",
        "topic": "Wearable Biomarkers",
        "subtopic": "Thoraco-Abdominal Kinematics (ProShirt)",
        "clinical_tags": ["proshirt", "respiratory_effort", "paradoxical_breathing"],
        "biomarker_tags": ["proshirt_effort_high"],
        "symptom_tags": ["chest_strain", "labored_breathing"],
        "trigger_conditions": {"ProShirt_Asynchrony": "> 30%"},
        "visual_summary": "Smart textile garment with textile sensors showing respiratory effort shifts.",
        "start_scene": "ProShirt animation highlighting chest and abdominal expansion sensors.",
        "core_scene": "Detects paradoxical breathing effort during obstructive airway events.",
        "end_scene": "Confirms need for continuous pressure therapy to stabilize breathing.",
        "can_follow": [4, 6],
        "can_precede": [25, 26],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    25: {
        "title": "ProShirt - Fit Check",
        "topic": "Wearable Biomarkers",
        "subtopic": "Smart Garment Positioning (ProShirt)",
        "clinical_tags": ["proshirt", "sensor_alignment", "garment_fit"],
        "biomarker_tags": ["proshirt_signal_noise"],
        "symptom_tags": ["loose_garment", "signal_loss"],
        "trigger_conditions": {"ProShirt_SignalQuality": "< 70%"},
        "visual_summary": "Adjusting ProShirt smart garment straps for optimal sensor contact against skin.",
        "start_scene": "ProShirt alert indicating poor sensor contact or signal noise.",
        "core_scene": "Adjusting garment zipper and alignment over chest.",
        "end_scene": "Signal quality indicator turns green confirming proper sensor fit.",
        "can_follow": [24],
        "can_precede": [],
        "transition_type": "fade_1_5s",
        "safety_level": "standard",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    },
    26: {
        "title": "SomnoArt - Sleep Architecture Changed",
        "topic": "Wearable Biomarkers",
        "subtopic": "Sleep Staging & REM Reduction (SomnoArt)",
        "clinical_tags": ["somnoart", "rem_reduction", "deep_sleep_loss"],
        "biomarker_tags": ["somnoart_rem_low"],
        "symptom_tags": ["daytime_sleepiness", "memory_fog"],
        "trigger_conditions": {"SomnoArt_REM_Pct": "< 12.0"},
        "visual_summary": "SomnoArt hypnogram chart showing reduced REM and slow-wave deep sleep stages.",
        "start_scene": "SomnoArt clinical hypnogram showing absence of deep REM sleep cycles.",
        "core_scene": "Explains how sleep apnea micro-arousals suppress restorative REM sleep.",
        "end_scene": "Encourages consistent CPAP use to restore natural sleep architecture.",
        "can_follow": [6, 17, 24],
        "can_precede": [27],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_1_of_2"]
    },
    27: {
        "title": "SomnoArt - Poor Sleep Continuity",
        "topic": "Wearable Biomarkers",
        "subtopic": "Sleep Efficiency Index (SomnoArt)",
        "clinical_tags": ["somnoart", "sleep_efficiency", "insomnia_co_morbidity"],
        "biomarker_tags": ["somnoart_efficiency_low"],
        "symptom_tags": ["frequent_awakenings", "unrefreshing_sleep"],
        "trigger_conditions": {"SomnoArt_SleepEfficiency": "< 75.0%"},
        "visual_summary": "SomnoArt sleep report highlighting low sleep efficiency score.",
        "start_scene": "SomnoArt report displaying low overall sleep efficiency (<75%).",
        "core_scene": "Identifies frequent awakening periods throughout the night.",
        "end_scene": "Recommends optimizing CPAP humidity, mask comfort, and sleep schedule.",
        "can_follow": [6, 17, 26],
        "can_precede": [15],
        "transition_type": "fade_1_5s",
        "safety_level": "biomarker_alert",
        "reuse_mode": "standalone_or_sequence",
        "scenario_fit": ["standalone", "clip_2_of_2"]
    }
}

def parse_vtt(vtt_path):
    """Parses VTT files into cue segments with timestamps and text."""
    cues = []
    if not os.path.exists(vtt_path):
        return cues
    
    with open(vtt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_cue = None
    for line in lines:
        line = line.strip()
        if "-->" in line:
            parts = line.split("-->")
            start = parts[0].strip()
            end = parts[1].strip()
            current_cue = {"start": start, "end": end, "text": ""}
        elif current_cue and line and not line.startswith("WEBVTT"):
            if current_cue["text"]:
                current_cue["text"] += " " + line
            else:
                current_cue["text"] = line
            if current_cue not in cues:
                cues.append(current_cue)
    return cues

def get_video_info(video_path):
    """Extracts resolution, fps, duration, and samples 3 frames using OpenCV."""
    if cv2 is None:
        return {
            "fps": 30.0,
            "frame_count": 300,
            "duration_s": 10.0,
            "width": 1920,
            "height": 1080,
            "status": "default_no_cv2"
        }

    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {"status": "error", "duration_s": 10.0, "width": 1920, "height": 1080}
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_s = round(frame_count / fps, 2) if fps > 0 else 10.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        cap.release()
        return {
            "fps": fps,
            "frame_count": frame_count,
            "duration_s": duration_s,
            "width": width,
            "height": height
        }
    except Exception as e:
        return {"status": f"error: {e}", "duration_s": 10.0, "width": 1920, "height": 1080}

def main():
    print("Starting Metadata Generation for 27 Videos...")
    
    # Load whisper model for transcription verification
    print("Loading Whisper model (base)...")
    model = None
    if whisper is not None:
        try:
            model = whisper.load_model("base")
        except Exception as e:
            print(f"Warning loading Whisper: {e}")

    master_list = []
    
    # Find all mp4 files in VIDEOS_DIR
    video_files = sorted([f for f in os.listdir(VIDEOS_DIR) if f.endswith('.mp4')])
    
    for vfile in video_files:
        # Extract video ID from prefix
        prefix_str = vfile.split('_')[0]
        try:
            vid_id = int(prefix_str)
        except ValueError:
            continue
            
        video_path = VIDEOS_DIR / vfile
        print(f"\nProcessing Video {vid_id}: {vfile}")
        
        # 1. OpenCV Analysis
        tech_info = get_video_info(video_path)
        
        # 2. Whisper Transcription
        audio_transcript_whisper = ""
        if model:
            try:
                res = model.transcribe(str(video_path))
                audio_transcript_whisper = res.get("text", "").strip()
                print(f"  -> Whisper Transcript: '{audio_transcript_whisper}'")
            except Exception as e:
                print(f"  -> Whisper extraction error: {e}")
                
        # 3. Subtitle VTT Parsing
        base_name = vfile.replace(".mp4", "")
        en_vtt_path = SUBTITLES_DIR / f"{base_name}.en.vtt"
        fr_vtt_path = SUBTITLES_DIR / f"{base_name}.fr.vtt"
        
        en_cues = parse_vtt(en_vtt_path)
        fr_cues = parse_vtt(fr_vtt_path)
        
        full_en_text = " ".join([c["text"] for c in en_cues])
        full_fr_text = " ".join([c["text"] for c in fr_cues])
        
        # 4. Clinical Registry Lookup
        clinical_data = CLINICAL_REGISTRY.get(vid_id, {})
        
        # Build standard metadata schema
        meta_record = {
            "video_id": vid_id,
            "filename": vfile,
            "title": clinical_data.get("title", base_name),
            "duration_s": tech_info.get("duration_s", 10.0),
            "technical": tech_info,
            "topic": clinical_data.get("topic", "CPAP Therapy"),
            "subtopic": clinical_data.get("subtopic", "General"),
            "clinical_tags": clinical_data.get("clinical_tags", []),
            "biomarker_tags": clinical_data.get("biomarker_tags", []),
            "symptom_tags": clinical_data.get("symptom_tags", []),
            "trigger_conditions": clinical_data.get("trigger_conditions", {}),
            "visual_summary": clinical_data.get("visual_summary", ""),
            "narration_summary": full_en_text if full_en_text else audio_transcript_whisper,
            "whisper_audio_transcript": audio_transcript_whisper,
            "scene_segmentation": {
                "start_scene_0_3s": {
                    "timecode": "00:00:00 - 00:00:03",
                    "description": clinical_data.get("start_scene", "")
                },
                "core_scene_3_7s": {
                    "timecode": "00:00:03 - 00:00:07",
                    "description": clinical_data.get("core_scene", "")
                },
                "end_scene_7_10s": {
                    "timecode": "00:00:07 - 00:00:10",
                    "description": clinical_data.get("end_scene", "")
                }
            },
            "composability": {
                "can_follow": clinical_data.get("can_follow", []),
                "can_precede": clinical_data.get("can_precede", []),
                "transition_type": clinical_data.get("transition_type", "fade_1_5s"),
                "reuse_mode": clinical_data.get("reuse_mode", "standalone_or_sequence"),
                "scenario_fit": clinical_data.get("scenario_fit", ["standalone"])
            },
            "safety_level": clinical_data.get("safety_level", "standard"),
            "language_assets": {
                "en": {
                    "subtitle_file": f"{base_name}.en.vtt",
                    "full_narration": full_en_text,
                    "cues": en_cues
                },
                "fr": {
                    "subtitle_file": f"{base_name}.fr.vtt",
                    "full_narration": full_fr_text,
                    "cues": fr_cues
                }
            }
        }
        
        # Save individual JSON
        out_json_path = OUTPUT_DIR / f"video_{vid_id:02d}.json"
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(meta_record, f, indent=2, ensure_ascii=False)
            
        master_list.append(meta_record)
        print(f"  -> Saved metadata to {out_json_path}")

    # Process any dynamically generated videos in NEW_VIDEOS_DIR
    if NEW_VIDEOS_DIR.exists():
        new_video_files = sorted([f for f in os.listdir(NEW_VIDEOS_DIR) if f.endswith('.mp4')])
        for nvfile in new_video_files:
            nv_path = NEW_VIDEOS_DIR / nvfile
            print(f"\nProcessing Generated Video: {nvfile}")
            nv_tech = get_video_info(nv_path)
            
            nv_record = {
                "filename": nvfile,
                "type": "generated_ai_video",
                "duration_s": nv_tech.get("duration_s", 10.0),
                "technical": nv_tech,
                "topic": "AI Generated Coaching",
                "subtopic": "Customized Patient Synthesis",
                "safety_level": "generated_review"
            }
            nv_json_path = OUTPUT_DIR / f"{Path(nvfile).stem}.json"
            with open(nv_json_path, "w", encoding="utf-8") as f:
                json.dump(nv_record, f, indent=2, ensure_ascii=False)
            master_list.append(nv_record)
            print(f"  -> Saved generated metadata to {nv_json_path}")
        
    # Save master JSON
    master_json_path = OUTPUT_DIR / "master_video_metadata.json"
    with open(master_json_path, "w", encoding="utf-8") as f:
        json.dump(master_list, f, indent=2, ensure_ascii=False)
        
    print(f"\nSUCCESS: Generated metadata files and master registry at {master_json_path} (Total indexed: {len(master_list)})")

if __name__ == "__main__":
    main()
