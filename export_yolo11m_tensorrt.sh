#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/../.venv}"
MODEL_SOURCE="${MODEL_SOURCE:-$SCRIPT_DIR/yolo11m.pt}"
ENGINE_DIR="${ENGINE_DIR:-$SCRIPT_DIR/models}"
IMGSZ="${IMGSZ:-320}"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "[!] Python virtualenv not found: $VENV_DIR" >&2
    exit 1
fi
if [[ ! -f "$MODEL_SOURCE" ]]; then
    echo "[!] YOLO11m weights not found: $MODEL_SOURCE" >&2
    echo "    Download yolo11m.pt first, or set MODEL_SOURCE=/path/to/yolo11m.pt." >&2
    exit 1
fi

cd "$SCRIPT_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
mkdir -p "$ENGINE_DIR"

echo "[*] Exporting YOLO11m to TensorRT FP16 on this Jetson..."
echo "    Source: $MODEL_SOURCE"
echo "    Image size: $IMGSZ"

python - "$MODEL_SOURCE" "$ENGINE_DIR" "$IMGSZ" <<'PY'
import sys
from pathlib import Path
from ultralytics import YOLO

source = Path(sys.argv[1])
output_dir = Path(sys.argv[2])
imgsz = int(sys.argv[3])

exported = YOLO(str(source)).export(
    format="engine",
    half=True,
    imgsz=imgsz,
    device=0,
)
exported_path = Path(exported)
target = output_dir / "yolo11m.engine"
if exported_path.resolve() != target.resolve():
    target.write_bytes(exported_path.read_bytes())
print(f"[*] TensorRT engine ready: {target}")
PY

echo "[*] Start the tracker with: ./run_cart_tracker.sh"
