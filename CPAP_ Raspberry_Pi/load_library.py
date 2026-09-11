"""
OSA-IVC — Library loader + matcher for Scenarios 1, 2, and 3
--------------------------------------------------------------
Reads all 27 metadata JSON files, builds an in-memory lookup, and matches
incoming events to:
- Scenario 1: Single existing video asset (10s)
- Scenario 2: Combination of 2 existing videos with 1.5s fade transition (~20s)
- Scenario 3: Hybrid existing video + Google Vertex AI dynamic generation request
"""

import json
import os
import glob
from pathlib import Path

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GOOGLE_VERTEX_API_KEY = os.environ.get("GOOGLE_VERTEX_API_KEY", "")
DEFAULT_LANGUAGE = "en"


def load_library(root: str = "metadata") -> dict:
    """
    Scans metadata JSON files (either in root directly or root/metadata/*.json)
    and builds an in-memory registry indexed by video_id, trigger_type, and clinical_tags.
    """
    possible_paths = [
        os.path.join(root, "*.json"),
        os.path.join(root, "metadata", "*.json"),
        os.path.join("metadata", "*.json")
    ]
    
    files = []
    for pattern in possible_paths:
        matched = glob.glob(pattern)
        if matched:
            files.extend(matched)
            
    files = sorted(list(set(files)))
    
    by_video_id = {}
    by_trigger = {}
    by_tag = {}

    for path in files:
        if "master_video_metadata.json" in path:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                
            vid_id = meta.get("video_id")
            if not vid_id:
                continue
                
            by_video_id[vid_id] = meta
            
            # Map by trigger_type / filename stem
            filename_stem = meta.get("filename", "").replace(".mp4", "")
            by_trigger[filename_stem] = meta
            by_trigger[str(vid_id)] = meta
            
            # Map by clinical and biomarker tags
            for tag in meta.get("clinical_tags", []) + meta.get("biomarker_tags", []):
                if tag not in by_tag:
                    by_tag[tag] = []
                by_tag[tag].append(meta)
                
        except Exception as e:
            print(f"Error loading metadata JSON {path}: {e}")

    print(f"Library Loader: Successfully indexed {len(by_video_id)} video metadata records.")
    return {
        "by_video_id": by_video_id,
        "by_trigger": by_trigger,
        "by_tag": by_tag
    }


def select_video(event: dict, library: dict) -> dict:
    """
    Selects coaching video(s) for an event or multi-event payload based on Scenario 1, 2, or 3.
    """
    by_id = library.get("by_video_id", {})
    all_events = event.get("all_events", [event])
    language = event.get("language", DEFAULT_LANGUAGE)
    
    # -------------------------------------------------------------
    # SCENARIO 1: SINGLE EVENT -> SINGLE EXISTING VIDEO (10 seconds)
    # -------------------------------------------------------------
    if len(all_events) == 1:
        vid_id = all_events[0].get("video_id")
        if not vid_id:
            # Fallback trigger string lookup
            trigger = all_events[0].get("trigger_type")
            meta = library.get("by_trigger", {}).get(trigger)
            vid_id = meta.get("video_id") if meta else None
            
        if vid_id and vid_id in by_id:
            meta = by_id[vid_id]
            lang_asset = meta["language_assets"].get(language, meta["language_assets"]["en"])
            return {
                "scenario": "scenario_1_single",
                "action": "reuse",
                "patient_id": event.get("patient_id", "P001"),
                "title": meta["title"],
                "video_filename": meta["filename"],
                "video": meta["filename"],
                "subtitles": lang_asset["subtitle_file"],
                "subtitle_file": lang_asset["subtitle_file"],
                "duration_s": meta["duration_s"],
                "category": meta["topic"],
                "trigger_reason": f"Scenario 1: Single trigger ({meta['title']})",
                "relevance": "high",
                "safety_level": meta["safety_level"]
            }

    # -------------------------------------------------------------
    # SCENARIO 2: MULTI-EVENT -> STITCH 2 VIDEOS + FADE ANIMATION (~20s)
    # -------------------------------------------------------------
    if len(all_events) >= 2:
        v1_id = all_events[0].get("video_id")
        v2_id = all_events[1].get("video_id")
        
        meta1 = by_id.get(v1_id)
        meta2 = by_id.get(v2_id)
        
        if meta1 and meta2:
            # Verify transition compatibility using composability metadata
            comp1 = meta1.get("composability", {})
            can_precede = comp1.get("can_precede", [])
            
            # Check if video 1 can precede video 2, or swap if video 2 can precede video 1
            if v2_id not in can_precede:
                comp2 = meta2.get("composability", {})
                if v1_id in comp2.get("can_precede", []):
                    meta1, meta2 = meta2, meta1  # Swap order for clinical coherence
                    v1_id, v2_id = v2_id, v1_id

            lang1 = meta1["language_assets"].get(language, meta1["language_assets"]["en"])
            lang2 = meta2["language_assets"].get(language, meta2["language_assets"]["en"])
            
            return {
                "scenario": "scenario_2_dual_stitched",
                "action": "stitch_dual",
                "patient_id": event.get("patient_id", "P001"),
                "title": f"{meta1['title']} + {meta2['title']}",
                # title and duration_s ride along because the Video VM's
                # package contract wants a per-clip title and length in its
                # clips array, and only the library knows them.
                "clip_1": {
                    "video_id": v1_id,
                    "filename": meta1["filename"],
                    "title": meta1["title"],
                    "duration_s": meta1["duration_s"],
                    "subtitle_file": lang1["subtitle_file"],
                    # Both languages, not just the requested one: a package
                    # clip needs subtitle_en_url AND subtitle_fr_url.
                    "subtitle_files": {
                        code: asset["subtitle_file"]
                        for code, asset in meta1["language_assets"].items()
                    }
                },
                "clip_2": {
                    "video_id": v2_id,
                    "filename": meta2["filename"],
                    "title": meta2["title"],
                    "duration_s": meta2["duration_s"],
                    "subtitle_file": lang2["subtitle_file"],
                    "subtitle_files": {
                        code: asset["subtitle_file"]
                        for code, asset in meta2["language_assets"].items()
                    }
                },
                "transition": {
                    "type": "crossfade",
                    "duration_s": 1.5
                },
                "total_duration_s": 18.5,  # 10s + 10s - 1.5s overlap
                "category": f"{meta1['topic']} / {meta2['topic']}",
                "trigger_reason": f"Scenario 2: Dual triggers detected ({meta1['title']} & {meta2['title']})",
                # "high", not "critical": the dashboard's relevance field only
                # accepts low/medium/high, so a stitched decision — the one case
                # that used to send "critical" — was rejected downstream.
                "relevance": "high"
            }

    # -------------------------------------------------------------
    # SCENARIO 3: PARTIAL MATCH -> EXISTING VIDEO + GOOGLE VERTEX AI
    # -------------------------------------------------------------
    primary_event = all_events[0]
    vid_id = primary_event.get("video_id")
    meta = by_id.get(vid_id)
    
    if meta:
        lang_asset = meta["language_assets"].get(language, meta["language_assets"]["en"])
        missing_condition = primary_event.get("metrics", {})
        
        # Build prompt payload for Google Vertex AI generation
        prompt_payload = {
            "model": "google-vertex-veo",
            "api_key": GOOGLE_VERTEX_API_KEY,
            "api_url_with_key": f"https://videointelligence.googleapis.com/v1/videos:annotate?key={GOOGLE_VERTEX_API_KEY}",
            "prompt": f"Generate a 10-second high-definition medical coaching animation showing {meta['topic']} care instructions for anomalous metrics: {missing_condition}.",
            "target_duration_s": 10.0,
            "style": "3D_medical_animation_clean"
        }
        
        return {
            "scenario": "scenario_3_hybrid_generated",
            "action": "generate_hybrid",
            "patient_id": event.get("patient_id", "P001"),
            "title": f"{meta['title']} (Hybrid AI Enhanced)",
            "existing_clip": {
                "video_id": meta["video_id"],
                "filename": meta["filename"],
                "subtitle_file": lang_asset["subtitle_file"]
            },
            "transition": {
                "type": "crossfade",
                "duration_s": 1.5
            },
            "vertex_ai_request": prompt_payload,
            "category": meta["topic"],
            "trigger_reason": "Scenario 3: Partial match found in library, requesting Vertex AI generation for custom scene",
            "relevance": "high"
        }

    # Default fallback
    return {
        "scenario": "none",
        "action": "none",
        "message": "No matching coaching video found in library."
    }
