@echo off
cd /d "%~dp0"
echo =======================================================
echo Starting High-Speed Smart Cart Tracker
echo Model: YOLOv8 Nano (Fast FPS)
echo Camera: External USB Webcam (Index 1)
echo =======================================================
.\.venv\Scripts\python.exe main_cart.py --camera 1 --model yolov8n.pt --conf 0.20
pause
