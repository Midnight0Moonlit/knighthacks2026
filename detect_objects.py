import argparse
import sys
import time
import cv2
from ultralytics import YOLO

def parse_args():
    parser = argparse.ArgumentParser(description="YOLO Target Object Detection")
    parser.add_argument(
        "--camera",
        type=int,
        default=1,
        help="Camera index to use (default: 1 for external USB webcam, 0 for laptop webcam)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8s.pt",
        help="YOLO model weight: yolov8s.pt (recommended balance), yolov8m.pt (higher accuracy), yolov8n.pt (fastest)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.28,
        help="Confidence threshold for detections (default: 0.28)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Inference image resolution size (default: 640)",
    )
    return parser.parse_args()

def open_camera(index):
    # Use DirectShow backend on Windows for reliable USB device capture
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        # Fallback to default backend
        cap = cv2.VideoCapture(index)
    return cap

def main():
    args = parse_args()

    print(f"[*] Loading model: {args.model}...")
    model = YOLO(args.model)

    target_names = {"apple", "banana", "orange", "bottle"}
    target_class_ids = [
        cls_id for cls_id, name in model.names.items() if name.lower() in target_names
    ]
    print(f"[*] Target classes: {[model.names[i] for i in target_class_ids]} (IDs: {target_class_ids})")

    print(f"[*] Connecting to Camera index {args.camera}...")
    cap = open_camera(args.camera)

    if not cap.isOpened():
        print(f"[!] Warning: Camera index {args.camera} could not be opened. Falling back to camera 0...")
        cap = open_camera(0)
        args.camera = 0

    if not cap.isOpened():
        print("[!] Error: No accessible cameras found!")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[*] Camera {args.camera} initialized at {actual_w}x{actual_h}")

    window_name = f"YOLO Detection [Cam {args.camera} | {args.model}] - Press 'c' to switch cam, 'q' to quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    print("\n" + "=" * 55)
    print(f" Model: {args.model} | Conf: {args.conf}")
    print(f" Camera: Index {args.camera}")
    print(" Targets: Apple, Banana, Orange, Water Bottle")
    print(" Controls:")
    print("   [q] or [ESC] : Quit")
    print("   [c]          : Toggle between Camera 0 and 1")
    print("   [+] / [-]    : Adjust confidence threshold")
    print("=" * 55 + "\n")

    current_camera = args.camera
    conf_threshold = args.conf

    fps = 0.0
    frame_count = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[!] Error reading frame from camera.")
                break

            # YOLO inference
            results = model.predict(
                frame,
                classes=target_class_ids,
                conf=conf_threshold,
                imgsz=args.imgsz,
                verbose=False,
            )

            annotated_frame = results[0].plot()

            # Count detected targets
            counts = {}
            for box in results[0].boxes:
                cls_id = int(box.cls[0].item())
                label = model.names[cls_id]
                score = float(box.conf[0].item())
                counts[label] = counts.get(label, 0) + 1

            # Calculate FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()

            # Status overlays
            summary_text = "Targets: " + (", ".join([f"{k}: {v}" for k, v in counts.items()]) if counts else "None")
            info_text = f"Cam: {current_camera} | Conf: {conf_threshold:.2f} | FPS: {fps:.1f} | Model: {args.model}"

            # Semi-transparent HUD header
            cv2.rectangle(annotated_frame, (10, 10), (620, 80), (20, 20, 20), -1)
            cv2.putText(
                annotated_frame,
                summary_text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 120),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                annotated_frame,
                info_text,
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (220, 220, 220),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('c'):
                # Switch camera between 0 and 1
                new_camera = 0 if current_camera == 1 else 1
                print(f"[*] Switching to camera index {new_camera}...")
                cap.release()
                cap = open_camera(new_camera)
                if cap.isOpened():
                    current_camera = new_camera
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                else:
                    print(f"[!] Could not open camera {new_camera}, reverting back.")
                    cap = open_camera(current_camera)
            elif key == ord('+') or key == ord('='):
                conf_threshold = min(0.95, round(conf_threshold + 0.05, 2))
                print(f"[*] Increased confidence threshold to: {conf_threshold}")
            elif key == ord('-') or key == ord('_'):
                conf_threshold = max(0.10, round(conf_threshold - 0.05, 2))
                print(f"[*] Decreased confidence threshold to: {conf_threshold}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[*] Stream stopped. Resources cleaned up.")

if __name__ == "__main__":
    main()
