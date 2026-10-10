#!/usr/bin/env bash
# =======================================================
# Smart Shopping Cart - Jetson Orin Nano Headless Launcher
# =======================================================

# Ensure script runs from project root
cd "$(dirname "$0")"

# Check if TensorRT engine exists, otherwise fallback to PyTorch weights
MODEL="yolov8s.engine"
if [ ! -f "$MODEL" ]; then
    echo "[!] Warning: TensorRT engine ($MODEL) not found."
    echo "[*] Falling back to PyTorch model (yolov8s.pt)..."
    MODEL="yolov8s.pt"
fi

echo "======================================================="
echo " Starting Smart Shopping Cart Engine on Jetson"
echo " Model:    $MODEL"
echo " Camera:   Auto-detecting /dev/video* (Index 0)"
echo " API Port: 5000 (http://0.0.0.0:5000/cart)"
echo " Mode:     Headless Daemon"
echo "======================================================="

python3 main_cart.py --camera 0 --model "$MODEL" --conf 0.18 --headless --port 5000
