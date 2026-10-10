import argparse
import sys
import time
import cv2
import torch
from ultralytics import YOLO
from vision.camera import open_camera, open_preferred_camera
from vision.zone import CartPolygonZone

def parse_args():
    parser = argparse.ArgumentParser(description="YOLO Target Object Detection")
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera index to use (default: 0; the other USB index is tried automatically)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n.pt",
        help="YOLO model weight: yolov8n.pt (recommended for Jetson Nano), yolov8s.pt, or yolov8m.pt",
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
        default=320,
        help="Inference image resolution size (default: 320 for Jetson Nano)",
    )
    parser.add_argument(
        "--max-fps",
        type=float,
        default=5.0,
        help="Maximum inference rate (default: 5 FPS for Jetson Nano)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Inference device: cpu or CUDA index such as 0 (default: cpu for stability)",
    )
    parser.add_argument(
        "--camera-only",
        action="store_true",
        help="Display the camera without loading or running YOLO",
    )
    parser.add_argument(
        "--zone-config",
        type=str,
        default="config/zone_config.json",
        help="Path to the adjustable four-corner zone configuration",
    )
    return parser.parse_args()

def main():
    args = parse_args()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)

    model = None
    if not args.camera_only:
        print(f"[*] Loading model: {args.model} on {args.device}...")
        model = YOLO(args.model)

    target_class_ids = []
    if model is not None:
        target_names = {"apple", "banana", "orange", "bottle"}
        target_class_ids = [
            cls_id for cls_id, name in model.names.items() if name.lower() in target_names
        ]
        print(f"[*] Target classes: {[model.names[i] for i in target_class_ids]} (IDs: {target_class_ids})")

    print(f"[*] Connecting to Camera index {args.camera}...")
    cap, actual_camera = open_preferred_camera(args.camera)
    if actual_camera is not None:
        args.camera = actual_camera

    if not cap.isOpened():
        print("[!] Error: No accessible cameras found!")
        sys.exit(1)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[*] Camera {args.camera} initialized at {actual_w}x{actual_h}")

    zone = CartPolygonZone(args.zone_config)
    window_name = (
        f"YOLO Detection [Cam {args.camera} | {args.model}] - "
        "Drag zone corners | 's' save | 'q' quit"
    )
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    frame_size = {"width": actual_w, "height": actual_h}

    def on_mouse(event, x, y, flags, param):
        zone.handle_mouse_event(
            event,
            x,
            y,
            flags,
            param,
            frame_size["width"],
            frame_size["height"],
        )

    cv2.setMouseCallback(window_name, on_mouse)

    print("\n" + "=" * 55)
    print(f" Model: {args.model} | Conf: {args.conf}")
    print(f" Camera: Index {args.camera}")
    print(" Targets: Apple, Banana, Orange, Water Bottle")
    print(" Controls:")
    print("   [q] or [ESC] : Quit")
    print("   [c]          : Toggle between Camera 0 and 1")
    print("   [drag]       : Move a zone corner")
    print("   [s]          : Save the zone corners")
    print("   [r]          : Reset the zone corners")
    print("   [+] / [-]    : Adjust confidence threshold")
    print("=" * 55 + "\n")

    current_camera = args.camera
    conf_threshold = args.conf

    fps = 0.0
    frame_count = 0
    start_time = time.time()
    next_inference = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[!] Error reading frame from camera.")
                break

            frame_size["height"], frame_size["width"] = frame.shape[:2]
            now = time.monotonic()
            if now < next_inference:
                cv2.waitKey(1)
                continue
            next_inference = now + (1.0 / args.max_fps if args.max_fps > 0 else 0)

            counts = {}
            annotated_frame = frame
            if model is not None:
                # YOLO inference
                results = model.predict(
                    frame,
                    classes=target_class_ids,
                    conf=conf_threshold,
                    imgsz=args.imgsz,
                    max_det=5,
                    device=args.device,
                    verbose=False,
                )
                annotated_frame = results[0].plot()

                for box in results[0].boxes:
                    cls_id = int(box.cls[0].item())
                    label = model.names[cls_id]
                    counts[label] = counts.get(label, 0) + 1

            zone.draw(annotated_frame)

            # Calculate FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()

            # Status overlays
            summary_text = "Targets: " + (", ".join([f"{k}: {v}" for k, v in counts.items()]) if counts else "None")
            mode_text = "camera-only" if model is None else f"{args.model} @ {args.device}"
            info_text = f"Cam: {current_camera} | FPS: {fps:.1f} | {mode_text}"

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
                else:
                    print(f"[!] Could not open camera {new_camera}, reverting back.")
                    cap = open_camera(current_camera)
            elif key == ord('s'):
                zone.save_config()
            elif key == ord('r'):
                zone.reset_defaults()
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
