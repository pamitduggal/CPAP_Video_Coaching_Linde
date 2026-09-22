#!/usr/bin/env python3
"""
===============================================================================
sync_remote_nodes.py - Distributed Multi-Node Trigger & Video Synchronizer
===============================================================================
This module automatically notifies and synchronizes external ecosystem nodes:
  1. AI Server VM (VM3 / ML Engine)
  2. Raspberry Pi 5 Edge Node (Port 8000)
  3. Central Backend & Clinical DB (VM2 / Port 80)

Whenever a new video or subtitle is added, updated, or removed:
  - Compiles the full clinical trigger matrix with direct stream URLs.
  - Broadcasts the trigger updates via HTTP webhooks with retries.
  - Saves the unified distributed catalog to 'metadata/distributed_trigger_catalog.json'.
===============================================================================
"""

import os
import sys
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from urllib.parse import urlparse
import requests

# Ensure UTF-8 output encoding for Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# =============================================================================
# DIRECTORY & ENVIRONMENT CONFIGURATION
# =============================================================================
env_base = os.environ.get("VIDEO_BASE_DIR")
if env_base and Path(env_base).exists():
    BASE_DIR = Path(env_base)
else:
    BASE_DIR = Path(__file__).resolve().parent

METADATA_DIR = BASE_DIR / "metadata"
EXISTING_VIDEOS_DIR = BASE_DIR / "existing_videos"
NEW_VIDEOS_DIR = BASE_DIR / "new_videos"
EXISTING_SUBTITLES_DIR = BASE_DIR / "existing_subtitles"
NEW_SUBTITLES_DIR = BASE_DIR / "new_subtitles"

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://159.84.143.246:8080")
DASHBOARD_BASE_URL = os.environ.get("DASHBOARD_URL") or os.environ.get("DASHBOARD_BASE_URL", "http://159.84.143.151:80")
AI_SERVER_URL = os.environ.get("AI_SERVER_URL", "http://159.84.143.151:8001/api/triggers/sync")
RPI_EDGE_URL = os.environ.get("RPI_EDGE_URL", "http://159.84.143.246:8000/api/triggers/sync")

SERVER_API_KEY = os.environ.get("VIDEO_SERVER_API_KEY") or os.environ.get("SERVER_API_KEY", "")
VIDEO_SERVER_KEY = os.environ.get("X_VIDEO_SERVER_KEY") or os.environ.get("VIDEO_SERVER_KEY", "")
ML_SERVER_KEY = os.environ.get("ML_SERVER_KEY") or os.environ.get("BACKEND_API_KEY", "")

logger = logging.getLogger("CPAP_Distributed_Sync")


# =============================================================================
# CATALOG COMPILER
# =============================================================================
def compile_distributed_trigger_catalog() -> Dict[str, Any]:
    """
    Compiles the complete clinical trigger dictionary, streaming URLs,
    and bilingual subtitle endpoints for all indexed videos.
    """
    master_json_path = METADATA_DIR / "master_video_metadata.json"
    records: List[Dict[str, Any]] = []

    if master_json_path.exists():
        try:
            with open(master_json_path, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception as err:
            logger.warning(f"Could not read master metadata: {err}")

    # Build normalized trigger catalog items
    catalog_items = []
    for r in records:
        vid_id = r.get("video_id")
        fname = r.get("filename", "")
        vstem = Path(fname).stem
        vtype = r.get("type", "curated_clinical_video")
        folder = "existing" if vtype == "curated_clinical_video" or (EXISTING_VIDEOS_DIR / fname).exists() else "new"

        item = {
            "video_id": vid_id,
            "filename": fname,
            "title": r.get("title", vstem),
            "category": r.get("category", "Personalized Coaching"),
            "subtopic": r.get("subtopic", r.get("title", vstem)),
            "trigger_type": r.get("trigger_type", "clinical_anomaly_trigger"),
            "condition_logic": r.get("condition_logic", "AND"),
            "clinical_priority": r.get("clinical_priority", "medium"),
            "trigger_conditions": r.get("trigger_conditions", {}),
            "tags": r.get("tags", {"clinical": [], "biomarker": [], "symptom": []}),
            "duration_s": r.get("duration_s", 10.0),
            "urls": {
                "video_stream": f"{PUBLIC_BASE_URL}/videos/{folder}/{fname}",
                "subtitle_en": f"{PUBLIC_BASE_URL}/subtitles/{vstem}.en.vtt",
                "subtitle_fr": f"{PUBLIC_BASE_URL}/subtitles/{vstem}.fr.vtt"
            },
            "composability": r.get("composability", {
                "transition_type": "fade_1_5s",
                "scenario_fit": ["standalone", "clip_2_of_2"]
            }),
            "bucket": folder
        }
        catalog_items.append(item)

    # Calculate statistics
    ev_count = len(list(EXISTING_VIDEOS_DIR.glob("*.mp4")))
    nv_count = len(list(NEW_VIDEOS_DIR.glob("*.mp4")))
    es_count = len(list(EXISTING_SUBTITLES_DIR.glob("*.vtt")))
    ns_count = len(list(NEW_SUBTITLES_DIR.glob("*.vtt")))

    payload = {
        "event": "clinical_video_catalog_update",
        "sync_timestamp": datetime.now(timezone.utc).isoformat(),
        "video_vm_server": PUBLIC_BASE_URL,
        "summary": {
            "total_curated_videos": ev_count,
            "total_ai_videos": nv_count,
            "total_library_videos": ev_count + nv_count,
            "total_subtitle_tracks": es_count + ns_count,
            "total_indexed_triggers": len(catalog_items)
        },
        "supported_scenarios": [
            "scenario_1_single_clip",
            "scenario_2_stitched_sequence",
            "scenario_3_generative_ai_veo"
        ],
        "triggers": catalog_items,
        "video_triggers": catalog_items
    }

    # Cache locally to disk
    try:
        out_file = METADATA_DIR / "distributed_trigger_catalog.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as err:
        logger.warning(f"Could not cache distributed trigger catalog: {err}")

    return payload


# =============================================================================
# MULTI-NODE DISPATCH ENGINE
# =============================================================================
def _dispatch_webhook(node_name: str, target_urls: List[str], headers: Dict[str, str], payload: Dict[str, Any], verbose: bool = True) -> Dict[str, Any]:
    """
    Sends the catalog update payload to target URLs with fallback and retry logic.
    """
    status_result = {"node": node_name, "status": "unreachable", "url": None, "code": None}
    
    for url in target_urls:
        if not url:
            continue
        for attempt in range(2):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=(1.5, 2.5)
                )
                if resp.status_code in (200, 201, 202, 204):
                    status_result["status"] = "synced"
                    status_result["url"] = url
                    status_result["code"] = resp.status_code
                    if verbose:
                        print(f"  [DISTRIBUTED SYNC] [OK] Successfully notified {node_name} at {url} (HTTP {resp.status_code})")
                    return status_result
                elif resp.status_code == 404:
                    # Endpoint route mismatch, try next candidate URL
                    break
                else:
                    if verbose:
                        print(f"  [DISTRIBUTED SYNC] [WARN] {node_name} returned status {resp.status_code} on {url}")
            except requests.RequestException as e:
                if attempt == 1 and verbose:
                    print(f"  [DISTRIBUTED SYNC] [NOTICE] {node_name} ({url}) not reachable: {e}")
                time.sleep(0.2)
            except Exception as e:
                if attempt == 1 and verbose:
                    print(f"  [DISTRIBUTED SYNC] [ERROR] {node_name} error: {e}")
                time.sleep(0.2)
                
    return status_result


def broadcast_triggers_to_all_nodes(new_videos_added: Optional[List[str]] = None, verbose: bool = True) -> Dict[str, Any]:
    """
    Main broadcast function:
      1. Compiles the latest video & trigger catalog.
      2. Concurrently notifies AI Server (VM3), Raspberry Pi Edge (Port 8000),
         and Central Backend (VM2).
      3. Returns the dispatch results for all nodes.
    """
    if verbose:
        print("=" * 75)
        print(" [DISTRIBUTED SYNC] [BROADCAST] Notifying AI Server, Raspberry Pi & Backend...")
        if new_videos_added:
            print(f"   [+] New Video Assets : {', '.join(new_videos_added)}")

    payload = compile_distributed_trigger_catalog()
    if new_videos_added:
        payload["newly_added_videos"] = new_videos_added

    dash_parsed = urlparse(DASHBOARD_BASE_URL)
    dash_host = dash_parsed.hostname or "159.84.143.151"

    # Node 1: AI Server VM (VM3 / ML Engine)
    ai_candidates = [
        AI_SERVER_URL,
        f"http://{dash_host}:8001/api/triggers/sync",
        f"http://{dash_host}/api/ai/sync-catalog",
        f"{DASHBOARD_BASE_URL.rstrip('/')}/api/ai/sync-catalog"
    ]
    ai_headers = {
        "Content-Type": "application/json",
        "X-ML-Key": ML_SERVER_KEY,
        "X-API-KEY": SERVER_API_KEY
    }

    # Node 2: Raspberry Pi 5 Edge Node (Port 8000)
    rpi_candidates = [
        RPI_EDGE_URL,
        "http://159.84.143.246:8000/api/triggers/sync",
        "http://159.84.143.246:8000/api/catalog/update"
    ]
    rpi_headers = {
        "Content-Type": "application/json",
        "X-API-KEY": SERVER_API_KEY
    }

    # Node 3: Central Backend & Database (VM2 / Port 80)
    backend_candidates = [
        f"{DASHBOARD_BASE_URL.rstrip('/')}/api/videos/catalog-sync",
        f"{DASHBOARD_BASE_URL.rstrip('/')}/api/catalog/sync",
        f"{DASHBOARD_BASE_URL.rstrip('/')}/api/videos/sync",
        f"http://{dash_host}/api/videos/assign"
    ]
    backend_headers = {
        "Content-Type": "application/json",
        "X-Video-Server-Key": VIDEO_SERVER_KEY
    }

    # Execute dispatches
    res_ai = _dispatch_webhook("AI Server (VM3)", ai_candidates, ai_headers, payload, verbose=verbose)
    res_rpi = _dispatch_webhook("Raspberry Pi 5 Edge Node", rpi_candidates, rpi_headers, payload, verbose=verbose)
    res_vm2 = _dispatch_webhook("Central Backend (VM2)", backend_candidates, backend_headers, payload, verbose=verbose)

    summary = {
        "sync_timestamp": payload["sync_timestamp"],
        "total_triggers": len(payload["video_triggers"]),
        "ai_server": res_ai,
        "raspberry_pi": res_rpi,
        "central_backend": res_vm2
    }

    if verbose:
        print(" [DISTRIBUTED SYNC] [COMPLETE] Multi-node trigger distribution cycle finished.")
        print(f"   * Total Synced Triggers : {summary['total_triggers']}")
        print(f"   * AI Server Status      : {res_ai['status']}")
        print(f"   * Raspberry Pi Status   : {res_rpi['status']}")
        print(f"   * Central Backend Status: {res_vm2['status']}")
        print("=" * 75)

    return summary


def broadcast_in_background(new_videos_added: Optional[List[str]] = None):
    """Launches the broadcast dispatch asynchronously in a separate daemon thread."""
    t = threading.Thread(
        target=broadcast_triggers_to_all_nodes,
        args=(new_videos_added, True),
        daemon=True,
        name="DistributedSyncBroadcast"
    )
    t.start()


# =============================================================================
# CLI ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    broadcast_triggers_to_all_nodes(verbose=True)
