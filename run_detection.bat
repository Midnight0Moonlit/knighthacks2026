@echo off
cd /d "%~dp0"
echo =======================================================
echo Starting YOLO Object Detection
echo Model: YOLOv8 Small (stronger detection accuracy)
echo Camera: Defaulting to External USB Camera (Index 1)
echo =======================================================
.\.venv\Scripts\python.exe detect_objects.py --camera 1 --model yolov8s.pt --conf 0.28
pause
