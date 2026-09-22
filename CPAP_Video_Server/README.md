# CPAP Just-in-Time Video Coaching: Video Server (VM4)

FastAPI media delivery service and generative video orchestration engine.  
DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France.

---

## Role in the platform

The Video Server acts as the media repository and streaming daemon for the SleepCare network. It runs on a Windows Server VM (VM4) and delivers 39 coaching clips along with French and English subtitles over standard HTTP 206 byte ranges.

When the edge node or AI supervisor selects an intervention, it tells this server which clip or sequence to stage. The server:
- Streams MP4 video with byte-range seeking so phones can buffer anywhere in the file without waiting for a full download.
- Delivers synchronized WebVTT subtitles in English and French.
- Serves Scenario 2 dual-clip playlists with client-side crossfades (`fade_1_5s`), avoiding the latency of stitching video files together on the server.
- Uses an in-memory deduplication engine to check whether a prompt for Google Veo 3.1 has already been rendered before hitting external cloud APIs.
- Records patient video assignments in `assignment_ledger.py` and forwards the assignment to the central clinical backend.
- Serves a local operations dashboard on port 8080 for testing playback and inspecting event streams.

---

## Directory layout

```text
CPAP_Video_Server/
├── video_vm_server.py            # Main FastAPI streaming service (:8080)
├── deduplication_engine.py       # Prompt hasher and semantic cache for generative video
├── assignment_ledger.py          # Atomic JSON ledger of patient assignments
├── build_video_metadata.py       # OpenCV script that profiles video resolution and cue lines
├── calculate_kpis.py             # Script to verify video availability and subtitle parity
├── sync_remote_nodes.py          # Broadcasts trigger changes to AI and Edge nodes
├── update_master_metadata.py     # Aggregates individual video JSONs into master catalog
├── start_server.bat              # Windows batch file to launch Uvicorn with auto-recovery
├── dashboard/                    # Web UI assets for clinical operations console
├── existing_videos/              # 37 curated 1080p MP4 coaching clips (1 to 37)
├── new_videos/                   # 2 AI-generated 1080p MP4 clips (38 and 39)
├── existing_subtitles/           # 74 WebVTT subtitle files (EN and FR)
├── new_subtitles/                # 4 WebVTT subtitle files (EN and FR)
├── metadata/                     # Metadata records and catalog indexes
└── .env.example                  # Environment variable template
```

---

## Quick start

### 1. Configure environment
```powershell
copy .env.example .env
```
Populate `SERVER_API_KEY`, `VIDEO_SERVER_KEY`, and `BACKEND_API_KEY`. If you plan to test live video generation with Google Veo, also provide `GOOGLE_VERTEX_API_KEY` and your Google Cloud project ID.

### 2. Start the service
```powershell
.\start_server.bat
```
The server will start on port 8080. Open `http://localhost:8080/` in a browser on the host to check the console.

Check the health endpoint:
```powershell
curl http://localhost:8080/health
```

---

## Detailed documentation

For complete schemas and operational runbooks, see the documents in `docs/`:

| Topic | Document |
| :--- | :--- |
| End-to-end system topology | [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) |
| Streaming implementation and deduplication shield | [docs/COMPONENTS.md](../docs/COMPONENTS.md) |
| File and module inventory | [docs/CODEBASE_MAP.md](../docs/CODEBASE_MAP.md) |
| Orchestration and generation API specs | [docs/API.md](../docs/API.md) |
| Complete route index | [docs/ROUTES.md](../docs/ROUTES.md) |
| Assignment ledger and prompt cache layout | [docs/STATE.md](../docs/STATE.md) |
| Windows service deployment | [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) |
| Adding new coaching videos and extracting cues | [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) |
| Intern handover notes | [docs/HANDOVER_REPORT.md](../docs/HANDOVER_REPORT.md) |
| Video prompts and concepts guide (PDF) | [docs/resources/CPAP_Wearables_Video_Ideas_and_Google_Veo_Prompts.pdf](../docs/resources/CPAP_Wearables_Video_Ideas_and_Google_Veo_Prompts.pdf) |
