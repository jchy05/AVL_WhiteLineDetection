@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" lane_pipeline_viewer.py %*
) else (
    python lane_pipeline_viewer.py %*
)
if errorlevel 1 pause
