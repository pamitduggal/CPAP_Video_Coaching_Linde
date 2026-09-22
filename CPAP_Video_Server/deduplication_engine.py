#!/usr/bin/env python3
"""
===============================================================================
deduplication_engine.py - 3-Level Deep Metadata Deduplication Engine
===============================================================================
Ensures that neither legacy videos (Clips 1–37) nor newly generated AI videos (38+)
are ever duplicated. Inspects 100% of video metadata:
  1. Level 1: Exact Prompt MD5 Cache Lookup
  2. Level 2: Dual Directory Filename & Title Slug Matching
  3. Level 3: Deep Semantic & Metadata Inspection across:
     - Titles and subtopics
     - Clinical, biomarker, and symptom tags
     - Detailed 3-act scene descriptions (start_scene, core_scene, end_scene)
     - Full spoken voiceover narration transcripts and WebVTT cue text
     - Biomarker trigger types and trigger conditions
===============================================================================
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Tuple

# Base Directories
env_base = os.environ.get("VIDEO_BASE_DIR")
if env_base and Path(env_base).exists():
    BASE_DIR = Path(env_base)
else:
    BASE_DIR = Path(__file__).resolve().parent

EXISTING_DIR = BASE_DIR / "existing_videos"
NEW_DIR = BASE_DIR / "new_videos"
METADATA_DIR = BASE_DIR / "metadata"
EXISTING_SUBTITLES_DIR = BASE_DIR / "existing_subtitles"
NEW_SUBTITLES_DIR = BASE_DIR / "new_subtitles"

STOP_WORDS_DEDUP: Set[str] = {
    "a", "an", "the", "in", "on", "to", "for", "and", "or", "of", "with", "at", 
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", 
    "be", "this", "that", "it", "cpap", "video", "coaching", "proper", "how", 
    "patient", "adjust", "adjustment", "adjusting", "routine", "guide", "medical",
    "animation", "second", "stylized", "warm", "setting", "action", "showing",
    "clip", "demonstration", "help", "can", "make", "using", "use", "ensure"
}

# In-memory mtime cache to avoid redundant disk I/O on repeated requests
_CACHED_RECORDS: List[Dict[str, Any]] = []
_CACHED_MASTER_MTIME: float = 0.0


def load_all_video_records() -> List[Dict[str, Any]]:
    """
    Loads complete metadata records from master_video_metadata.json
    and supplements from any individual metadata/video_*.json files.
    Uses mtime caching to avoid disk reads when metadata hasn't changed.
    """
    global _CACHED_RECORDS, _CACHED_MASTER_MTIME

    master_file = METADATA_DIR / "master_video_metadata.json"
    current_mtime = master_file.stat().st_mtime if master_file.exists() else 0.0

    if _CACHED_RECORDS and current_mtime == _CACHED_MASTER_MTIME and current_mtime > 0:
        return _CACHED_RECORDS

    records_by_id: Dict[int, Dict[str, Any]] = {}

    # 1. Primary source: master_video_metadata.json
    if master_file.exists():
        try:
            with open(master_file, "r", encoding="utf-8") as f:
                master_list = json.load(f)
                for item in master_list:
                    vid = item.get("video_id")
                    if vid is not None:
                        records_by_id[int(vid)] = item
        except Exception:
            pass

    # 2. Supplementary source: individual video_*.json files
    if METADATA_DIR.exists():
        for jf in METADATA_DIR.glob("video_*.json"):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                    vid = rec.get("video_id")
                    if vid is not None and int(vid) not in records_by_id:
                        records_by_id[int(vid)] = rec
            except Exception:
                pass

    _CACHED_RECORDS = sorted(records_by_id.values(), key=lambda x: x.get("video_id", 999))
    _CACHED_MASTER_MTIME = current_mtime
    return _CACHED_RECORDS


def extract_searchable_corpus(record: Dict[str, Any]) -> Tuple[str, Set[str]]:
    """
    Extracts 100% of searchable clinical text and keywords from a video metadata record:
    - filename, title, subtopic, category
    - trigger_type & trigger_conditions
    - clinical tags, biomarker tags, symptom tags
    - scene descriptions (0-3s, 3-7s, 7-10s)
    - full spoken voiceover narration & individual cue lines
    """
    parts: List[str] = []

    # High-level fields
    parts.append(str(record.get("filename", "")))
    parts.append(str(record.get("title", "")))
    parts.append(str(record.get("subtopic", "")))
    parts.append(str(record.get("category", "")))
    parts.append(str(record.get("trigger_type", "")))

    # Trigger conditions
    for k, v in record.get("trigger_conditions", {}).items():
        parts.append(f"{k} {v}")

    # Tags
    tags = record.get("tags", {})
    for tag_cat in ("clinical", "biomarker", "symptom"):
        for t in tags.get(tag_cat, []):
            parts.append(str(t).replace("_", " "))

    # Detailed Scene Segmentations (0-3s, 3-7s, 7-10s)
    scenes = record.get("scene_segmentation", {})
    for scene_key in ("start_scene_0_3s", "core_scene_3_7s", "end_scene_7_10s"):
        s_data = scenes.get(scene_key, {})
        if isinstance(s_data, dict) and "description" in s_data:
            parts.append(str(s_data["description"]))

    # Language Assets & Spoken Voiceover Narration
    lang_assets = record.get("language_assets", {})
    for lang_code in ("en", "fr"):
        l_info = lang_assets.get(lang_code, {})
        if isinstance(l_info, dict):
            if "full_narration" in l_info:
                parts.append(str(l_info["full_narration"]))
            for cue in l_info.get("cues", []):
                if isinstance(cue, dict) and "text" in cue:
                    parts.append(str(cue["text"]))

    corpus_text = " ".join(parts).lower()
    tokens = set(re.findall(r'[a-zA-Z]{3,}', corpus_text)) - STOP_WORDS_DEDUP
    return corpus_text, tokens


def find_existing_library_match(raw_prompt: str, title_slug: str = "") -> Optional[Dict[str, Any]]:
    """
    Modular 3-Level Pre-Generation Deduplication Shield:
    Checks if an incoming prompt duplicates ANY existing video (legacy 1–37 or newly generated 38+).
    
    Returns:
        Dict with match details if duplicate detected, else None (safe to generate).
    """
    if not raw_prompt or not raw_prompt.strip():
        return None

    raw_prompt_clean = raw_prompt.strip()

    # =========================================================================
    # LEVEL 1: Exact Prompt MD5 Hash Cache Lookup (<1ms)
    # =========================================================================
    prompt_hash = hashlib.md5(raw_prompt_clean.lower().encode("utf-8")).hexdigest()[:10]
    cache_index_file = METADATA_DIR / "generative_cache_index.json"
    if cache_index_file.exists():
        try:
            with open(cache_index_file, "r", encoding="utf-8") as f:
                cache_map = json.load(f)
            cached_filename = cache_map.get(prompt_hash)
            if cached_filename:
                p_new = NEW_DIR / cached_filename
                p_exist = EXISTING_DIR / cached_filename
                if p_new.exists() and p_new.stat().st_size > 0:
                    return {
                        "matched": True,
                        "level": "Level 1: Exact Prompt Hash Cache",
                        "bucket": "new",
                        "filename": cached_filename,
                        "path": p_new,
                        "title": cached_filename.replace(".mp4", "").replace("_", " "),
                        "score": 10.0,
                        "match_field": "prompt_hash_cache"
                    }
                elif p_exist.exists() and p_exist.stat().st_size > 0:
                    return {
                        "matched": True,
                        "level": "Level 1: Exact Prompt Hash Cache",
                        "bucket": "existing",
                        "filename": cached_filename,
                        "path": p_exist,
                        "title": cached_filename.replace(".mp4", "").replace("_", " "),
                        "score": 10.0,
                        "match_field": "prompt_hash_cache"
                    }
        except Exception:
            pass

    # =========================================================================
    # LEVEL 2: Dual-Directory Filename & Title Slug Matching
    # =========================================================================
    if not title_slug:
        cleaned_words = [w.capitalize() for w in re.sub(r'[^a-zA-Z0-9\s]', ' ', raw_prompt_clean).split() if w]
        title_slug = "_".join(cleaned_words[:6]) if cleaned_words else "Custom_Coaching"

    # 2A. Exact slug match in NEW_DIR
    for p in NEW_DIR.glob(f"*_{title_slug}.mp4"):
        if p.exists() and p.stat().st_size > 0:
            return {
                "matched": True,
                "level": "Level 2: Dual Directory Slug Match (new_videos)",
                "bucket": "new",
                "filename": p.name,
                "path": p,
                "title": p.stem.replace("_", " "),
                "score": 9.0,
                "match_field": "filename_slug_new"
            }

    # 2B. Exact slug match in EXISTING_DIR
    for p in EXISTING_DIR.glob(f"*_{title_slug}.mp4"):
        if p.exists() and p.stat().st_size > 0:
            return {
                "matched": True,
                "level": "Level 2: Dual Directory Slug Match (existing_videos)",
                "bucket": "existing",
                "filename": p.name,
                "path": p,
                "title": p.stem.replace("_", " "),
                "score": 9.0,
                "match_field": "filename_slug_existing"
            }

    # =========================================================================
    # LEVEL 3: Deep Semantic & Metadata Inspection (100% of Metadata Fields)
    # =========================================================================
    all_records = load_all_video_records()
    if not all_records:
        return None

    prompt_tokens = set(re.findall(r'[a-zA-Z]{3,}', raw_prompt_clean.lower())) - STOP_WORDS_DEDUP
    if not prompt_tokens:
        return None

    best_match: Optional[Dict[str, Any]] = None
    highest_score: float = 0.0

    raw_lower = raw_prompt_clean.lower()

    for item in all_records:
        vfile = item.get("filename")
        if not vfile:
            continue

        bucket = "existing" if (EXISTING_DIR / vfile).exists() else ("new" if (NEW_DIR / vfile).exists() else None)
        if not bucket:
            continue
        vpath = (EXISTING_DIR / vfile) if bucket == "existing" else (NEW_DIR / vfile)

        # Extract full metadata corpus & tokens
        corpus_text, corpus_tokens = extract_searchable_corpus(item)

        overlap = prompt_tokens.intersection(corpus_tokens)
        score = float(len(overlap))

        # Title token match bonus (+1.5 per token)
        title_text = str(item.get("title", "")).lower()
        title_tokens = set(re.findall(r'[a-zA-Z]{3,}', title_text)) - STOP_WORDS_DEDUP
        title_overlap = prompt_tokens.intersection(title_tokens)
        score += (len(title_overlap) * 1.5)

        # Spoken Narration Match Bonus (+1.0 per token in full_narration)
        lang_assets = item.get("language_assets", {})
        narration_en = str(lang_assets.get("en", {}).get("full_narration", "")).lower()
        narration_tokens = set(re.findall(r'[a-zA-Z]{3,}', narration_en)) - STOP_WORDS_DEDUP
        narration_overlap = prompt_tokens.intersection(narration_tokens)
        score += (len(narration_overlap) * 1.0)

        # Core Scene Action Match Bonus (+1.0 per token in core_scene_3_7s)
        core_scene = str(item.get("scene_segmentation", {}).get("core_scene_3_7s", {}).get("description", "")).lower()
        core_tokens = set(re.findall(r'[a-zA-Z]{3,}', core_scene)) - STOP_WORDS_DEDUP
        core_overlap = prompt_tokens.intersection(core_tokens)
        score += (len(core_overlap) * 1.0)

        # High-Precision Clinical Phrase Signatures
        if "strap" in raw_lower and "mask" in raw_lower and "1_Mask_leak" in vfile:
            score += 4.0
        if "cushion" in raw_lower and "clean" in raw_lower and "3_Cushion" in vfile:
            score += 4.0
        if "humidifier" in raw_lower and "dry" in raw_lower and "7_Dry_mouth" in vfile:
            score += 4.0
        if "chin" in raw_lower and "mouth" in raw_lower and "8_Mouth_breathing" in vfile:
            score += 4.0
        if "nasal" in raw_lower and "congestion" in raw_lower and "9_Nasal_congestion" in vfile:
            score += 4.0
        if "saline" in raw_lower and ("spray" in raw_lower or "nasal" in raw_lower) and "9_Nasal_congestion" in vfile:
            score += 5.0
        if "hexoskin" in raw_lower and "electrode" in raw_lower and "28_Hexoskin" in vfile:
            score += 5.0
        if "hexoskin" in raw_lower and "strap" in raw_lower and "29_Hexoskin" in vfile:
            score += 5.0
        if "mightysat" in raw_lower and ("warming" in raw_lower or "perfusion" in raw_lower) and "31_MightySat" in vfile:
            score += 5.0
        if "somnoart" in raw_lower and ("positioning" in raw_lower or "armband" in raw_lower) and "34_SomnoArt" in vfile:
            score += 5.0
        if "tube" in raw_lower and "rainout" in raw_lower and ("38_Proper" in vfile or "39_Humidifier" in vfile):
            score += 5.0
        if "oxygen" in raw_lower and "desaturation" in raw_lower and ("16_ScanWatch" in vfile or "38_Create" in vfile or "39_Managing" in vfile):
            score += 5.0

        if score > highest_score:
            highest_score = score
            match_details = f"Level 3: Full Metadata Semantic Match (overlap: {list(overlap)[:5]})"
            best_match = {
                "matched": True,
                "level": match_details,
                "bucket": bucket,
                "filename": vfile,
                "path": vpath,
                "title": item.get("title", vfile),
                "score": score,
                "video_id": item.get("video_id"),
                "overlap_keywords": list(overlap)
            }

    # Minimum score threshold to prevent false positives
    if highest_score >= 3.0 and best_match:
        return best_match

    return None


def register_prompt_cache(raw_prompt: str, output_filename: str) -> None:
    """
    Saves the prompt MD5 hash mapping into generative_cache_index.json
    so future identical prompts resolve in <1ms.
    """
    if not raw_prompt or not output_filename:
        return
    prompt_hash = hashlib.md5(raw_prompt.strip().lower().encode("utf-8")).hexdigest()[:10]
    cache_index_file = METADATA_DIR / "generative_cache_index.json"
    cache_map = {}
    if cache_index_file.exists():
        try:
            with open(cache_index_file, "r", encoding="utf-8") as f:
                cache_map = json.load(f)
        except Exception:
            cache_map = {}
    cache_map[prompt_hash] = output_filename
    try:
        cache_index_file.parent.mkdir(parents=True, exist_ok=True)
        temp_cache = cache_index_file.with_suffix(".tmp")
        with open(temp_cache, "w", encoding="utf-8") as f:
            json.dump(cache_map, f, indent=2)
        temp_cache.replace(cache_index_file)
    except Exception:
        pass
