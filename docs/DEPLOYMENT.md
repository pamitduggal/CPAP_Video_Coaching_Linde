# SleepCare CPAP Ecosystem: Production Deployment and Operations Guide

> DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France  
> Author: Pamit Duggal (Software and AI Engineering Intern)  
> Scope: Installation steps, Windows batch files, environment variables, and systemd units

---

## 1. Raspberry Pi 5 edge node setup

### Hardware and OS requirements
- Hardware: Raspberry Pi 5 (4GB or 8GB model) with a 32GB+ Class 10 MicroSD card or NVMe SSD.
- Operating System: Raspberry Pi OS 64-bit (Debian Bookworm).
- Network: Static DHCP lease over Ethernet or 5GHz Wi-Fi.

### Step-by-step setup
```bash
# 1. Enter the project folder
cd ~/Desktop/CPAP_Raspberry_Pi

# 2. Create the Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install packages
pip install --upgrade pip
pip install -r requirements.txt

# 4. Copy the environment configuration
cp .env.example .env
nano .env  # Set your API_KEY, VIDEO_VM_URL, and BACKEND_API_URL
```

### Pulling the latest catalog
Before starting the service, test your connection to the Video VM and sync metadata for wearable videos:
```bash
.venv/bin/python sync_catalog.py --check   # Preview changes
.venv/bin/python sync_catalog.py           # Updates metadata/video_28..37.json
```

### Running in the terminal
```bash
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

### Setting up Tailscale Funnel for mobile access
Because patients upload data over cellular connections while the Pi sits behind a home NAT router, we use Tailscale Funnel to provide an HTTPS ingress point:
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale funnel 8000
```
Use `https://<your-machine-name>.ts.net` as the base URL in the mobile app.

### Running as a systemd service
To ensure the edge app restarts after a reboot or power loss, create `/etc/systemd/system/cpap-edge.service`:
```ini
[Unit]
Description=SleepCare CPAP Raspberry Pi Edge Service
After=network.target tailscaled.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Desktop/CPAP_Raspberry_Pi
ExecStart=/home/pi/Desktop/CPAP_Raspberry_Pi/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
EnvironmentFile=/home/pi/Desktop/CPAP_Raspberry_Pi/.env

[Install]
WantedBy=multi-user.target
```

Enable and start it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cpap-edge.service
sudo systemctl start cpap-edge.service
```

---

## 2. CPAP Video Server setup (VM4)

### Host requirements
- Operating System: Windows Server 2022 Datacenter
- Address: `159.84.143.246`
- Runtime: Python 3.12 64-bit
- Network firewall: Open TCP port 8080 inbound for API and media traffic.

### Installation
Open PowerShell as Administrator:
```powershell
cd C:\CPAP_Video_Server
& "C:\Program Files\Python312\python.exe" -m pip install fastapi uvicorn requests opencv-python pydantic python-dotenv
```

### Starting the service
Run the batch file:
```cmd
c:\CPAP_Video_Server\start_server.bat
```
What the launcher script does:
1. It runs a PowerShell command checking whether port 8080 is already held by a zombie process, killing it if found.
2. It prints active configuration details (IP addresses, asset counts).
3. It launches `http://localhost:8080/` in the default browser.
4. It starts `video_vm_server.py`. The script includes an outer loop that catches unexpected Windows socket resets (`WinError 64`) and restarts Uvicorn automatically.

### Running automatically on Windows boot
To run the Video Server in the background without needing a user to log in:
1. Open Task Scheduler (`taskschd.msc`).
2. Click Create Task and name it `SleepCare_Video_Server`.
3. Set the trigger to "At system startup".
4. Set the action to run `C:\CPAP_Video_Server\start_server.bat`.
5. Select "Run whether user is logged on or not" and check "Run with highest privileges".

---

## 3. CPAP AI Supervisor Server setup (VM3)

### Host requirements
- Operating System: Windows Server 2022 Datacenter
- Address: `159.84.143.151`
- Ports: Port 8000 for the REST API and dashboard; Port 8001 for the webhook companion daemon.

### Installation
```powershell
cd C:\CPAP_AI_Server
& "C:\Program Files\Python312\python.exe" -m pip install fastapi uvicorn requests pandas numpy scipy scikit-learn lightgbm catboost xgboost lifelines jupyter
```

### Starting the AI Server
```cmd
c:\CPAP_AI_Server\run_ai_server.bat
```
What happens at launch:
1. Sets `PYTHONUTF8=1` so logging doesn't fail on Unicode characters.
2. Runs `scripts/clear_ports.py` to scan ports 8000 and 8001, freeing them if previous instances hung.
3. Opens `http://localhost:8000/dashboard` in the browser.
4. Starts FastAPI on port 8000 and the sync daemon on port 8001.

---

## 4. Environment variable reference

### Raspberry Pi edge (`CPAP_Raspberry_Pi/.env`)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `API_KEY` | None | Shared secret header required for `/ingest` and `/timing`. |
| `VIDEO_VM_URL` | `http://159.84.143.246:8080` | URL of the Video Server. Leave empty to disable video push. |
| `VIDEO_SERVER_API_KEY` | None | Sent to the Video VM as `X-API-KEY`. |
| `GENERATION_TIMEOUT_S` | `20` | Timeout in seconds when waiting for generative video. |
| `BACKEND_API_URL` | `http://159.84.143.151:80/api/telemetry` | Central backend telemetry endpoint. |
| `BACKEND_API_KEY` | None | Sent to the backend as `X-API-Key`. |
| `TELEMETRY_ENABLED` | `true` | Set to false to disable telemetry reporting. |
| `LIBRARY_ROOT` | `.` | Directory where video metadata JSON files are stored. |

### CPAP Video Server (`CPAP_Video_Server/.env`)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | IP interface to bind. |
| `PORT` | `8080` | Listening port. |
| `PUBLIC_BASE_URL` | `http://159.84.143.246:8080` | URL prefix returned in video links. |
| `DASHBOARD_URL` | `http://159.84.143.151:80` | Central clinical portal URL. |
| `BACKEND_API_URL` | `http://159.84.143.151:80/api/telemetry` | Telemetry endpoint on the clinical backend. |
| `BACKEND_API_KEY` | None | Header secret for backend telemetry writes. |
| `AI_SERVER_URL` | `http://159.84.143.151:8001/api/triggers/sync` | Target endpoint for AI server catalog sync. |
| `RPI_EDGE_URL` | `http://159.84.143.246:8000/api/triggers/sync` | Target endpoint for Pi edge catalog sync. |
| `SERVER_API_KEY` | None | Expected value for `X-API-KEY` on write endpoints. |
| `VIDEO_SERVER_KEY` | None | Key sent to the central backend (`X-Video-Server-Key`). |
| `GOOGLE_VERTEX_API_KEY` | None | Google Cloud key for Veo 3.1 video synthesis. |
| `GOOGLE_CLOUD_PROJECT` | None | Google Cloud project ID. |
| `GOOGLE_CLOUD_LOCATION`| `us-central1` | Vertex AI region. |
| `VERTEX_MODEL` | `veo-3.1-generate-preview` | Model name used for video rendering. |

### CPAP AI Supervisor Server (`CPAP_AI_Server/.env`)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `SERVER_HOST` | `0.0.0.0` | IP interface to bind. |
| `SERVER_PORT` | `8000` | Port for dashboard and main API. |
| `WEBHOOK_PORT` | `8001` | Dedicated port for catalog sync webhook. |
| `BACKEND_API_URL` | `http://159.84.143.151/api/data` | URL for central database queries. |
| `BACKEND_API_KEY` | None | Ingestion key for central database (`X-ML-Key`). |
| `AI_SERVER_API_KEY` | None | Key protecting internal AI endpoints (`X-API-KEY`). |
| `VIDEO_SERVER_URL` | `http://159.84.143.246:8080` | Base URL of the Video VM. |
| `VIDEO_SERVER_API_KEY` | None | Key sent to the Video VM. |
| `SYNC_INTERVAL_MINUTES`| `30` | Minutes between automatic pipeline runs. |

---

## 5. Verification commands

Run these from your terminal to verify that each node is responding:

```bash
# 1. Check Pi edge node
curl -s http://localhost:8000/health

# 2. Check Video VM
curl -s http://159.84.143.246:8080/health

# 3. Check that subtitles return without caching headers
curl -I http://159.84.143.246:8080/subtitles/1_Mask_leak_adjust_straps.en.vtt

# 4. Check AI Server on port 8000
curl -s http://159.84.143.151:8000/health

# 5. Check AI Server webhook listener on port 8001
curl -s http://159.84.143.151:8001/health
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for local testing procedures.
