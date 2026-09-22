import sys
sys.path.insert(0, r"c:\CPAP_AI_Server")

from core.video_engine import (
    VideoAssignmentTracker,
    get_assignment_tracker,
    is_video_already_assigned,
    orchestrate_video_recommendation,
    orchestrate_pipeline_videos,
    CLINICAL_VIDEO_REGISTRY
)
from core.server import app
from core.registry import get_pipeline_state_copy

print("1. Checking tracker singleton...")
tracker = get_assignment_tracker()
summary = tracker.get_summary()
print("   Tracker summary:", summary)
assert "total_patients" in summary
assert "total_assignments" in summary

print("2. Checking pipeline state...")
state = get_pipeline_state_copy()
print("   Pipeline state keys:", list(state.keys()))
assert "last_video_skipped_duplicates" in state

print("3. Testing orchestrate_pipeline_videos with limit of 0 to verify execution logic without dispatching...")
res = orchestrate_pipeline_videos(force=False, max_dispatches=0)
print("   Orchestrate pipeline result:", res)
assert res["status"] == "success"
assert res["orchestrated_count"] == 0

print("4. Testing FastAPI routes registration...")
routes = [route.path for route in app.routes]
print("   Checking new routes in app:")
for r in ["/api/video-server/assigned-tracker", "/api/video-server/assigned-tracker/clear"]:
    assert r in routes, f"Missing route: {r}"
    print(f"   - Route registered: {r}")

print("\nALL SYSTEM INTEGRATION CHECKS PASSED CLEANLY!")
