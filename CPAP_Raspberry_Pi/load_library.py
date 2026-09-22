"""
OSA-IVC — Library loader + matcher for Scenarios 1, 2, and 3
--------------------------------------------------------------
Reads all 27 metadata JSON files, builds an in-memory lookup, and matches
incoming events to:
- Scenario 1: Single existing video asset (10s)
- Scenario 2: Combination of 2 existing videos with 1.5s fade transition (~20s)
- Scenario 3: Generation request for a detected condition the library has no clip for
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

    def clip_for(evt):
        """The library clip covering one event, or None if there is none."""
        vid = evt.get("video_id")
        if not vid:
            by_trigger = library.get("by_trigger", {}).get(evt.get("trigger_type"))
            vid = by_trigger.get("video_id") if by_trigger else None
        return by_id.get(vid)

    # Scenarios 1 and 2 may only consider events the library can actually
    # answer. Splitting here rather than filtering inline keeps an uncovered
    # event from silently occupying a clip slot it has no clip for.
    covered = [e for e in all_events if clip_for(e)]
    uncovered = [e for e in all_events if not clip_for(e)]

    # -------------------------------------------------------------
    # SCENARIO 3: DETECTED CONDITION WITH NO CLIP -> GENERATE ONE
    # -------------------------------------------------------------
    # Checked FIRST, deliberately. As a fall-through after 1 and 2 this branch
    # was unreachable: every shape that could reach it still had its ids
    # resolving, so scenario 2 always returned first.
    if uncovered and not covered:
        # all_events arrives severity-sorted from edge_detection.detect_event.
        target = uncovered[0]
        trigger = target.get("trigger_type") or "unrecognised_condition"
        readable = trigger.replace("_", " ")
        metrics = target.get("metrics", {})
        measured = ", ".join(f"{k} {v}" for k, v in metrics.items()) or "no numeric detail"
        return {
            "scenario": "scenario_3_generated",
            "action": "generate",
            "patient_id": event.get("patient_id", "P001"),
            "title": f"Personalised coaching: {readable}",
            # No api_key and no api_url here. The Video VM holds the Vertex
            # credentials, not the Pi — and this decision is written to
            # logs/events/ and returned in the /ingest HTTP response, so a key
            # placed here would leak on every request.
            #
            # No "model" either: the VM interpolates it straight into the
            # Vertex URL path, so a wrong value becomes a request for a model
            # that does not exist. Omitting it lets the VM use its own default,
            # which is the right call — model choice belongs to whoever owns
            # the Vertex relationship.
            "vertex_ai_request": {
                "patient_id": str(event.get("patient_id", "P001")),
                "prompt": (
                    f"A 10-second medical coaching animation for a CPAP patient "
                    f"showing how to respond to {readable} (measured: {measured}). "
                    f"Clean 3D medical animation, calm and instructional."
                ),
            },
            "target_duration_s": 10.0,
            "category": "Generated coaching",
            "trigger_reason": (
                f"Scenario 3: no library clip covers '{trigger}' — requesting generation"
            ),
            "relevance": "high",
            "uncovered_signals": [e.get("trigger_type") for e in uncovered],
        }
    
    # -------------------------------------------------------------
    # SCENARIO 1: SINGLE EVENT -> SINGLE EXISTING VIDEO (10 seconds)
    # -------------------------------------------------------------
    if len(covered) == 1:
        vid_id = covered[0].get("video_id")
        if not vid_id:
            # Fallback trigger string lookup
            trigger = covered[0].get("trigger_type")
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
    if len(covered) >= 2:
        v1_id = covered[0].get("video_id")
        v2_id = covered[1].get("video_id")
        
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


    # Default fallback
    return {
        "scenario": "none",
        "action": "none",
        "message": "No matching coaching video found in library."
    }
