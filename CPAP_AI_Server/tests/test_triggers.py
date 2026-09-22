import sys
sys.path.insert(0, r"c:\CPAP_AI_Server")
from core.registry import sync_video_catalog_from_vm, CLINICAL_VIDEO_REGISTRY, DYNAMIC_CATALOG_STATE
from core.video_engine import resolve_clinical_video_for_patient

print("Testing dynamic sync from Video VM...")
res = sync_video_catalog_from_vm()
print(f"Sync result: {res}")
print(f"Catalog length: {len(DYNAMIC_CATALOG_STATE)}")

test_cases = [
    ({"ecg_quality": 35}, 28, "ECG_Quality < 40%"),
    ({"hr_dropout": 35}, 28, "HR_Dropout >= 30%"),
    ({"thoracic_belt_shift": True}, 29, "Thoracic_Belt_Shift"),
    ({"rip_artifact": 32}, 29, "RIP_Artifact >= 30%"),
    ({"docking_failure": True}, 30, "Docking_Failure"),
    ({"sync_led_unconfirmed": True}, 30, "Sync_LED_Unconfirmed"),
    ({"perfusion_index": 0.3}, 31, "Perfusion_Index < 0.5%"),
    ({"finger_depth_misaligned": True}, 32, "Finger_Depth_Misaligned"),
    ({"nail_obstruction": True}, 32, "Nail_Obstruction"),
    ({"signal_iq": 55}, 33, "Signal_IQ < 60%"),
    ({"ppg_seal_loss": True}, 34, "PPG_Seal_Loss"),
    ({"calibration_movement_detected": True}, 35, "Calibration_Movement_Detected"),
    ({"sensor_impedance_high": True}, 36, "Sensor_Impedance_High"),
    ({"cpap_tube_and_wearable_conflict": True}, 37, "CPAP_Tube_And_Wearable_Conflict"),
]

passed = 0
for telem, expected_id, label in test_cases:
    vid = resolve_clinical_video_for_patient({"patient_id": "PT_TEST", **telem}, None)
    assert vid["id"] == expected_id, f"Failed for {label}: got id {vid['id']}, expected {expected_id}"
    print(f"PASS: {label:35s} -> Video {vid['id']:2d} ({vid['filename']})")
    passed += 1

print(f"\nAll {passed} wearable anomaly test scenarios passed successfully!")
