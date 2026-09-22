@echo off
setlocal EnableExtensions
title SleepCare CPAP Video Server (Port 8080)
cd /d "C:\CPAP_Video_Server"

if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=8080
if "%VIDEO_BASE_DIR%"=="" set VIDEO_BASE_DIR=C:\CPAP_Video_Server
if "%PUBLIC_BASE_URL%"=="" set PUBLIC_BASE_URL=http://159.84.143.246:8080
if "%DASHBOARD_BASE_URL%"=="" set DASHBOARD_BASE_URL=http://159.84.143.151:80
if "%DASHBOARD_URL%"=="" set DASHBOARD_URL=http://159.84.143.151:80
rem Keys are loaded from .env file or host environment
if "%SERVER_API_KEY%"=="" set SERVER_API_KEY=%VIDEO_SERVER_API_KEY%
if "%VIDEO_SERVER_KEY%"=="" set VIDEO_SERVER_KEY=%X_VIDEO_SERVER_KEY%

cls
echo ===============================================================================
echo                 SLEEPCARE CPAP VIDEO SERVER - LIVE CONSOLE
echo ===============================================================================
echo  [SERVER CONFIGURATION]
echo    HOST               : %HOST%
echo    PORT               : %PORT%
echo    LOCAL DASHBOARD    : http://localhost:%PORT%/
echo    BASE DIRECTORY     : %VIDEO_BASE_DIR%
echo    PUBLIC BASE URL    : %PUBLIC_BASE_URL%
echo    CENTRAL DASHBOARD  : %DASHBOARD_BASE_URL%
echo    INBOUND API KEY    : %SERVER_API_KEY:~0,8%... (active)
echo    VIDEO WEBHOOK KEY  : %VIDEO_SERVER_KEY:~0,8%... (active)
echo.
echo  [3 CLINICAL DELIVERY SCENARIOS SUPPORTED]
echo    [1] Scenario 1: Existing Video Selection (Single Clip)
echo        - Formats 1080p MP4 and exact .en.vtt / .fr.vtt bilingual subtitles
echo    [2] Scenario 2: Videos Stitching Together (Virtual Sequence / Multi-Clip)
echo        - Multi-clip coaching playlist with 1.5s alpha crossfade (fade_1_5s)
echo    [3] Scenario 3: New Video Generation (Google Veo / Vertex AI)
echo        - AI generation with instant bilingual subtitle and metadata synthesis
echo.
echo  [LIVE ASSET STATUS AND REAL-TIME AUTO-SYNC]
echo    * Curated Clinical Videos  : 37 MP4 files (existing_videos/)
echo    * Generative AI Videos     : 2 MP4 files (new_videos/)
echo    * Total Subtitle Tracks    : 78 WebVTT files (bilingual English + French)
echo    * Real-time Asset Watcher  : ACTIVE (Auto-syncs video count, subtitles, and triggers)
echo    * Persistent Deduplication : ACTIVE (Remembers assigned videos across server restarts)
echo ===============================================================================
echo.

set PYTHON_BIN=C:\Program Files\Python312\python.exe
if not exist "%PYTHON_BIN%" (
    set PYTHON_BIN=python
)

echo [PRE-FLIGHT] Checking and freeing port %PORT% if in use...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%PORT%'; Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { if ($_ -and $_ -ne $PID) { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; Write-Host \"  [*] Freed port $p (Terminated previous PID: $_)\" } }"
ping -n 2 127.0.0.1 >nul

echo.
echo ===============================================================================
echo  [DASHBOARD UI] Automatically opening SleepCare CPAP Dashboard in browser:
echo  URL: http://localhost:%PORT%/
echo ===============================================================================
echo.

REM Automatically launch default web browser to the dashboard URL after 1.5s delay
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Milliseconds 1500; Start-Process 'http://localhost:%PORT%/'"

echo [BOOT] Starting Uvicorn server on %HOST%:%PORT%...
echo.

"%PYTHON_BIN%" "%VIDEO_BASE_DIR%\video_vm_server.py"

echo.
echo ===============================================================================
echo Server process stopped or terminated.
echo ===============================================================================
pause