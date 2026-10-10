import argparse
import sys
import time
import cv2
import numpy as np
from ultralytics import YOLO
from vision.zone import CartPolygonZone
from vision.camera import open_camera, open_preferred_camera

def parse_args():
    parser = argparse.ArgumentParser(description="Shopping Cart 4-Corner Polygon Zone & Inside/Outside Tracker")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0; the other USB index is tried automatically)")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="YOLO model path (Nano default: yolov8n.pt)")
    parser.add_argument("--conf", type=float, default=0.28, help="Detection confidence threshold")
    parser.add_argument("--imgsz", type=int, default=320, help="Inference image size (default: 320 for Jetson Nano)")
    parser.add_argument("--max-fps", type=float, default=5.0, help="Maximum inference rate (default: 5 FPS for Jetson Nano)")
    return parser.parse_args()

def main():
    args = parse_args()

    print(f"[*] Loading model: {args.model}...")
    model = YOLO(args.model)

    # Pre-trained COCO classes: bottle (39), banana (46), apple (47)
    target_names = {"apple", "banana", "bottle"}
    target_class_ids = [
        cls_id for cls_id, name in model.names.items() if name.lower() in target_names
    ]
    print(f"[*] Target classes: {[model.names[i] for i in target_class_ids]} (IDs: {target_class_ids})")

    print(f"[*] Opening Camera {args.camera}...")
    cap, actual_camera = open_preferred_camera(args.camera)
    if actual_camera is not None:
        args.camera = actual_camera

    if not cap.isOpened():
        print("[!] Error: No available camera found.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Initialize Cart Polygon Zone
    zone = CartPolygonZone()

    window_name = "Smart Cart Zone Calibration - Drag 4 Corners | 's'=Save | 'q'=Quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # Attach interactive mouse callback for corner dragging
    def on_mouse(event, x, y, flags, param):
        w = param.get("w", 1280)
        h = param.get("h", 720)
        zone.handle_mouse_event(event, x, y, flags, None, w, h)

    param_dict = {"w": 1280, "h": 720}
    cv2.setMouseCallback(window_name, on_mouse, param_dict)

    print("\n" + "=" * 65)
    print(" Calibration Instructions:")
    print("  * LEFT-CLICK & DRAG any of the 4 Green corner dots to snap")
    print("    the polygon to the 4 metal corners of your cart rim.")
    print("  * [s] : SAVE calibration to config/zone_config.json")
    print("  * [r] : RESET polygon to defaults")
    print("  * [c] : Switch camera (0 <-> 1)")
    print("  * [+] / [-] : Adjust detection sensitivity")
    print("  * [q] / ESC : Quit")
    print("=" * 65 + "\n")

    current_camera = args.camera
    conf_threshold = args.conf
    next_inference = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[!] Error reading camera frame.")
                break

            h, w = frame.shape[:2]
            param_dict["w"] = w
            param_dict["h"] = h
            now = time.monotonic()
            if now < next_inference:
                cv2.imshow(window_name, frame)
                cv2.waitKey(1)
                continue
            next_inference = now + (1.0 / args.max_fps if args.max_fps > 0 else 0)

            # Run YOLO detection
            results = model.predict(
                frame,
                classes=target_class_ids,
                conf=conf_threshold,
                imgsz=args.imgsz,
                max_det=10,
                verbose=False,
            )

            # Draw polygon zone on frame
            annotated_frame = frame.copy()
            annotated_frame = zone.draw(annotated_frame, show_handles=True)

            inside_count = 0
            outside_count = 0

            # Process detections
            for box in results[0].boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                name = model.names[cls_id]

                x1, y1, x2, y2 = map(int, xyxy)
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                # Check INSIDE / OUTSIDE status
                status, dist = zone.get_zone_status(cx, cy, w, h)

                if status == "INSIDE":
                    inside_count += 1
                    # Bright Emerald Green for INSIDE
                    tag_color = (0, 255, 0)
                    flag_text = f"INSIDE CART ({name})"
                elif status == "OUTSIDE":
                    outside_count += 1
                    # Bold Crimson Red for OUTSIDE
                    tag_color = (0, 0, 255)
                    flag_text = f"OUTSIDE CART ({name})"
                else:
                    tag_color = (0, 255, 255)
                    flag_text = f"ON RIM ({name})"

                # 1. Draw bounding box with status color
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), tag_color, 2)

                # 2. Draw centroid target marker
                cv2.circle(annotated_frame, (cx, cy), 6, tag_color, -1)
                cv2.circle(annotated_frame, (cx, cy), 8, (255, 255, 255), 2)

                # 3. Draw prominent Visual Status Badge above box
                badge_w = 180
                badge_h = 24
                bx1 = max(0, x1)
                by1 = max(0, y1 - badge_h - 4)
                cv2.rectangle(annotated_frame, (bx1, by1), (bx1 + badge_w, by1 + badge_h), tag_color, -1)
                cv2.putText(
                    annotated_frame,
                    flag_text,
                    (bx1 + 6, by1 + 17),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (0, 0, 0) if status == "INSIDE" else (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

                # Confidence label
                cv2.putText(
                    annotated_frame,
                    f"{conf:.2f}",
                    (x1, y2 + 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (220, 220, 220),
                    1,
                    cv2.LINE_AA,
                )

            # Top Status HUD Header
            hud_bg = (25, 25, 25)
            cv2.rectangle(annotated_frame, (10, 10), (700, 50), hud_bg, -1)
            hud_text = f"INSIDE: {inside_count}  |  OUTSIDE: {outside_count}  |  Conf: {conf_threshold:.2f}  |  Cam: {current_camera}"
            cv2.putText(
                annotated_frame,
                hud_text,
                (20, 37),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 230),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('s'):
                zone.save_config()
            elif key == ord('r'):
                zone.reset_defaults()
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

if __name__ == "__main__":
    main()
