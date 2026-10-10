import argparse
import sys
import time
import cv2
from ultralytics import YOLO
from vision.camera import open_camera, open_preferred_camera

from vision.zone import CartPolygonZone
from core.inventory import CartInventory
from core.cart_tracker import DirectCountCartTracker
from core.server import start_http_server, update_web_frame

def parse_args():
    parser = argparse.ArgumentParser(description="Smart Shopping Cart - Direct Count ADD/REMOVE Tracker")
    parser.add_argument("--camera", type=int, default=1, help="Camera index (default: 1 for USB webcam)")
    parser.add_argument("--model", type=str, default="yolov8s.pt", help="YOLO model weight file")
    parser.add_argument("--conf", type=float, default=0.18, help="Detection confidence threshold")
    parser.add_argument("--port", type=int, default=5000, help="HTTP API Port (default: 5000)")
    parser.add_argument("--headless", action="store_true", help="Run headlessly without OpenCV window (for Jetson/Cart)")
    return parser.parse_args()

def main():
    args = parse_args()

    print(f"[*] Initializing YOLO Model: {args.model}...")
    model = YOLO(args.model)

    # Whitelist COCO classes: bottle (39), banana (46), apple (47)
    target_names = {"apple", "banana", "bottle"}
    target_class_ids = [
        cls_id for cls_id, name in model.names.items() if name.lower() in target_names
    ]
    print(f"[*] Target classes: {[model.names[i] for i in target_class_ids]} (IDs: {target_class_ids})")

    # Initialize Cart Polygon Zone
    zone = CartPolygonZone()

    # Initialize Inventory and Direct Count Tracker
    inventory = CartInventory()
    tracker = DirectCountCartTracker(inventory=inventory, confirm_frames=3)

    # 🚀 Start Background HTTP API Server (Serves http://localhost:5000/cart)
    start_http_server(inventory, host="0.0.0.0", port=args.port)

    print(f"[*] Connecting to Camera index {args.camera}...")
    cap, actual_camera = open_preferred_camera(args.camera, width=1280, height=720)
    if actual_camera is not None:
        args.camera = actual_camera

    if not cap.isOpened():
        print("[!] Error: Could not open any camera device. Check USB connection.")
        sys.exit(1)

    window_name = "Smart Cart Tracker - Drag Corners | 's'=Save | 'r'=Reset | 'q'=Quit"
    param_dict = {"w": 1280, "h": 720}

    if not args.headless:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        def on_mouse(event, x, y, flags, param):
            w = param_dict.get("w", 1280)
            h = param_dict.get("h", 720)
            zone.handle_mouse_event(event, x, y, flags, None, w, h)
        cv2.setMouseCallback(window_name, on_mouse)

    print("\n" + "=" * 65)
    print(" Smart Shopping Cart System Running!")
    print(f" 🌐 Tablet HTTP API:   http://localhost:{args.port}/cart")
    print(f" 📹 Web Camera Stream: http://localhost:{args.port}/video_feed")
    print(" Controls:")
    print("   * DRAG CORNERS : Adjust 4 green dots to fit cart entrance rim")
    print("   [s]            : SAVE corner calibration to config file")
    print("   [r]            : Reset cart inventory tally to 0")
    print("   [c]            : Switch camera (0 <-> 1)")
    print("   [+] / [-]      : Adjust detection confidence")
    print("   [q] / ESC      : Quit")
    print("=" * 65 + "\n")

    current_camera = args.camera
    conf_threshold = args.conf
    fail_count = 0

    fps = 0.0
    frame_count = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                fail_count += 1
                if fail_count >= 10:
                    print("[!] Video stream stalled. Reconnecting...")
                    cap.release()
                    time.sleep(0.5)
                    cap, actual_camera = open_preferred_camera(current_camera, width=1280, height=720)
                    fail_count = 0
                else:
                    time.sleep(0.01)
                continue

            fail_count = 0
            h, w = frame.shape[:2]
            param_dict["w"] = w
            param_dict["h"] = h

            # 1. YOLO Inference
            results = model.predict(
                frame,
                classes=target_class_ids,
                conf=conf_threshold,
                imgsz=640,
                verbose=False,
            )

            # 2. Extract Detections
            raw_detections = []
            for box in results[0].boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                name = model.names[cls_id]

                x1, y1, x2, y2 = map(int, xyxy)
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                raw_detections.append({
                    "name": name,
                    "conf": conf,
                    "box": [x1, y1, x2, y2],
                    "centroid": (cx, cy),
                })

            # 3. Draw Polygon Zone
            annotated_frame = frame.copy()
            annotated_frame = zone.draw(annotated_frame, show_handles=True)

            # 4. Direct Count Delta Tracking & Triggers
            tracked_detections = tracker.process_frame(raw_detections, zone, w, h)

            # 5. Draw HUD & Badges
            annotated_frame = tracker.draw_hud(annotated_frame, tracked_detections, zone)

            # 6. Stream frame to web server for browser/phone viewing
            update_web_frame(annotated_frame)

            # FPS calculation
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()

            cv2.putText(
                annotated_frame,
                f"FPS: {fps:.1f} | Conf: {conf_threshold:.2f} | Cam: {current_camera} | API :5000",
                (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 200),
                1,
                cv2.LINE_AA,
            )

            if not args.headless:
                cv2.imshow(window_name, annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break
                elif key == ord('s'):
                    zone.save_config()
                elif key == ord('r'):
                    inventory.tally = {"apple": 0, "banana": 0, "bottle": 0}
                    tracker.confirmed_counts = {"apple": 0, "banana": 0, "bottle": 0}
                    for k in tracker.frame_history:
                        tracker.frame_history[k].clear()
                    print("\n[*] Cart inventory tally reset to 0.")
                elif key == ord('c'):
                    new_camera = 0 if current_camera == 1 else 1
                    cap.release()
                    new_cap = open_camera(new_camera, width=1280, height=720)
                    if new_cap.isOpened():
                        cap = new_cap
                        current_camera = new_camera
                    else:
                        new_cap.release()
                        cap = open_camera(current_camera, width=1280, height=720)
                elif key in [ord('+'), ord('=')]:
                    conf_threshold = min(0.95, round(conf_threshold + 0.05, 2))
                    print(f"[*] Conf: {conf_threshold}")
                elif key in [ord('-'), ord('_')]:
                    conf_threshold = max(0.10, round(conf_threshold - 0.05, 2))
                    print(f"[*] Conf: {conf_threshold}")
            else:
                time.sleep(0.01)

    finally:
        cap.release()
        if not args.headless:
            cv2.destroyAllWindows()
        print("\n[*] Shopping session closed.")
        print(f"[*] Final Cart State: {inventory.tally}")

if __name__ == "__main__":
    main()
