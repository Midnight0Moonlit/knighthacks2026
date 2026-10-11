import argparse
import sys
import time
import cv2
from ultralytics import YOLO
from vision.camera import open_camera, open_preferred_camera

from vision.zone import CartPolygonZone
from core.inventory import CartInventory
from core.cart_tracker import CartTracker

def parse_args():
    parser = argparse.ArgumentParser(description="Smart Shopping Cart - High-Speed ADD/REMOVE Tracker")
    parser.add_argument("--camera", type=int, default=1, help="Camera index (default: 1 for USB webcam)")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="YOLO model weight file (default: yolov8n.pt for high FPS)")
    parser.add_argument("--conf", type=float, default=0.22, help="Detection confidence threshold")
    parser.add_argument("--imgsz", type=int, default=320, help="Inference image size (default: 320 for Jetson Nano)")
    parser.add_argument("--max-fps", type=float, default=5.0, help="Maximum inference rate (default: 5 FPS for Jetson Nano)")
    parser.add_argument("--device", default="cpu", help="Inference device: cpu or CUDA index such as 0")
    return parser.parse_args()

def main():
    args = parse_args()

    print(f"[*] Initializing YOLO Model: {args.model} (High-Speed Nano)...")
    model = YOLO(args.model)

    # Pre-trained COCO classes: bottle (39), banana (46), apple (47)
    target_names = {"apple", "banana", "bottle"}
    target_class_ids = [
        cls_id for cls_id, name in model.names.items() if name.lower() in target_names
    ]
    print(f"[*] Target classes: {[model.names[i] for i in target_class_ids]} (IDs: {target_class_ids})")

    # Initialize Cart Polygon Zone
    zone = CartPolygonZone()

    # Initialize Inventory and Tracker
    inventory = CartInventory()
    tracker = CartTracker(inventory=inventory)

    print(f"[*] Opening Camera {args.camera}...")
    cap, actual_camera = open_preferred_camera(args.camera)
    if actual_camera is not None:
        args.camera = actual_camera

    if not cap.isOpened():
        print("[!] Error: No available camera found.")
        sys.exit(1)

    window_name = "Smart Cart Tracker - Drag Corners | 's'=Save | 'r'=Reset | 'q'=Quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # Enable interactive mouse dragging directly in the main app
    param_dict = {"w": 1280, "h": 720}
    def on_mouse(event, x, y, flags, param):
        w = param_dict.get("w", 1280)
        h = param_dict.get("h", 720)
        zone.handle_mouse_event(event, x, y, flags, None, w, h)

    cv2.setMouseCallback(window_name, on_mouse)

    print("\n" + "=" * 65)
    print(" Smart Shopping Cart System Running!")
    print(" Targets: Apple, Banana, Water Bottle")
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
    consecutive_fail_count = 0
    next_inference = 0.0

    fps = 0.0
    frame_count = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                consecutive_fail_count += 1
                if consecutive_fail_count >= 5:
                    print("[!] Camera frame read timeout. Re-opening stream...")
                    cap.release()
                    time.sleep(0.5)
                    cap = open_camera(current_camera)
                    consecutive_fail_count = 0
                else:
                    time.sleep(0.02)
                continue

            consecutive_fail_count = 0
            h, w = frame.shape[:2]
            now = time.monotonic()
            if now < next_inference:
                cv2.waitKey(1)
                continue
            next_inference = now + (1.0 / args.max_fps if args.max_fps > 0 else 0)
            param_dict["w"] = w
            param_dict["h"] = h

            # 1. Fast YOLO prediction (instantaneous, no ByteTrack delay)
            results = model.predict(
                frame,
                classes=target_class_ids,
                conf=conf_threshold,
                imgsz=args.imgsz,
                max_det=10,
                device=args.device,
                verbose=False,
            )

            # 2. Extract raw detections
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

            # 3. Draw polygon with draggable handles
            annotated_frame = frame.copy()
            annotated_frame = zone.draw(annotated_frame, show_handles=True)

            # 4. Update centroid tracker and state machine
            tracked_detections = tracker.process_frame(raw_detections, zone, w, h)

            # 5. Draw HUD, badges, trails, and inventory card
            annotated_frame = tracker.draw_hud(annotated_frame, tracked_detections, zone)

            # Calculate live FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()

            # FPS / Cam Overlay
            cv2.putText(
                annotated_frame,
                f"FPS: {fps:.1f} | Conf: {conf_threshold:.2f} | Cam: {current_camera}",
                (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 200),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('s'):
                zone.save_config()
            elif key == ord('r'):
                inventory.tally = {"apple": 0, "banana": 0, "bottle": 0}
                print("\n[*] Cart inventory tally reset to 0.")
            elif key == ord('c'):
                new_camera = 0 if current_camera == 1 else 1
                cap.release()
                new_cap = open_camera(new_camera)
                if new_cap.isOpened():
                    cap = new_cap
                    current_camera = new_camera
                else:
                    new_cap.release()
                    cap = open_camera(current_camera)
                    print(f"[!] Could not open camera {new_camera}; keeping camera {current_camera}.")
            elif key in [ord('+'), ord('=')]:
                conf_threshold = min(0.95, round(conf_threshold + 0.05, 2))
                print(f"[*] Conf: {conf_threshold}")
            elif key in [ord('-'), ord('_')]:
                conf_threshold = max(0.10, round(conf_threshold - 0.05, 2))
                print(f"[*] Conf: {conf_threshold}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n[*] Shopping session finished.")
        print(f"[*] Final Cart State: {inventory.tally}")

if __name__ == "__main__":
    main()
