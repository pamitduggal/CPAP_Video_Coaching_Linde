@echo off
setlocal enabledelayedexpansion
cd /d C:\CPAP_AI_Server

set DATA_DIR=C:\CPAP_AI_Server\data
set NOTEBOOK_NAME=M4_FINAL_F2.ipynb
set SERVER_HOST=0.0.0.0
set SERVER_PORT=8000
set WEBHOOK_PORT=8001
set SYNC_INTERVAL_MINUTES=30
set RUN_MODE=SERVER

:: AI Server and Backend Security Settings (Loaded from .env or environment)
if "%AI_SERVER_API_KEY%"=="" set AI_SERVER_API_KEY=%AI_SERVER_KEY%
if "%BACKEND_API_KEY%"=="" set BACKEND_API_KEY=%ML_KEY%
set PIPELINE_TIMEOUT_SECONDS=900
set MAX_PIPELINE_RETRIES=1

:: Video VM Server Settings (Port 8080)
set VIDEO_SERVER_URL=http://159.84.143.246:8080

:: Video Assignment Deduplication & Batch Throttling (0 = unlimited)
set MAX_VIDEO_DISPATCHES_PER_RUN=0

cls
echo ===============================================================================
echo                 SLEEPCARE CPAP AI MODEL SERVER - LIVE CONSOLE
echo ===============================================================================
echo   [SERVER CONFIGURATION]
echo     HOST               : %SERVER_HOST%
echo     PORT               : %SERVER_PORT%
echo     WEBHOOK PORT       : %WEBHOOK_PORT% [/api/triggers/sync active listener]
echo     SWAGGER DOCS       : http://159.84.143.246:%SERVER_PORT%/docs
echo     WEB DASHBOARD      : http://localhost:%SERVER_PORT%/dashboard
echo     PUBLIC DASHBOARD   : http://159.84.143.246:%SERVER_PORT%/dashboard
echo     SYNC INTERVAL      : Every %SYNC_INTERVAL_MINUTES% minutes
echo     BACKEND SOURCE     : http://159.84.143.151/api/data
echo     SERVER AUTH KEY    : [configured via env]
echo     VIDEO VM SERVER    : %VIDEO_SERVER_URL%
echo     VIDEO VM API KEY   : [configured via env]
echo     VIDEO SERVER KEY   : [configured via env]
echo     LOCAL CATALOG      : distributed_trigger_catalog.json [dynamic boolean logic]
echo     VIDEO TRACKER      : artifacts\assigned_videos_tracker.json [persistent deduplication active]
echo     PIPELINE TIMEOUT   : %PIPELINE_TIMEOUT_SECONDS%s [retries: %MAX_PIPELINE_RETRIES%]
echo.
echo   [CLINICAL VIDEO SCENARIOS SUPPORTED]
echo     * SCENARIO 1: Existing Video Selection [37 Curated Clinical MP4s]
echo     * SCENARIO 2: Compounding Multi-Issue Playlists [Ranked by Clinical Priority]
echo     * SCENARIO 3: Generative AI On-Demand [Google Vertex AI / Veo 3.1 Model]
echo.
echo   [MEDIA AND SUBTITLE ASSETS INVENTORY]
echo     * 39 Library Videos [37 Curated 1080p Coaching Clips + 2 AI-Generated Clips]
echo     * 78 Bilingual WebVTT Subtitles [39 English .en.vtt + 39 French .fr.vtt]
echo     * Dynamic Boolean Logic [AND: Concurrent Breaches / OR: Any Breach]
echo.
echo   [LIVE LOGGING ENABLED]
echo     * Real-time HTTP requests, client IPs, and response status
echo     * Dual-port listener: REST API and Dashboard (8000), Webhook Receiver (8001)
echo     * Detailed video stream requests [file name, subtitles, client]
echo     * Active Scenario logging [Scenario 1, Scenario 2, Scenario 3]
echo     * Inbound orchestration events [patient ID, title, trigger reason]
echo     * Fast-Path deduplication handling [sub-1ms response shield]
echo     * Dashboard push status and latency
echo ===============================================================================
echo.

set PYTHONPATH=%CD%;%PYTHONPATH%
set PYTHONSTARTUP=%CD%\sitecustomize.py
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Automatic Pre-flight Port Cleanup & Status Output
"C:\Program Files\Python312\python.exe" scripts\clear_ports.py %SERVER_PORT% %WEBHOOK_PORT%

echo ===============================================================================
echo   [DASHBOARD AUTO-LAUNCH]
echo     Launching interactive Web Dashboard in your default browser...
echo     * Local URL  : http://localhost:%SERVER_PORT%/dashboard
echo     * Public URL : http://159.84.143.246:%SERVER_PORT%/dashboard
echo.
echo     (Opening automatically in default browser...)
echo ===============================================================================
echo.

:: Automatically open default browser to localhost dashboard URL in background
start "" /b cmd /c "ping 127.0.0.1 -n 3 >nul && start http://localhost:%SERVER_PORT%/dashboard"

"C:\Program Files\Python312\python.exe" api_data_loader.py --server

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] AI Server exited with code %ERRORLEVEL%.
    pause
)

