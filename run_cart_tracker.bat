@echo off
cd /d "%~dp0"
echo =======================================================
echo Starting Smart Cart Tracker
echo Model: YOLOv8 Small (High Accuracy for Wire Mesh/Bottles)
echo Camera: External USB Webcam (Index 1)
echo =======================================================
.\.venv\Scripts\python.exe main_cart.py --camera 1 --model yolov8s.pt --conf 0.18
pause
