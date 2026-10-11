#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -n "${PYTHON_BIN:-}" ]]; then
    python_bin="$PYTHON_BIN"
elif [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    python_bin="$SCRIPT_DIR/.venv/bin/python"
else
    python_bin="python3"
fi

camera="${CAMERA_INDEX:-0}"
device="${DEVICE:-}"
if [[ -n "${MODEL_PATH:-}" ]]; then
    model="$MODEL_PATH"
elif [[ -f "$SCRIPT_DIR/models/yolo11m.engine" ]]; then
    model="$SCRIPT_DIR/models/yolo11m.engine"
else
    model="yolov8n.pt"
    echo "[!] YOLO11m TensorRT engine not found; using YOLOv8 PyTorch fallback: $model"
fi
confidence="${CONFIDENCE:-0.20}"
imgsz="${IMGSZ:-640}"
max_fps="${MAX_FPS:-5}"
if [[ -z "$device" ]]; then
    if [[ "$model" == *.engine ]]; then
        device="0"
    else
        device="cpu"
    fi
fi

echo "Starting Smart Cart Tracker"
echo "Camera: $camera | Model: $model | Device: $device"

exec "$python_bin" main_cart.py \
    --camera "$camera" \
    --model "$model" \
    --conf "$confidence" \
    --imgsz "$imgsz" \
    --max-fps "$max_fps" \
    --device "$device"
