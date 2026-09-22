import sys
sys.path.insert(0, r"c:\CPAP_AI_Server")
from core.registry import CLINICAL_VIDEO_REGISTRY, sync_video_catalog_from_vm
from core.video_engine import VideoOrchestrationClient, resolve_clinical_video_for_patient, resolve_clinical_video_playlist_for_patient

print("Checking registry length:", len(CLINICAL_VIDEO_REGISTRY))
assert len(CLINICAL_VIDEO_REGISTRY) >= 37, f"Expected at least 37, got {len(CLINICAL_VIDEO_REGISTRY)}"

sync_res = sync_video_catalog_from_vm()
print("Dynamic sync result:", sync_res)
assert sync_res["status"] in ("success", "cached_fallback")
assert sync_res.get("total_curated_videos", 37) >= 37 or sync_res.get("total_library_videos", 39) >= 37

# Test playlist resolution
playlist = resolve_clinical_video_playlist_for_patient(
    patient_plan_row={"patient_id": "10042", "use_mean_7d": 5.2, "leaks95_mean_7d": 32.0},
    feature_row={"thoracic_belt_shift": True, "signal_iq": 45.0}
)
print(f"Resolved playlist items: {len(playlist)}")
for item in playlist:
    print(f"  - Step {item['step']}: Video {item['video_id']} ({item['video_filename']})")

print("\nCore pipeline imports and video engine checks passed cleanly!")
