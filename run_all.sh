#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/../.venv}"
LOG_DIR="${LOG_DIR:-${TMPDIR:-/tmp}/knighthacks2026}"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "[!] Python virtualenv not found: $VENV_DIR" >&2
    echo "    Set VENV_DIR to the directory containing bin/activate." >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "[!] npm is required but was not found in PATH." >&2
    exit 1
fi

cd "$SCRIPT_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
mkdir -p "$LOG_DIR"

backend_pid=""
frontend_pid=""
tracker_pid=""

stop_processes() {
    trap - EXIT INT TERM
    for pid in "$tracker_pid" "$frontend_pid" "$backend_pid"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    wait "$tracker_pid" "$frontend_pid" "$backend_pid" 2>/dev/null || true
}

trap stop_processes EXIT INT TERM

echo "[*] Using Python: $(command -v python)"
echo "[*] Starting Flask backend on http://localhost:5001"
python app.py > >(tee "$LOG_DIR/backend.log") 2>&1 &
backend_pid=$!

echo "[*] Starting Vite dashboard on http://localhost:5173"
npm run dev -- --host > >(tee "$LOG_DIR/frontend.log") 2>&1 &
frontend_pid=$!

echo "[*] Starting computer vision cart tracker"
./run_cart_tracker.sh > >(tee "$LOG_DIR/cart-tracker.log") 2>&1 &
tracker_pid=$!

echo
echo "[*] All services started."
echo "    Dashboard: http://localhost:5173"
echo "    Backend:   http://localhost:5001"
echo "    Logs:      $LOG_DIR"
echo "    Press Ctrl+C to stop everything."

wait -n "$backend_pid" "$frontend_pid" "$tracker_pid"
status=$?
echo "[!] A service exited; stopping the remaining services." >&2
exit "$status"
