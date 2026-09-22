"""
Test suite for Video Server Technical Briefing Integrations:
1. 39 catalog items with explicit boolean logic ('AND' / 'OR') and clinical priority.
2. Dynamic trigger evaluation with AND/OR rules.
3. Scenario 2 compounding issue playlist sequenced strictly by clinical priority ranking.
4. VM4 <1ms Fast-Path Deduplication response handling.
5. Inbound Webhook authentication and catalog sync on /api/triggers/sync.
6. Dashboard stats reporting 39 library videos and webhook active status.
"""
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import (
    LOCAL_CATALOG_PATH,
    WEBHOOK_PORT,
    VIDEO_SERVER_API_KEY,
    BACKEND_API_KEY,
)
from core.registry import (
    load_local_catalog_cache,
    CLINICAL_VIDEO_REGISTRY,
    get_clinical_video_catalog,
    update_catalog_from_payload,
)
from core.video_engine import (
    evaluate_dynamic_trigger_rule,
    resolve_clinical_video_playlist_for_patient,
    orchestrate_video_recommendation,
)
from fastapi.testclient import TestClient
from core.server import app

def test_catalog_structure_and_logic():
    print("-> Testing catalog structure and boolean logic fields...")
    load_local_catalog_cache(LOCAL_CATALOG_PATH)
    catalog = get_clinical_video_catalog()
    assert catalog, "Catalog failed to load"
    assert len(catalog) == 39, f"Expected 39 catalog items, got {len(catalog)}"

    # Check for videos 38 and 39
    ids = {item["video_id"] for item in catalog}
    assert 38 in ids, "Video 38 (AI-generated) missing from catalog"
    assert 39 in ids, "Video 39 (AI-generated) missing from catalog"

    valid_logic = {"AND", "OR"}
    valid_priorities = {"critical", "high", "medium", "low", "maintenance"}

    for item in catalog:
        vid = item.get("video_id")
        logic = item.get("condition_logic")
        priority = item.get("clinical_priority")

        assert logic in valid_logic, f"Video {vid} has invalid condition_logic: {logic}"
        assert priority in valid_priorities, f"Video {vid} has invalid clinical_priority: {priority}"

    print(f"   [PASS] 39 catalog items validated. All contain valid boolean logic and clinical priorities.")


def test_evaluate_dynamic_trigger_rule():
    print("-> Testing evaluate_dynamic_trigger_rule for AND / OR logic...")
    
    # Test AND logic
    and_conditions = [
        {"metric": "ahi", "operator": ">=", "threshold": 15.0},
        {"metric": "leak_rate", "operator": ">=", "threshold": 24.0}
    ]

    # Both breached -> True
    telemetry_both = {"ahi": 16.0, "leak_rate": 25.0}
    assert evaluate_dynamic_trigger_rule(telemetry_both, and_conditions, "AND") is True

    # Only one breached -> False
    telemetry_one = {"ahi": 16.0, "leak_rate": 10.0}
    assert evaluate_dynamic_trigger_rule(telemetry_one, and_conditions, "AND") is False

    # Test OR logic
    or_conditions = [
        {"metric": "ahi", "operator": ">=", "threshold": 15.0},
        {"metric": "leak_rate", "operator": ">=", "threshold": 24.0}
    ]

    # One breached -> True
    assert evaluate_dynamic_trigger_rule(telemetry_one, or_conditions, "OR") is True
    
    # Neither breached -> False
    telemetry_neither = {"ahi": 4.0, "leak_rate": 10.0}
    assert evaluate_dynamic_trigger_rule(telemetry_neither, or_conditions, "OR") is False

    print("   [PASS] Dynamic trigger rule evaluation functions as specified.")


def test_scenario2_playlist_priority_sorting():
    print("-> Testing Scenario 2 compounding issue playlist priority sequencing...")

    # Create telemetry that triggers multiple conditions (e.g. high leak, low usage, high AHI)
    telemetry = {
        "patient_id": "TEST_PATIENT_999",
        "ahi": 28.0,
        "leak_rate": 35.0,
        "usage_hours": 2.5,
        "mask_type": "nasal",
        "pressure": 12.0
    }

    playlist = resolve_clinical_video_playlist_for_patient(telemetry)
    assert len(playlist) > 1, f"Expected multi-clip playlist, got {len(playlist)}"

    # Check sequencing: critical -> high -> medium -> low -> maintenance
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "maintenance": 4}
    rankings = [priority_order.get(clip.get("clinical_priority", "medium"), 99) for clip in playlist]

    assert rankings == sorted(rankings), f"Playlist not sorted by clinical priority: {[clip.get('clinical_priority') for clip in playlist]}"
    print(f"   [PASS] Playlist returned {len(playlist)} clips strictly sequenced by clinical priority: {[clip.get('clinical_priority') for clip in playlist]}.")


def test_fast_path_idempotency():
    print("-> Testing VM4 <1ms Fast-Path Deduplication response handling...")

    # Mock requests.post to return the VM4 duplicate fast-path JSON
    vm4_fast_path_resp = MagicMock()
    vm4_fast_path_resp.status_code = 200
    vm4_fast_path_resp.json.return_value = {
        "status": "already_assigned",
        "duplicate_detected": True,
        "dashboard_push": "skipped_duplicate",
        "message": "Video already dispatched within cooldown window."
    }

    with patch("requests.post", return_value=vm4_fast_path_resp):
        res = orchestrate_video_recommendation("PATIENT_DUP_1", 30, "High AHI alert", "159.84.143.246:8080")
        assert res.get("status") == "already_assigned" or res.get("duplicate_detected") is True
        assert res.get("duplicate_detected") is True

    print("   [PASS] Fast-path duplicate response handled gracefully without error.")


def test_inbound_webhook_authentication_and_sync():
    print("-> Testing inbound webhook /api/triggers/sync authentication and sync...")
    client = TestClient(app)

    # 1. Reject missing / invalid key
    resp_unauth = client.post("/api/triggers/sync", json={"test": True}, headers={"X-API-KEY": "wrong-key"})
    assert resp_unauth.status_code == 403, f"Expected 403, got {resp_unauth.status_code}"

    # 2. Accept valid key
    test_payload = [
        {
            "video_id": 30,
            "filename": "30_High_AHI_sleep_position.mp4",
            "title": "Sleep Position Adjustment for Positional OSA",
            "condition_logic": "AND",
            "clinical_priority": "critical",
            "trigger_conditions": [{"metric": "ahi", "operator": ">=", "threshold": 15.0}]
        }
    ]
    resp_auth = client.post(
        "/api/triggers/sync",
        json=test_payload,
        headers={"X-API-KEY": VIDEO_SERVER_API_KEY, "X-ML-Key": BACKEND_API_KEY}
    )
    assert resp_auth.status_code == 200, f"Expected 200, got {resp_auth.status_code}: {resp_auth.text}"
    body = resp_auth.json()
    assert body.get("status") == "success"
    assert body.get("synced_triggers") == 1

    # Reload local cache to restore full 39 catalog
    load_local_catalog_cache(LOCAL_CATALOG_PATH)

    print("   [PASS] Inbound webhook authentication and catalog update verified.")


def test_dashboard_stats():
    print("-> Testing /api/dashboard/stats returns webhook info and 39 library videos...")
    client = TestClient(app)
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 200
    stats = resp.json()

    webhook_port = stats.get("config", {}).get("webhook_port")
    webhook_active = stats.get("config", {}).get("webhook_active")
    total_videos = stats.get("catalog", {}).get("total_library_videos")

    assert webhook_port == 8001, f"Expected webhook_port 8001, got {webhook_port}"
    assert webhook_active is True, f"Expected webhook_active True, got {webhook_active}"
    assert total_videos >= 39, f"Expected at least 39 videos, got {total_videos}"

    print(f"   [PASS] Dashboard stats: webhook_port={webhook_port}, library_videos={total_videos}.")


if __name__ == "__main__":
    print("===============================================================================")
    print(" RUNNING TECHNICAL BRIEFING INTEGRATION TESTS")
    print("===============================================================================")
    test_catalog_structure_and_logic()
    test_evaluate_dynamic_trigger_rule()
    test_scenario2_playlist_priority_sorting()
    test_fast_path_idempotency()
    test_inbound_webhook_authentication_and_sync()
    test_dashboard_stats()
    print("===============================================================================")
    print(" ALL TECHNICAL BRIEFING INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("===============================================================================")
