import sys
import os
sys.path.insert(0, r"c:\CPAP_AI_Server")
from unittest.mock import MagicMock

print("--- Testing Server Dashboard Endpoints ---", flush=True)
from core.server import dashboard_view, get_dashboard_stats, get_server_logs, root, logger, log_ring_buffer

# 1. Test dashboard HTML view
d_resp = dashboard_view()
assert d_resp.status_code == 200
assert "text/html" in d_resp.media_type
print(f"PASS: dashboard_view returned HTML ({len(d_resp.body)} bytes)", flush=True)

# 2. Test dashboard stats JSON
stats = get_dashboard_stats()
assert "config" in stats
assert "pipeline" in stats
assert "tracker" in stats
assert "catalog" in stats
assert stats["catalog"]["total_curated_videos"] in (37, 39)
assert stats["catalog"]["total_library_videos"] == 39
print(f"PASS: get_dashboard_stats returned {stats['catalog']['total_curated_videos']} curated videos / {stats['catalog']['total_library_videos']} library videos", flush=True)

# 3. Test log ring buffer
logger.info("TEST_VERIFY_LOG_CAPTURE_STREAM")
logs = get_server_logs()
assert any("TEST_VERIFY_LOG_CAPTURE_STREAM" in l["message"] for l in logs)
print(f"PASS: get_server_logs returned {len(logs)} log entries with live message found", flush=True)

# 4. Test root negotiation
req_html = MagicMock()
req_html.headers = {"accept": "text/html,application/xhtml+xml"}
res_html = root(req_html)
assert res_html.status_code == 200

req_json = MagicMock()
req_json.headers = {"accept": "application/json"}
res_json = root(req_json)
assert isinstance(res_json, dict)
assert res_json["status"] == "online"
print("PASS: root endpoint content negotiation works perfectly!", flush=True)
print("\nALL SERVER DASHBOARD ENDPOINT TESTS PASSED!", flush=True)
