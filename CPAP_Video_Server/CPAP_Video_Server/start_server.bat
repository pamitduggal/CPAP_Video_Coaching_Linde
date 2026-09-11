@echo off
setlocal enabledelayedexpansion

title CPAP Video VM Server (Port 8080)
cd /d C:\CPAP_Video_Server

if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=8080
if "%VIDEO_BASE_DIR%"=="" set VIDEO_BASE_DIR=C:\CPAP_Video_Server
if "%PUBLIC_BASE_URL%"=="" set PUBLIC_BASE_URL=http://159.84.143.246:8080
if "%DASHBOARD_BASE_URL%"=="" set DASHBOARD_BASE_URL=http://159.84.143.151:80
if "%DASHBOARD_URL%"=="" set DASHBOARD_URL=http://159.84.143.151:80
if "%SERVER_API_KEY%"=="" set SERVER_API_KEY=your_server_api_key_here
if "%VIDEO_SERVER_API_KEY%"=="" set VIDEO_SERVER_API_KEY=your_server_api_key_here
if "%VIDEO_SERVER_KEY%"=="" set VIDEO_SERVER_KEY=your_video_server_key_here
if "%X_VIDEO_SERVER_KEY%"=="" set X_VIDEO_SERVER_KEY=your_video_server_key_here

cls
echo ===============================================================================
echo                   CPAP VIDEO VM SERVER - LIVE CONSOLE
echo ===============================================================================
echo  [SERVER CONFIGURATION]
echo    HOST               : %HOST%
echo    PORT               : %PORT%
echo    BASE DIRECTORY     : %VIDEO_BASE_DIR%
echo    PUBLIC BASE URL    : %PUBLIC_BASE_URL%
echo    DASHBOARD URL      : %DASHBOARD_BASE_URL%
echo    SECURITY KEY       : %SERVER_API_KEY:~0,8%... (active)
echo    VIDEO WEBHOOK KEY  : %VIDEO_SERVER_KEY:~0,8%... (active)
echo.
echo  [LIVE LOGGING ENABLED]
echo    * Real-time HTTP requests, client IPs, and response status
echo    * Detailed video stream requests (file name, range, client)
echo    * Inbound orchestration events (patient ID, title, trigger reason)
echo    * Dashboard push status and latency
echo    * Vertex AI generation triggers and metadata indexing
echo ===============================================================================
echo.

set PYTHON_BIN="C:\Program Files\Python312\python.exe"
if not exist %PYTHON_BIN% (
    set PYTHON_BIN=python
)

echo [BOOT] Starting Uvicorn server on %HOST%:%PORT%...
echo.

%PYTHON_BIN% video_vm_server.py

echo.
echo ===============================================================================
echo Server process stopped or terminated.
echo ===============================================================================
pause