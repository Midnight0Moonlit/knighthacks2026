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
model="${MODEL_PATH:-yolov8n.pt}"

echo "Starting cart zone calibration"
echo "Camera: $camera | Model: $model"

exec "$python_bin" calibrate_zone.py \
    --camera "$camera" \
    --model "$model"
