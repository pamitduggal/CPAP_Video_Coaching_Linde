@echo off
cd /d C:\CPAP_AI_Server

set DATA_DIR=C:\CPAP_AI_Server\data
set NOTEBOOK_NAME=M4_FINAL_F2.ipynb
set SERVER_HOST=0.0.0.0
set SERVER_PORT=8000
set SYNC_INTERVAL_MINUTES=30
set RUN_MODE=SERVER

:: AI Server & Backend Security Settings
if "%AI_SERVER_API_KEY%"=="" set AI_SERVER_API_KEY=your_ai_server_key_here
if "%BACKEND_API_KEY%"=="" set BACKEND_API_KEY=your_backend_api_key_here
set PIPELINE_TIMEOUT_SECONDS=900
set MAX_PIPELINE_RETRIES=1

:: Video VM Server Settings (Port 8080)
set VIDEO_SERVER_URL=http://159.84.143.246:8080
if "%VIDEO_SERVER_API_KEY%"=="" set VIDEO_SERVER_API_KEY=your_video_server_api_key_here
if "%VIDEO_SERVER_KEY%"=="" set VIDEO_SERVER_KEY=your_video_server_key_here

cls
echo ===============================================================================
echo                SLEEPCARE CPAP AI MODEL SERVER - LIVE CONSOLE
echo ===============================================================================
echo  [SERVER CONFIGURATION]
echo    HOST               : %SERVER_HOST%
echo    PORT               : %SERVER_PORT%
echo    SWAGGER DOCS       : http://159.84.143.246:%SERVER_PORT%/docs
echo    SYNC INTERVAL      : Every %SYNC_INTERVAL_MINUTES% minutes
echo    BACKEND SOURCE     : http://159.84.143.151/api/data
echo    SERVER AUTH KEY    : %AI_SERVER_API_KEY:~0,8%... (enforced)
echo    VIDEO VM SERVER    : %VIDEO_SERVER_URL%
echo    VIDEO VM API KEY   : %VIDEO_SERVER_API_KEY:~0,8%... (active)
echo    VIDEO SERVER KEY   : %VIDEO_SERVER_KEY:~0,8%... (active)
echo    PIPELINE TIMEOUT   : %PIPELINE_TIMEOUT_SECONDS%s (retry: %MAX_PIPELINE_RETRIES%)
echo.
echo  [LIVE LOGGING ENABLED]
echo    * Real-time HTTP requests, client IPs, and response status
echo    * Detailed video stream requests (file name, range, client)
echo    * Inbound orchestration events (patient ID, title, trigger reason)
echo    * Dashboard push status and latency
echo    * Vertex AI generation triggers and metadata indexing
echo ===============================================================================
echo.

set PYTHONPATH=%CD%;%PYTHONPATH%
set PYTHONSTARTUP=%CD%\sitecustomize.py
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

"C:\Program Files\Python312\python.exe" api_data_loader.py --server

pause
