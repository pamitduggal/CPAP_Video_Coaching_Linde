#!/usr/bin/env python3
"""
===============================================================================
update_master_metadata.py - Instant Master Metadata Synchronizer
===============================================================================
This module provides a fast, lightweight synchronization function that scans
all individual metadata records ('metadata/video_XX.json') along with any new
videos in 'new_videos/', synthesizes missing metadata or subtitles, and compiles
the single master metadata file: 'metadata/master_video_metadata.json'.
===============================================================================
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any

# Import helper functions from build_video_metadata
from build_video_metadata import (
    BASE_DIR,
    METADATA_DIR,
    NEW_VIDEOS_DIR,
    NEW_SUBTITLES_DIR,
    build_generated_video_record
)


def update_master_metadata() -> int:
    """
    Collects all metadata records, detects any unindexed AI videos in 'new_videos/',
    generates their JSON and subtitle records, and writes 'master_video_metadata.json'.

    Returns:
        int: Total number of indexed video records.
    """
    master_records: List[Dict[str, Any]] = []
    
    # -------------------------------------------------------------------------
    # 1. Collect all existing individual video_XX.json records
    # -------------------------------------------------------------------------
    existing_json_files = sorted(
        METADATA_DIR.glob("video_*.json"),
        key=lambda x: int(re.findall(r'\d+', x.name)[0]) if re.findall(r'\d+', x.name) else 999
    )
    
    for json_file in existing_json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                record = json.load(f)
                master_records.append(record)
        except Exception as e:
            print(f"[Warning] Error reading metadata file {json_file.name}: {e}")
            
    existing_ids = {r.get("video_id") for r in master_records if "video_id" in r}
    
    # -------------------------------------------------------------------------
    # 2. Check for any new video files in 'new_videos/' without metadata yet
    # -------------------------------------------------------------------------
    if NEW_VIDEOS_DIR.exists():
        new_video_files = sorted(
            [f for f in os.listdir(NEW_VIDEOS_DIR) if f.endswith('.mp4')],
            key=lambda x: int(x.split('_')[0]) if x.split('_')[0].isdigit() else 999
        )
        
        int_ids = [i for i in existing_ids if isinstance(i, int)]
        max_id = max(int_ids, default=37)
        for nvfile in new_video_files:
            prefix_str = nvfile.split('_')[0]
            vid_id = int(prefix_str) if prefix_str.isdigit() else (max_id + 1)
            if not prefix_str.isdigit():
                max_id += 1
            
            # If this video ID does not have a record yet, create it
            if vid_id not in existing_ids:
                record = build_generated_video_record(nvfile, vid_id)
                
                # Save individual JSON record
                out_json = METADATA_DIR / f"video_{vid_id:02d}.json"
                with open(out_json, "w", encoding="utf-8") as f:
                    json.dump(record, f, indent=2, ensure_ascii=False)
                    
                master_records.append(record)
                existing_ids.add(vid_id)
                print(f"  -> Indexed new video metadata: {out_json.name}")

    # -------------------------------------------------------------------------
    # 3. Sort records strictly by video_id (1, 2, 3... 27, 28...)
    # -------------------------------------------------------------------------
    master_records.sort(key=lambda x: x.get("video_id", 0))
    
    # -------------------------------------------------------------------------
    # 4. Save the compiled master_video_metadata.json
    # -------------------------------------------------------------------------
    master_path = METADATA_DIR / "master_video_metadata.json"
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(master_records, f, indent=2, ensure_ascii=False)
        
    print(f"[SUCCESS] Master metadata synchronized at {master_path} (Total videos: {len(master_records)})")
    
    # -------------------------------------------------------------------------
    # 5. Synchronize distributed trigger catalog
    # -------------------------------------------------------------------------
    try:
        from sync_remote_nodes import compile_distributed_trigger_catalog
        compile_distributed_trigger_catalog()
    except Exception as err:
        print(f"[Warning] Could not recompile distributed trigger catalog: {err}")

    return len(master_records)


if __name__ == "__main__":
    update_master_metadata()
