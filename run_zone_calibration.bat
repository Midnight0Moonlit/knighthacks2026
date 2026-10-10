@echo off
cd /d "%~dp0"
echo Starting Cart Zone Calibration...
.\.venv\Scripts\python.exe calibrate_zone.py --camera 1 --model yolov8s.pt
pause
