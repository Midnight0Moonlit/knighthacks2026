@echo off
cd /d "%~dp0"
echo =======================================================
echo Starting Smart Shopping Cart Dynamic Tracker
echo Model: YOLOv8 Small + ByteTrack
echo Camera: External USB Webcam (Index 1)
echo =======================================================
.\.venv\Scripts\python.exe main_cart.py --camera 1 --model yolov8s.pt --conf 0.28
pause
