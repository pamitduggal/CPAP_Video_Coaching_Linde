import sys
sys.path.insert(0, r"c:\CPAP_AI_Server")
from starlette.testclient import TestClient
from core.server import app, logger, log_ring_buffer

client = TestClient(app)

print("1. Testing GET /dashboard...")
r_dash = client.get("/dashboard")
assert r_dash.status_code == 200
assert "text/html" in r_dash.headers["content-type"]
assert "SleepCare CPAP AI Server" in r_dash.text
print(f"   PASS: /dashboard returned valid HTML ({len(r_dash.text)} bytes)")

print("2. Testing GET / with Accept: text/html...")
r_root = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
assert r_root.status_code == 200
assert "text/html" in r_root.headers["content-type"]
print("   PASS: GET / automatically serves interactive dashboard to web browsers")

print("3. Testing GET / with Accept: application/json...")
r_json = client.get("/", headers={"Accept": "application/json"})
assert r_json.status_code == 200
assert "application/json" in r_json.headers["content-type"]
assert r_json.json()["status"] == "online"
print("   PASS: GET / preserves JSON status for API clients")

print("4. Testing GET /api/dashboard/stats...")
r_stats = client.get("/api/dashboard/stats")
assert r_stats.status_code == 200
stats = r_stats.json()
assert "config" in stats and "pipeline" in stats and "tracker" in stats and "catalog" in stats
print(f"   PASS: /api/dashboard/stats returned complete telemetry: {list(stats.keys())}")

print("5. Testing live terminal console log buffer...")
logger.info("DASHBOARD_LIVE_STREAM_VERIFIED_123")
r_logs = client.get("/api/server/logs")
assert r_logs.status_code == 200
logs = r_logs.json()
assert len(logs) > 0
found = any("DASHBOARD_LIVE_STREAM_VERIFIED_123" in l["message"] for l in logs)
assert found, "Log entry not found in ring buffer"
print(f"   PASS: Ring buffer successfully captured log (Total entries: {len(logs)})")

print("6. Testing single-patient video simulation...")
from core.config import AI_SERVER_API_KEY
r_sim = client.post("/api/video-server/orchestrate/10042?force=false", headers={"X-API-KEY": AI_SERVER_API_KEY})
assert r_sim.status_code == 200
sim_data = r_sim.json()
assert "resolved_video" in sim_data
print(f"   PASS: Patient 10042 simulated video -> Video #{sim_data['resolved_video']['id']} ({sim_data['resolved_video']['filename']})")

print("\nALL DASHBOARD AND LIVE LOG TESTS PASSED 100%!")
