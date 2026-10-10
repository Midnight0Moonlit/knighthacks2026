"""Safe, headless V4L2 camera probe for Jetson/Linux USB cameras."""

import argparse
import glob
import sys
import time

import cv2


def parse_args():
    parser = argparse.ArgumentParser(description="Probe a Linux V4L2 camera without YOLO or a GUI")
    parser.add_argument(
        "--device",
        default="/dev/video0",
        help="V4L2 device path (default: /dev/video0)",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=10,
        help="Number of frames to read before exiting (default: 10)",
    )
    parser.add_argument(
        "--format",
        choices=("MJPG", "H264", "YUYV"),
        default="MJPG",
        help="V4L2 pixel format to request (default: MJPG)",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    return parser.parse_args()


def main():
    args = parse_args()
    devices = sorted(glob.glob("/dev/video*"))
    print(f"[*] Video devices present: {devices or 'none'}", flush=True)
    print(f"[*] Opening {args.device} with V4L2...", flush=True)

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"[!] Could not open {args.device}", flush=True)
        return 1

    print("[+] Device opened", flush=True)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*args.format))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_text = "".join(chr((fourcc >> (8 * byte)) & 0xFF) for byte in range(4))
    print(f"[*] Negotiated format: {width}x{height}, {fps:.1f} FPS, {fourcc_text!r}", flush=True)

    successful_frames = 0
    started = time.monotonic()
    try:
        for frame_number in range(1, args.frames + 1):
            print(f"[*] Reading frame {frame_number}/{args.frames}...", flush=True)
            ok, frame = cap.read()
            if not ok or frame is None:
                print("[!] Frame read failed", flush=True)
                return 1

            successful_frames += 1
            print(
                f"[+] Frame {frame_number}: shape={frame.shape}, bytes={frame.nbytes}",
                flush=True,
            )
    finally:
        cap.release()

    elapsed = time.monotonic() - started
    print(f"[+] Camera probe passed: {successful_frames} frames in {elapsed:.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
