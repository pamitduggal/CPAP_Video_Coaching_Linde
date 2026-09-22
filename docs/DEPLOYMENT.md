# SleepCare CPAP Ecosystem — Production Deployment & Operations Guide

> **DISP Laboratory (Lyon) & Linde HomeCare France**  
> *Author: Pamit Duggal (Software & AI Engineering Intern)*  
> *Scope: Deployment Runbooks, System Services, Environment Reference & Health Checks*

---

## 1. Node 1: Raspberry Pi 5 Edge Deployment Runbook

### 1.1 Prerequisites
- **Hardware**: Raspberry Pi 5 (4GB or 8GB RAM), 32GB+ Class 10 MicroSD / NVMe SSD.
- **Operating System**: Raspberry Pi OS (64-bit) based on Debian Bookworm.
- **Network**: Wired Ethernet or dedicated 2.4/5GHz Wi-Fi with static DHCP lease.

### 1.2 Installation Steps
```bash
# 1. Clone repository to user home directory
cd ~/Desktop
git clone <repo-url> CPAP_Edge_copy
cd CPAP_Edge_copy

# 2. Initialize Python 3.11/3.12 Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install production dependencies
pip install --upgrade pip
pip install fastapi uvicorn requests pandas python-multipart slowapi python-dotenv

# 4. Configure environment variables
cp .env.example .env
nano .env  # Ensure API_KEY, VIDEO_VM_URL, and BACKEND_API_URL are set
```

### 1.3 Sync Catalog from Video VM
Before launching the service, verify connectivity with the Video VM and sync metadata for videos 28–37:
```bash
.venv/bin/python sync_catalog.py --check   # Dry run to inspect diffs
.venv/bin/python sync_catalog.py           # Syncs metadata/video_28..37.json
```

### 1.4 Launching the Service
```bash
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

### 1.5 Setting Up Tailscale Funnel (Public Cellular Ingress)
Because patient mobile phones operate over public cellular networks while the Pi sits behind a residential NAT router, **Tailscale Funnel** exposes port 8000 with end-to-end TLS:
```bash
# 1. Install and authenticate Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 2. Enable public Funnel on Port 8000
tailscale funnel 8000
```
Point the patient mobile app's `RECEIVER_BASE_URL` to `https://<your-node>.ts.net`.

### 1.6 Production Systemd Service (`/etc/systemd/system/cpap-edge.service`)
To ensure the edge service auto-starts on boot and restarts upon failure:
```ini
[Unit]
Description=SleepCare CPAP Raspberry Pi Edge Service
After=network.target tailscaled.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Desktop/CPAP_Edge_copy
ExecStart=/home/pi/Desktop/CPAP_Edge_copy/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
EnvironmentFile=/home/pi/Desktop/CPAP_Edge_copy/.env

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cpap-edge.service
sudo systemctl start cpap-edge.service
```

---

## 2. Node 2: CPAP Video Server Deployment Runbook (VM4)

### 2.1 Prerequisites
- **Operating System**: Windows Server 2022 Datacenter (x64)
- **Host Address**: `159.84.143.246`
- **Runtime**: Python 3.12 64-bit (`C:\Program Files\Python312\python.exe`)
- **Firewall Rules**: Port `8080` (Inbound TCP: Open for public streaming and API requests).

### 2.2 Directory Setup & Dependencies
```powershell
# In PowerShell (Administrator):
cd C:\CPAP_Video_Server

# Install required Python packages
& "C:\Program Files\Python312\python.exe" -m pip install fastapi uvicorn requests opencv-python pydantic python-dotenv
```

### 2.3 Starting the Server via `start_server.bat`
The launcher [`start_server.bat`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Video_Server/start_server.bat) executes automated pre-flight port checks and process supervision:
```cmd
c:\CPAP_Video_Server\start_server.bat
```
**Launcher Automation Workflow**:
1. Uses PowerShell to inspect Port `8080` and forcefully terminates any orphaned PID occupying the port.
2. Prints active configuration banner with listening IPs and asset counts (39 videos, 78 subtitles).
3. Spawns the default web browser to `http://localhost:8080/` after 1.5 seconds.
4. Executes `video_vm_server.py`, which wraps `uvicorn.run` in an infinite auto-recovery loop. If an unhandled Windows IOCP socket reset (`WinError 64`) occurs, the server automatically recovers in 0.5s.

### 2.4 Auto-Start via Windows Task Scheduler
To launch the Video Server automatically whenever Windows Server boots (without requiring an interactive user login):
1. Open **Task Scheduler** (`taskschd.msc`).
2. Create Task: `SleepCare_Video_Server`.
3. Trigger: **At system startup**.
4. Action: **Start a program** $\to$ `C:\CPAP_Video_Server\start_server.bat`.
5. Check: **Run whether user is logged on or not** and **Run with highest privileges**.

---

## 3. Node 3: CPAP AI Supervisor Server Deployment Runbook (VM3)

### 3.1 Prerequisites
- **Operating System**: Windows Server 2022 Datacenter (x64)
- **Host Address**: `159.84.143.151`
- **Ports**: Port `8000` (Main API & Dashboard), Port `8001` (Automated Webhook Companion Daemon).

### 3.2 Installation & Dependencies
```powershell
cd C:\CPAP_AI_Server
& "C:\Program Files\Python312\python.exe" -m pip install fastapi uvicorn requests pandas numpy scipy scikit-learn lightgbm catboost xgboost lifelines jupyter
```

### 3.3 Starting the AI Server via `run_ai_server.bat`
```cmd
c:\CPAP_AI_Server\run_ai_server.bat
```
**Launcher Automation Workflow**:
1. Sets `PYTHONUTF8=1` to guarantee UTF-8 console output.
2. Invokes [`scripts/clear_ports.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/scripts/clear_ports.py) to scan ports `8000` and `8001`, killing conflicting PIDs.
3. Automatically opens `http://localhost:8000/dashboard` in the default web browser.
4. Starts the dual-port FastAPI service: Port 8000 serves the web application; Port 8001 runs the companion webhook daemon.

---

## 4. Comprehensive Environment Variables Dictionary

### 4.1 Raspberry Pi Edge (`CPAP_Raspberry_Pi/.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `API_KEY` | *(configured in .env)* | Shared secret header required for `/ingest` and `/timing`. |
| `VIDEO_VM_URL` | `http://159.84.143.246:8080` | Base URL of Video Server VM4. Empty disables push. |
| `VIDEO_SERVER_API_KEY` | *(configured in .env)* | Sent to Video VM as `X-API-KEY`. |
| `GENERATION_TIMEOUT_S` | `20` | Max blocking timeout for Scenario 3 generation call. |
| `BACKEND_API_URL` | `http://159.84.143.151:80/api/telemetry` | Central backend URL for KPI telemetry push. |
| `BACKEND_API_KEY` | *(configured in .env)* | Sent to backend as `X-API-Key`. |
| `TELEMETRY_ENABLED` | `true` | Master killswitch for telemetry event trace push. |
| `LIBRARY_ROOT` | `.` | Root directory containing `metadata/*.json`. |

### 4.2 CPAP Video Server (`CPAP_Video_Server/.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Network binding interface. |
| `PORT` | `8080` | Listening port for media streaming and API requests. |
| `PUBLIC_BASE_URL` | `http://159.84.143.246:8080` | Public URL prefix for returned video & subtitle links. |
| `DASHBOARD_URL` | `http://159.84.143.151:80` | URL of the central clinical portal. |
| `BACKEND_API_URL` | `http://159.84.143.151:80/api/telemetry` | Central backend telemetry ingest URL. |
| `BACKEND_API_KEY` | *(configured in .env)* | Secret key for backend telemetry events. |
| `AI_SERVER_URL` | `http://159.84.143.151:8001/api/triggers/sync` | Webhook URL for AI Server catalog broadcasts. |
| `RPI_EDGE_URL` | `http://159.84.143.246:8000/api/triggers/sync` | Webhook URL for Pi Edge catalog broadcasts. |
| `SERVER_API_KEY` | *(configured in .env)* | Header token required for mutation routes (`X-API-KEY`). |
| `VIDEO_SERVER_KEY` | *(configured in .env)* | HMAC key sent to backend (`X-Video-Server-Key`). |
| `GOOGLE_VERTEX_API_KEY` | *(configured in .env)* | Google Cloud API key for Veo 3.1 video synthesis. |
| `GOOGLE_CLOUD_PROJECT` | `your-gcp-project-id` | Google Cloud Project ID. |
| `GOOGLE_CLOUD_LOCATION`| `us-central1` | GCP region for Vertex AI endpoints. |
| `VERTEX_MODEL` | `veo-3.1-generate-preview` | Foundation model ID for video generation. |

### 4.3 CPAP AI Supervisor Server (`CPAP_AI_Server/core/config.py`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `SERVER_HOST` | `0.0.0.0` | Network binding interface. |
| `SERVER_PORT` | `8000` | Primary REST API & interactive dashboard port. |
| `WEBHOOK_PORT` | `8001` | Dedicated companion webhook port for catalog sync. |
| `BACKEND_API_URL` | `http://159.84.143.151/api/data` | Base URL for central clinical database queries. |
| `BACKEND_API_KEY` | *(configured in .env)* | Ingestion key for central database (`X-ML-Key`). |
| `AI_SERVER_API_KEY` | *(configured in .env)* | API key protecting internal AI endpoints (`X-API-KEY`). |
| `VIDEO_SERVER_URL` | `http://159.84.143.246:8080` | Video VM server base URL. |
| `VIDEO_SERVER_API_KEY` | *(configured in .env)* | Bearer key for Video VM requests. |
| `SYNC_INTERVAL_MINUTES`| `30` | Periodic model pipeline execution cycle. |

---

## 5. Health Check & Validation Verification Commands

Execute these commands from any authorized terminal to verify cluster health:

```bash
# 1. Pi Edge Health Probe (Verifies 37 indexed videos)
curl -s http://localhost:8000/health | jq .

# 2. Video VM Health Probe (Verifies 39 indexed videos & ledger count)
curl -s http://159.84.143.246:8080/health | jq .

# 3. Video VM Subtitle Zero-Cache Header Verification
curl -I http://159.84.143.246:8080/subtitles/1_Mask_leak_adjust_straps.en.vtt

# 4. AI Server Health Probe (Verifies ML model status)
curl -s http://159.84.143.151:8000/health | jq .

# 5. AI Server Webhook Daemon Health Probe (Port 8001)
curl -s http://159.84.143.151:8001/health | jq .
```

---

*Proceed to [DEVELOPMENT.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/DEVELOPMENT.md) for local developer workflows and automated testing.*
