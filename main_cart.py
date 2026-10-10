import argparse
import sys
import time
import cv2
from ultralytics import YOLO

from vision.zone import CartPolygonZone
from core.inventory import CartInventory
from core.cart_tracker import CartTracker

def parse_args():
    parser = argparse.ArgumentParser(description="Smart Shopping Cart - Dynamic ADD/REMOVE Tracker")
    parser.add_argument("--camera", type=int, default=1, help="Camera index (default: 1 for USB webcam)")
    parser.add_argument("--model", type=str, default="yolov8s.pt", help="YOLO model weight file")
    parser.add_argument("--conf", type=float, default=0.28, help="Detection confidence threshold")
    return parser.parse_args()

def open_camera(index):
    # Use DirectShow backend on Windows
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)

    # 1. Clear out internal OS driver buffer so it never builds up lag or overflows
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cap

def main():
    args = parse_args()

    print(f"[*] Initializing YOLO Model: {args.model}...")
    model = YOLO(args.model)

    # Pre-trained COCO classes: bottle (39), banana (46), apple (47)
    target_names = {"apple", "banana", "bottle"}
    target_class_ids = [
        cls_id for cls_id, name in model.names.items() if name.lower() in target_names
    ]
    print(f"[*] Active target whitelist: {[model.names[i] for i in target_class_ids]} (IDs: {target_class_ids})")

    # Initialize Cart Polygon Zone
    zone = CartPolygonZone()

    # Initialize In-Memory Inventory and State Machine Tracker
    inventory = CartInventory()
    tracker = CartTracker(inventory=inventory)

    print(f"[*] Opening Camera {args.camera}...")
    cap = open_camera(args.camera)
    if not cap.isOpened():
        print(f"[!] Camera {args.camera} unavailable, falling back to 0...")
        cap = open_camera(0)
        args.camera = 0

    if not cap.isOpened():
        print("[!] Error: No available camera found.")
        sys.exit(1)

    window_name = "Smart Shopping Cart [Live Tracking] - Press 'c'=Cam, 'r'=Reset Tally, 'q'=Quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    print("\n" + "=" * 65)
    print(" Smart Shopping Cart System Running!")
    print(" Targets: Apple, Banana, Water Bottle")
    print(" Controls:")
    print("   [r]       : Reset cart inventory tally to 0")
    print("   [c]       : Switch camera (0 <-> 1)")
    print("   [+] / [-] : Adjust detection confidence")
    print("   [q] / ESC : Quit")
    print("=" * 65 + "\n")

    current_camera = args.camera
    conf_threshold = args.conf
    consecutive_fail_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                consecutive_fail_count += 1
                if consecutive_fail_count >= 5:
                    print("[!] Frame read timeout. Re-opening camera stream...")
                    cap.release()
                    time.sleep(0.5)
                    cap = open_camera(current_camera)
                    consecutive_fail_count = 0
                else:
                    time.sleep(0.02)
                continue

            consecutive_fail_count = 0
            h, w = frame.shape[:2]

            # Run YOLO with ByteTrack enabled for persistent ID assignment
            results = model.track(
                frame,
                persist=True,
                classes=target_class_ids,
                conf=conf_threshold,
                imgsz=640,
                verbose=False,
            )

            # Draw calibrated polygon zone
            annotated_frame = frame.copy()
            annotated_frame = zone.draw(annotated_frame, show_handles=False)

            # Parse tracked detections
            detections = []
            if results[0].boxes and results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                track_ids = results[0].boxes.id.int().cpu().tolist()
                clss = results[0].boxes.cls.int().cpu().tolist()
                confs = results[0].boxes.conf.cpu().tolist()

                for box, track_id, cls_id, conf in zip(boxes, track_ids, clss, confs):
                    x1, y1, x2, y2 = map(int, box)
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    name = model.names[cls_id]

                    detections.append({
                        "track_id": track_id,
                        "name": name,
                        "conf": conf,
                        "box": [x1, y1, x2, y2],
                        "centroid": (cx, cy),
                    })

                    # Draw item box
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
                    cv2.circle(annotated_frame, (cx, cy), 5, (0, 255, 255), -1)

            # Process state machine & inventory updates
            tracker.process_frame_tracks(detections, zone, w, h)

            # Draw trails, status badges, and live inventory card
            annotated_frame = tracker.draw_tracks_and_hud(annotated_frame, detections, zone)

            cv2.imshow(window_name, annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('r'):
                # Reset tally
                inventory.tally = {"apple": 0, "banana": 0, "bottle": 0}
                print("\n[*] Cart inventory tally reset to 0.")
            elif key == ord('c'):
                current_camera = 0 if current_camera == 1 else 1
                cap.release()
                cap = open_camera(current_camera)
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
