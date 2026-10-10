import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import cv2

_GLOBAL_INVENTORY = None
_LATEST_FRAME_LOCK = threading.Lock()
_LATEST_JPEG = None

def set_global_inventory(inv):
    global _GLOBAL_INVENTORY
    _GLOBAL_INVENTORY = inv

def update_web_frame(frame):
    global _LATEST_JPEG
    if frame is None:
        return
    try:
        h, w = frame.shape[:2]
        small_frame = cv2.resize(frame, (640, int(h * 640 / w)))
        ret, jpeg = cv2.imencode(".jpg", small_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ret:
            with _LATEST_FRAME_LOCK:
                _LATEST_JPEG = jpeg.tobytes()
    except Exception:
        pass

class CartHTTPRequestHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # Prevent browser aggressive caching so every fetch/refresh gets fresh data
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        global _GLOBAL_INVENTORY, _LATEST_JPEG

        # Endpoint 1: Live Interactive HTML Dashboard (Auto-refreshes every 500ms)
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self._send_cors_headers()
            self.end_headers()

            html = """<!DOCTYPE html>
<html>
<head>
    <title>Smart Shopping Cart - Live Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; text-align: center; }
        .card { max-width: 480px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }
        h1 { margin-top: 0; color: #38bdf8; font-size: 24px; }
        .item-row { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; margin: 10px 0; background: #334155; border-radius: 10px; font-size: 18px; }
        .count-badge { background: #0284c7; color: white; padding: 4px 14px; border-radius: 20px; font-weight: bold; font-size: 20px; }
        .total-box { margin-top: 20px; padding: 16px; background: #0284c7; border-radius: 10px; font-size: 20px; font-weight: bold; }
        .live-dot { height: 10px; width: 10px; background-color: #22c55e; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
        a { color: #38bdf8; text-decoration: none; font-size: 14px; display: inline-block; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🛒 Smart Cart Live <span class="live-dot"></span></h1>
        <div id="items">Loading...</div>
        <div class="total-box" id="total">Total Items: 0</div>
        <br>
        <a href="/video_feed" target="_blank">📹 View Live Camera Stream</a> | 
        <a href="/cart" target="_blank">{ JSON API }</a>
    </div>

    <script>
        async function updateCart() {
            try {
                const res = await fetch('/cart?t=' + Date.now());
                const data = await res.json();
                const items = data.items;
                let html = '';
                
                const icons = { 'apple': '🍎 Apple', 'banana': '🍌 Banana', 'bottle': '💧 Water Bottle' };
                for (const [key, val] of Object.entries(items)) {
                    const label = icons[key] || key.toUpperCase();
                    html += `<div class="item-row"><span>${label}</span><span class="count-badge">${val}</span></div>`;
                }
                document.getElementById('items').innerHTML = html;
                document.getElementById('total').innerText = 'Total Items: ' + data.total_items;
            } catch (err) {
                console.error(err);
            }
        }
        setInterval(updateCart, 400); // Live poll every 400ms
        updateCart();
    </script>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        # Endpoint 2: Raw JSON API
        elif self.path.startswith("/cart"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()

            tally = _GLOBAL_INVENTORY.tally if _GLOBAL_INVENTORY else {"apple": 0, "banana": 0, "bottle": 0}
            total = sum(tally.values())
            data = {
                "status": "success",
                "items": tally,
                "total_items": total,
            }
            self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

        # Endpoint 3: Snapshot JPEG
        elif self.path == "/snapshot":
            with _LATEST_FRAME_LOCK:
                jpeg_data = _LATEST_JPEG

            if jpeg_data:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(jpeg_data)
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"Frame not ready")

        # Endpoint 4: Video Feed
        elif self.path == "/video_feed":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self._send_cors_headers()
            self.end_headers()

            try:
                while True:
                    with _LATEST_FRAME_LOCK:
                        jpeg_data = _LATEST_JPEG

                    if jpeg_data:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n\r\n")
                        self.wfile.write(jpeg_data)
                        self.wfile.write(b"\r\n")
                    threading.Event().wait(0.08)
            except Exception:
                pass
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global _GLOBAL_INVENTORY
        if self.path == "/cart/reset":
            if _GLOBAL_INVENTORY:
                _GLOBAL_INVENTORY.tally = {"apple": 0, "banana": 0, "bottle": 0}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b'{"status": "reset_success", "items": {"apple": 0, "banana": 0, "bottle": 0}}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

def start_http_server(inventory, host="0.0.0.0", port=5000):
    set_global_inventory(inventory)
    server = HTTPServer((host, port), CartHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[*] Live Web UI Dashboard: http://localhost:{port}/")
    print(f"[*] JSON API Endpoint:     http://localhost:{port}/cart")
    return server
