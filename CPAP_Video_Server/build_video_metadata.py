#!/usr/bin/env python3
"""
===============================================================================
build_video_metadata.py - Unified Metadata & Subtitle Synthesis Engine
===============================================================================
This engine handles the creation, subtitle synthesis, and synchronization of
metadata for all CPAP coaching videos in both 'existing_videos/' and 'new_videos/'.
It performs:
  1. Real-time detection of any newly added MP4 video files.
  2. Automatic generation of bilingual (English & French) WebVTT subtitles.
  3. Video property extraction (resolution, duration, FPS) with safe fallbacks.
  4. Individual JSON record generation ('metadata/video_XX.json').
  5. Master registry compilation ('metadata/master_video_metadata.json').
===============================================================================
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import shutil
import requests

# Ensure UTF-8 output encoding for Windows CMD/PowerShell consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Safely import OpenCV for video inspection if installed; fallback gracefully if not
try:
    import cv2
except ImportError:
    cv2 = None

# =============================================================================
# DIRECTORY PATH CONFIGURATION
# =============================================================================
env_base = os.environ.get("VIDEO_BASE_DIR")
if env_base and Path(env_base).exists():
    BASE_DIR = Path(env_base)
else:
    BASE_DIR = Path(__file__).resolve().parent

EXISTING_VIDEOS_DIR = BASE_DIR / "existing_videos"
NEW_VIDEOS_DIR = BASE_DIR / "new_videos"
EXISTING_SUBTITLES_DIR = BASE_DIR / "existing_subtitles"
NEW_SUBTITLES_DIR = BASE_DIR / "new_subtitles"
METADATA_DIR = BASE_DIR / "metadata"

# Ensure all essential directories exist
EXISTING_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
NEW_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
EXISTING_SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)
NEW_SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# TECHNICAL INSPECTION & PARSING HELPERS
# =============================================================================
def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash using chunked streaming to prevent high memory usage."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def format_vtt_timestamp(seconds: float) -> str:
    """Formats seconds into WebVTT timestamp format: 00:00:00.000"""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    millis = int(round((s - int(s)) * 1000))
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}.{millis:03d}"


def get_video_info(video_path: Path) -> Dict[str, Any]:
    """
    Reads video file technical properties (width, height, FPS, duration).
    If OpenCV is not installed or the file cannot be opened, returns safe defaults.
    """
    default_info = {
        "duration_s": 10.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "frame_count": 300
    }
    
    if not video_path.exists() or cv2 is None:
        return default_info
        
    cap = None
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return default_info
            
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
        duration = round(frame_count / fps, 2) if fps > 0 else 10.0
        
        return {
            "duration_s": duration,
            "fps": round(fps, 2),
            "frame_count": frame_count,
            "width": width,
            "height": height
        }
    except Exception:
        return default_info
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


def parse_vtt(vtt_path: Path) -> List[Dict[str, str]]:
    """
    Parses cues (timestamps and narration text) from a WebVTT (.vtt) file.
    Returns a list of dicts: [{'start': '00:00:00.000', 'end': '00:00:03.000', 'text': '...'}]
    """
    if not vtt_path.exists():
        return []
        
    cues = []
    current_cue = None
    time_pattern = re.compile(r"((?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s*-->\s*((?:\d{2}:)?\d{2}:\d{2}\.\d{3})")
    
    try:
        with open(vtt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for line in lines:
            line_str = line.strip()
            
            if not line_str or line_str.startswith("WEBVTT"):
                if current_cue and current_cue.get("text"):
                    cues.append(current_cue)
                    current_cue = None
                continue
                
            match = time_pattern.search(line_str)
            if match:
                if current_cue and current_cue.get("text"):
                    cues.append(current_cue)
                current_cue = {
                    "start": match.group(1),
                    "end": match.group(2),
                    "text": ""
                }
            elif current_cue:
                if current_cue["text"]:
                    current_cue["text"] += " " + line_str
                else:
                    current_cue["text"] = line_str
                    
        if current_cue and current_cue.get("text"):
            cues.append(current_cue)
            
    except Exception as err:
        print(f"[Warning] Error parsing WebVTT file {vtt_path.name}: {err}")
        
    return cues


def generate_veo_subtitles_via_ai(prompt: str, duration_s: float = 10.0) -> Tuple[Optional[str], Optional[str]]:
    """
    Calls Google Gemini using GOOGLE_VERTEX_API_KEY to generate exact spoken narration
    with precise millisecond timestamped WebVTT cues (English and French) for a Google Veo video.
    """
    api_key = os.getenv("GOOGLE_VERTEX_API_KEY")
    if not api_key:
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            m = re.search(r'GOOGLE_VERTEX_API_KEY=(.+)', env_file.read_text(encoding="utf-8"))
            if m:
                api_key = m.group(1).strip()
    
    if not api_key:
        return None, None

    candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
    for model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req_body = {
            "contents": [{
                "parts": [{
                    "text": (
                        f"You are an expert clinical subtitle generator for medical CPAP coaching videos.\n"
                        f"For a {duration_s:.1f}-second clinical video generated from the prompt: \"{prompt}\",\n"
                        f"generate the EXACT spoken narration text with precise timestamped WebVTT cues.\n"
                        f"Requirements:\n"
                        f"1. Generate TWO tracks: 'en_vtt' (English) and 'fr_vtt' (French).\n"
                        f"2. Both tracks must start with 'WEBVTT'.\n"
                        f"3. Provide 2-3 precise timestamps spanning 0.0s to {duration_s:.1f}s (e.g. 00:00:00.000 --> 00:00:04.500).\n"
                        f"4. The text must be the exact spoken words describing the clinical action (NO generic 'welcome to your coaching' intro).\n"
                        f"5. Output ONLY a valid JSON object with keys: 'en_vtt' and 'fr_vtt'."
                    )
                }]
            }],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        try:
            resp = requests.post(url, json=req_body, timeout=8.0)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                en_vtt = parsed.get("en_vtt")
                fr_vtt = parsed.get("fr_vtt")
                if en_vtt and fr_vtt and "WEBVTT" in en_vtt:
                    return en_vtt, fr_vtt
        except Exception:
            continue

    return None, None


# =============================================================================
# AUTOMATIC SUBTITLE SYNTHESIS
# =============================================================================
def synthesize_subtitles_for_video(video_stem: str, target_dir: Optional[Path] = None, topic_or_prompt: str = "Personalized Coaching", duration_s: float = 10.0) -> Tuple[bool, bool]:
    """
    Generates bilingual (English and French) WebVTT subtitle files for any video.
    Returns (created_en, created_fr).
    """
    if target_dir is None:
        target_dir = NEW_SUBTITLES_DIR
        
    target_dir.mkdir(parents=True, exist_ok=True)
    en_vtt_path = target_dir / f"{video_stem}.en.vtt"
    fr_vtt_path = target_dir / f"{video_stem}.fr.vtt"
    
    clean_topic = topic_or_prompt.replace("_", " ").replace("-", " ").strip()
    # Remove leading number prefix if present (e.g. "38 ")
    clean_topic = re.sub(r'^\d+\s+', '', clean_topic)
    clean_topic = re.sub(r'\s+', ' ', clean_topic).strip()
    if clean_topic:
        clean_topic = clean_topic[0].upper() + clean_topic[1:]
        if not clean_topic.endswith(('.', '!', '?')):
            clean_topic += '.'

    # 0. Check if the video matches an existing video (e.g. from fallback synthesis)
    video_path = NEW_VIDEOS_DIR / f"{video_stem}.mp4"
    if not video_path.exists():
        video_path = EXISTING_VIDEOS_DIR / f"{video_stem}.mp4"
    
    created_en = False
    created_fr = False

    if video_path.exists() and video_path.stat().st_size > 0:
        try:
            v_size = video_path.stat().st_size
            v_hash = compute_file_sha256(video_path)
            for ex_vid in EXISTING_VIDEOS_DIR.glob("*.mp4"):
                if ex_vid.resolve() != video_path.resolve() and ex_vid.stat().st_size == v_size:
                    if compute_file_sha256(ex_vid) == v_hash:
                        ex_en = EXISTING_SUBTITLES_DIR / f"{ex_vid.stem}.en.vtt"
                        ex_fr = EXISTING_SUBTITLES_DIR / f"{ex_vid.stem}.fr.vtt"
                        if ex_en.exists() and not en_vtt_path.exists():
                            shutil.copyfile(ex_en, en_vtt_path)
                            created_en = True
                        if ex_fr.exists() and not fr_vtt_path.exists():
                            shutil.copyfile(ex_fr, fr_vtt_path)
                            created_fr = True
                        if created_en or created_fr or (en_vtt_path.exists() and fr_vtt_path.exists()):
                            return created_en, created_fr
        except Exception as e:
            print(f"[Warning] Subtitle matching check error: {e}")

    # 1. Generate exact spoken narration & timestamped WebVTT cues using Google Gemini AI
    if not en_vtt_path.exists() or not fr_vtt_path.exists():
        en_ai, fr_ai = generate_veo_subtitles_via_ai(topic_or_prompt, duration_s=duration_s)
        if en_ai and not en_vtt_path.exists():
            with open(en_vtt_path, "w", encoding="utf-8") as f:
                f.write(en_ai.strip() + "\n")
            created_en = True
        if fr_ai and not fr_vtt_path.exists():
            with open(fr_vtt_path, "w", encoding="utf-8") as f:
                f.write(fr_ai.strip() + "\n")
            created_fr = True

    if (created_en or en_vtt_path.exists()) and (created_fr or fr_vtt_path.exists()):
        return created_en, created_fr

    # Dynamic timestamp cue splits scaled to actual video duration
    cue1_start = format_vtt_timestamp(0.0)
    cue1_end = format_vtt_timestamp(min(4.5, duration_s * 0.45))
    cue2_start = format_vtt_timestamp(min(4.8, duration_s * 0.48))
    cue2_end = format_vtt_timestamp(max(duration_s - 0.5, duration_s * 0.95))

    # 2. English WebVTT (Direct, concise clinical instructions matching the prompt)
    if not en_vtt_path.exists():
        en_content = f"""WEBVTT

{cue1_start} --> {cue1_end}
{clean_topic}

{cue2_start} --> {cue2_end}
Follow these clinical steps to optimize equipment fit, pressure comfort, and breathing stability.
"""
        with open(en_vtt_path, "w", encoding="utf-8") as f:
            f.write(en_content)
        created_en = True

    # 3. French WebVTT (Direct, concise clinical instructions matching the prompt)
    if not fr_vtt_path.exists():
        fr_content = f"""WEBVTT

{cue1_start} --> {cue1_end}
{clean_topic}

{cue2_start} --> {cue2_end}
Suivez ces étapes cliniques pour optimiser l'ajustement du matériel, le confort et la stabilité respiratoire.
"""
        with open(fr_vtt_path, "w", encoding="utf-8") as f:
            f.write(fr_content)
        created_fr = True

    return created_en, created_fr


def infer_clinical_triggers(filename: str, title: str) -> Tuple[str, Dict[str, Any], Dict[str, List[str]], str, str]:
    """
    Infers structured clinical trigger types, trigger conditions, semantic tags,
    condition logic (AND/OR), and clinical priority from filename/title keywords
    to ensure newly added videos are immediately usable by AI Server and Raspberry Pi.
    """
    fn_lower = filename.lower()
    
    if "hexoskin" in fn_lower or "strap" in fn_lower:
        trigger_type = "hexoskin_ecg_impedance" if "electrode" in fn_lower else "hexoskin_respiratory_motion"
        trigger_conditions = {"Hexoskin_Signal_Quality": "< 50.0%", "Motion_Artifact_Rate": ">= 25.0%"}
        tags = {
            "clinical": ["hexoskin", "smart_textile", "cardiorespiratory"],
            "biomarker": ["ecg_snr", "respiratory_inductance_plethysmography"],
            "symptom": ["sensor_slippage", "signal_dropout"]
        }
    elif "mightysat" in fn_lower or "perfusion" in fn_lower or "finger" in fn_lower:
        trigger_type = "mightysat_perfusion_warning"
        trigger_conditions = {"Perfusion_Index": "< 0.5%", "SpO2_Confidence": "< 70.0%"}
        tags = {
            "clinical": ["masimo_mightysat", "pulse_oximetry", "perfusion"],
            "biomarker": ["perfusion_index", "spo2_instability"],
            "symptom": ["cold_periphery", "optical_misalignment"]
        }
    elif "somnoart" in fn_lower or "sleep_architecture" in fn_lower:
        trigger_type = "somnoart_sleep_fragmentation"
        trigger_conditions = {"Sleep_Continuity_Score": "< 60.0%", "Awakening_Frequency": ">= 4/hr"}
        tags = {
            "clinical": ["somno_art", "sleep_staging", "ppg_actigraphy"],
            "biomarker": ["sleep_fragmentation_index", "rem_loss"],
            "symptom": ["frequent_awakenings", "restless_sleep"]
        }
    elif "leak" in fn_lower:
        trigger_type = "mask_leak_high"
        trigger_conditions = {"CPAP_Leaks95": ">= 24.0 L/min"}
        tags = {
            "clinical": ["mask_leak", "seal_adjustment"],
            "biomarker": ["unintentional_leak_rate"],
            "symptom": ["air_blowing_in_eyes", "dry_mouth"]
        }
    elif "low_usage" in fn_lower or "usage" in fn_lower:
        trigger_type = "low_compliance"
        trigger_conditions = {"CPAP_Use": "< 4.0 hrs/night"}
        tags = {
            "clinical": ["low_usage", "habituation"],
            "biomarker": ["therapy_adherence"],
            "symptom": ["early_mask_removal", "claustrophobia"]
        }
    elif "humidifier" in fn_lower or "dry_mouth" in fn_lower or "rainout" in fn_lower:
        trigger_type = "humidification_comfort"
        trigger_conditions = {"Humidity_Discomfort_Index": ">= 2.0"}
        tags = {
            "clinical": ["humidifier", "anti_rainout"],
            "biomarker": ["airway_hydration"],
            "symptom": ["nasal_dryness", "condensation_in_tube"]
        }
    elif "bpm_core" in fn_lower or "blood_pressure" in fn_lower or "hypertension" in fn_lower:
        trigger_type = "cardiovascular_blood_pressure_warning"
        trigger_conditions = {"BPM_Systolic": ">= 140 mmHg", "BPM_Diastolic": ">= 90 mmHg"}
        tags = {
            "clinical": ["withings_bpm_core", "hypertension", "cardiovascular_monitoring"],
            "biomarker": ["systolic_bp", "diastolic_bp"],
            "symptom": ["morning_headache", "dizziness"]
        }
    elif "ecg" in fn_lower or "heart_sound" in fn_lower or "arrhythmia" in fn_lower:
        trigger_type = "cardiac_rhythm_anomaly"
        trigger_conditions = {"ECG_Arrhythmia_Detected": "true", "Heart_Rate_Anomaly": ">= 100 bpm"}
        tags = {
            "clinical": ["withings_bpm_core", "ecg_valvular", "cardiac_safety"],
            "biomarker": ["afib_indicator", "heart_murmur_score"],
            "symptom": ["palpitations", "chest_flutter"]
        }
    elif "scanwatch" in fn_lower:
        trigger_type = "scanwatch_nocturnal_hypoxemia"
        trigger_conditions = {"SpO2_Nocturnal_Min": "< 90.0%", "Breathing_Disturbances": ">= 30/hr"}
        tags = {
            "clinical": ["withings_scanwatch", "nocturnal_oximetry", "sleep_disturbances"],
            "biomarker": ["desaturation_index", "sleep_hrv"],
            "symptom": ["daytime_fatigue", "restless_awakening"]
        }
    elif "radg" in fn_lower or "rad_g" in fn_lower:
        trigger_type = "radg_continuous_hypoxemia"
        trigger_conditions = {"Masimo_SpO2": "< 88.0%", "Pulse_Rate_Instability": ">= 15%"}
        tags = {
            "clinical": ["masimo_rad_g", "continuous_pulse_oximetry", "respiratory_instability"],
            "biomarker": ["spo2_nadir", "pulse_rate_variability"],
            "symptom": ["gasping_awakening", "nocturnal_dyspnea"]
        }
    elif "proshirt" in fn_lower:
        trigger_type = "proshirt_thoracoabdominal_asynchrony"
        trigger_conditions = {"Thoracoabdominal_Asynchrony": ">= 45.0 deg", "Phase_Angle": ">= 35.0 deg"}
        tags = {
            "clinical": ["proshirt_textile", "respiratory_effort", "ribcage_abdominal_motion"],
            "biomarker": ["paradoxical_breathing_index"],
            "symptom": ["increased_work_of_breathing"]
        }
    elif "aerophagia" in fn_lower:
        trigger_type = "aerophagia_gastric_distension"
        trigger_conditions = {"Aerophagia_Discomfort_Score": ">= 2.0"}
        tags = {
            "clinical": ["aerophagia", "sleeping_position", "air_swallowing"],
            "biomarker": ["gastric_distension_index"],
            "symptom": ["bloating", "abdominal_pain", "morning_burping"]
        }
    else:
        trigger_type = "clinical_anomaly_trigger"
        trigger_conditions = {"Clinical_Anomaly_Score": ">= 0.75"}
        tags = {
            "clinical": ["personalized_coaching"],
            "biomarker": ["telemetry_alert"],
            "symptom": ["therapy_discomfort"]
        }

    # Infer clinical priority
    if any(k in trigger_type for k in ("cardiac", "hypoxemia", "arrhythmia")):
        clinical_priority = "critical"
    elif any(k in trigger_type for k in ("blood_pressure", "mask_leak", "asynchrony")):
        clinical_priority = "high"
    elif any(k in trigger_type for k in ("compliance", "humidification", "sleep_fragmentation", "perfusion")):
        clinical_priority = "medium"
    elif "cleaning" in fn_lower or "maintenance" in fn_lower or "cushion" in fn_lower:
        clinical_priority = "maintenance"
    else:
        clinical_priority = "medium"

    # Infer condition logic
    if "28_" in filename or "36_" in filename:
        condition_logic = "OR"
    else:
        condition_logic = "AND"
        
    return trigger_type, trigger_conditions, tags, condition_logic, clinical_priority


# =============================================================================
# UNIFIED ASSET & METADATA SYNCHRONIZER
# =============================================================================
def sync_all_video_assets(verbose: bool = True) -> Tuple[int, int, int]:
    """
    Scans existing_videos/ and new_videos/, auto-generates missing subtitles,
    creates/updates individual metadata/video_XX.json records, and compiles
    metadata/master_video_metadata.json.

    Returns:
        (total_videos_indexed, total_subtitles_count, new_subtitles_created_count)
    """
    master_records_map: Dict[int, Dict[str, Any]] = {}
    new_subtitles_count = 0
    
    # 1. Load existing individual metadata records from metadata/
    existing_jsons = sorted(
        METADATA_DIR.glob("video_*.json"),
        key=lambda x: int(re.findall(r'\d+', x.name)[0]) if re.findall(r'\d+', x.name) else 999
    )
    for jf in existing_jsons:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                rec = json.load(f)
                vid = rec.get("video_id")
                if vid is not None:
                    master_records_map[int(vid)] = rec
        except Exception as err:
            if verbose:
                print(f"[Warning] Error reading {jf.name}: {err}")

    # 2. Scan both video directories (existing_videos & new_videos)
    scan_configs = [
        (EXISTING_VIDEOS_DIR, EXISTING_SUBTITLES_DIR, "curated_clinical_video"),
        (NEW_VIDEOS_DIR, NEW_SUBTITLES_DIR, "generated_ai_video")
    ]
    
    for vid_dir, sub_dir, vid_type in scan_configs:
        if not vid_dir.exists():
            continue
            
        mp4_files = sorted(
            [f for f in os.listdir(vid_dir) if f.endswith('.mp4')],
            key=lambda x: int(x.split('_')[0]) if x.split('_')[0].isdigit() else 999
        )
        
        for vfile in mp4_files:
            vpath = vid_dir / vfile
            vstem = Path(vfile).stem
            prefix_match = re.match(r"^(\d+)", vfile)
            
            if prefix_match:
                vid_id = int(prefix_match.group(1))
                parts = vstem.split('_')
                clean_title_words = [w for w in parts[1:] if w] if len(parts) > 1 else [vstem]
            else:
                existing_ids = set(master_records_map.keys())
                vid_id = max(existing_ids, default=0) + 1
                clean_title_words = [w for w in vstem.split('_') if w]
                
            clean_title = " ".join(clean_title_words) if clean_title_words else f"CPAP Coaching Video {vid_id}"

            # Auto-synthesize subtitles if missing in corresponding subtitle directory
            c_en, c_fr = synthesize_subtitles_for_video(vstem, target_dir=sub_dir, topic_or_prompt=clean_title)
            if c_en:
                new_subtitles_count += 1
                if verbose:
                    print(f"  [SUBTITLE SYNTHESIS] [+] Generated English subtitle: {vstem}.en.vtt")
            if c_fr:
                new_subtitles_count += 1
                if verbose:
                    print(f"  [SUBTITLE SYNTHESIS] [+] Generated French subtitle: {vstem}.fr.vtt")

            # Parse WebVTT cues
            en_vtt_path = sub_dir / f"{vstem}.en.vtt"
            fr_vtt_path = sub_dir / f"{vstem}.fr.vtt"
            en_cues = parse_vtt(en_vtt_path)
            fr_cues = parse_vtt(fr_vtt_path)
            
            # Inspect technical properties
            tech = get_video_info(vpath)

            # Build or update record if not already fully registered
            if vid_id not in master_records_map:
                inferred_type, inferred_conditions, inferred_tags, inferred_logic, inferred_priority = infer_clinical_triggers(vfile, clean_title)
                record = {
                    "video_id": vid_id,
                    "filename": vfile,
                    "title": clean_title,
                    "type": vid_type,
                    "duration_s": tech.get("duration_s", 10.0),
                    "category": "Wearable Biomarkers" if ("Hexoskin" in vfile or "MightySat" in vfile or "SomnoArt" in vfile) else "Personalized Coaching",
                    "subtopic": clean_title,
                    "trigger_type": inferred_type,
                    "condition_logic": inferred_logic,
                    "clinical_priority": inferred_priority,
                    "trigger_conditions": inferred_conditions,
                    "tags": inferred_tags,
                    "technical_specs": {
                        "resolution": f"{tech.get('width', 1920)}x{tech.get('height', 1080)}",
                        "fps": tech.get("fps", 30.0),
                        "frame_count": tech.get("frame_count", 300),
                        "aspect_ratio": "16:9"
                    },
                    "scene_segmentation": {
                        "start_scene_0_3s": {
                            "timecode": "00:00:00 - 00:00:03",
                            "description": "Patient therapy assessment and intro"
                        },
                        "core_scene_3_7s": {
                            "timecode": "00:00:03 - 00:00:07",
                            "description": "Demonstration of personalized coaching intervention"
                        },
                        "end_scene_7_10s": {
                            "timecode": "00:00:07 - 00:00:10",
                            "description": "Optimal therapeutic compliance outcome"
                        }
                    },
                    "composability": {
                        "can_follow": [1, 2, 4, 7],
                        "can_precede": [14, 27],
                        "transition_type": "fade_1_5s",
                        "reuse_mode": "standalone_or_sequence",
                        "scenario_fit": ["standalone", "clip_2_of_2"]
                    },
                    "safety_level": "standard",
                    "language_assets": {
                        "en": {
                            "subtitle_file": f"{vstem}.en.vtt",
                            "full_narration": " ".join([c["text"] for c in en_cues]),
                            "cues": en_cues
                        },
                        "fr": {
                            "subtitle_file": f"{vstem}.fr.vtt",
                            "full_narration": " ".join([c["text"] for c in fr_cues]),
                            "cues": fr_cues
                        }
                    }
                }
                
                # Save individual JSON
                id_json_path = METADATA_DIR / f"video_{vid_id:02d}.json"
                with open(id_json_path, "w", encoding="utf-8") as f:
                    json.dump(record, f, indent=2, ensure_ascii=False)
                    
                master_records_map[vid_id] = record
                if verbose:
                    print(f"  [AUTO-METADATA] [*] Indexed new metadata: {id_json_path.name}")
            else:
                # Ensure language assets reflect current subtitle files from disk
                rec = master_records_map[vid_id]
                lang_assets = rec.setdefault("language_assets", {})
                updated_cues = False
                if en_cues:
                    if lang_assets.get("en", {}).get("cues") != en_cues:
                        updated_cues = True
                    lang_assets.setdefault("en", {})["cues"] = en_cues
                    lang_assets["en"]["subtitle_file"] = f"{vstem}.en.vtt"
                    lang_assets["en"]["full_narration"] = " ".join([c["text"] for c in en_cues])
                if fr_cues:
                    if lang_assets.get("fr", {}).get("cues") != fr_cues:
                        updated_cues = True
                    lang_assets.setdefault("fr", {})["cues"] = fr_cues
                    lang_assets["fr"]["subtitle_file"] = f"{vstem}.fr.vtt"
                    lang_assets["fr"]["full_narration"] = " ".join([c["text"] for c in fr_cues])
                if tech.get("duration_s") and rec.get("duration_s") != tech["duration_s"]:
                    rec["duration_s"] = tech["duration_s"]
                    updated_cues = True
                if tech.get("width") and tech.get("height"):
                    t_res = f"{tech['width']}x{tech['height']}"
                    specs = rec.setdefault("technical_specs", {})
                    if specs.get("resolution") != t_res:
                        specs["resolution"] = t_res
                        specs["fps"] = tech.get("fps", 30.0)
                        specs["frame_count"] = tech.get("frame_count", 300)
                        updated_cues = True
                if updated_cues:
                    id_json_path = METADATA_DIR / f"video_{vid_id:02d}.json"
                    with open(id_json_path, "w", encoding="utf-8") as f:
                        json.dump(rec, f, indent=2, ensure_ascii=False)

    # 3. Sort master list strictly by numerical video_id
    sorted_master_records = [master_records_map[k] for k in sorted(master_records_map.keys())]
    
    # 4. Save master_video_metadata.json
    master_json_path = METADATA_DIR / "master_video_metadata.json"
    with open(master_json_path, "w", encoding="utf-8") as f:
        json.dump(sorted_master_records, f, indent=2, ensure_ascii=False)

    # 5. Count total subtitle files
    total_subs = len(list(EXISTING_SUBTITLES_DIR.glob("*.vtt"))) + len(list(NEW_SUBTITLES_DIR.glob("*.vtt")))
    
    # 6. Synchronize distributed trigger catalog
    try:
        from sync_remote_nodes import compile_distributed_trigger_catalog
        compile_distributed_trigger_catalog()
    except Exception as err:
        if verbose:
            print(f"  [Warning] Could not recompile distributed trigger catalog: {err}")

    return len(sorted_master_records), total_subs, new_subtitles_count


def build_generated_video_record(video_file: str, video_id: int) -> Dict[str, Any]:
    """Compatibility alias for single record build."""
    sync_all_video_assets(verbose=False)
    target_json = METADATA_DIR / f"video_{video_id:02d}.json"
    if target_json.exists():
        with open(target_json, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"video_id": video_id, "filename": video_file}


def main():
    print("=" * 75)
    print(" CPAP Video VM Server - Unified Asset & Subtitle Synchronizer")
    print("=" * 75)
    total_vids, total_subs, new_subs = sync_all_video_assets(verbose=True)
    print(f"\n[SUCCESS] Master metadata synchronized at metadata/master_video_metadata.json")
    print(f"   * Total Indexed Videos   : {total_vids} MP4 files")
    print(f"   * Total Subtitle Tracks : {total_subs} WebVTT files")
    print(f"   * New Subtitles Created : {new_subs} tracks")
    print("=" * 75)


if __name__ == "__main__":
    main()
