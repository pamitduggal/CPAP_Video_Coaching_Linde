import sys
import os
import json
sys.path.insert(0, r"c:\CPAP_AI_Server")

from core.video_engine import (
    VideoAssignmentTracker,
    get_assignment_tracker,
    is_video_already_assigned,
    orchestrate_video_recommendation,
    CLINICAL_VIDEO_REGISTRY
)

print("--- Testing VideoAssignmentTracker ---")
tracker = get_assignment_tracker()
test_pid = "99999"
test_vid_record = CLINICAL_VIDEO_REGISTRY[29]

# 1. Verify initially not assigned
assert not tracker.is_assigned(test_pid, 29, test_vid_record["filename"])
print("Step 1: Verified patient is not initially assigned.")

# 2. Record an assignment
rec = tracker.record_assignment(
    patient_id=test_pid,
    video_record=test_vid_record,
    trigger_reason="Test strap adjustment",
    event_id="EVT_TEST_99999"
)
print("Step 2: Recorded assignment:", rec)
assert tracker.is_assigned(test_pid, 29, test_vid_record["filename"])
assert tracker.is_assigned(test_pid, 29)
assert tracker.is_assigned(test_pid, video_filename=test_vid_record["filename"])

# 3. Test orchestrate_video_recommendation duplicate suppression
dup_res = orchestrate_video_recommendation(
    patient_id=test_pid,
    video_record=test_vid_record,
    custom_reason="Should be skipped"
)
print("Step 3: Duplicate dispatch result:", dup_res)
assert dup_res.get("status") == "already_assigned"
assert dup_res.get("skipped") is True
print("Step 3: Verified duplicate call was skipped without hitting network!")

# 4. Test reloading tracker from disk (simulating server restart)
print("Step 4: Simulating server restart by creating new tracker instance from disk...")
new_tracker = VideoAssignmentTracker()
assert new_tracker.is_assigned(test_pid, 29, test_vid_record["filename"])
print(f"Step 4: Reloaded from disk successfully! Tracked patients: {new_tracker.get_summary()['total_patients']}")

# 5. Clean up test patient record
del tracker._raw_assignments[test_pid]
tracker._assigned_keys.remove((test_pid, test_vid_record["filename"].lower()))
tracker._assigned_keys.remove((test_pid, "29"))
if test_pid in tracker._patient_latest:
    del tracker._patient_latest[test_pid]
tracker._save_to_disk()

assert not tracker.is_assigned(test_pid, 29)
print("Step 5: Cleaned up test patient record from disk.")
print("\nAll VideoAssignmentTracker tests PASSED perfectly!")
