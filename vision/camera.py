"""Camera helpers for USB webcams on desktop Linux, Jetson, and Windows."""

import platform

import cv2


def open_camera(index, width=640, height=360):
    """Open a camera with a backend suitable for the current operating system."""
    if platform.system() == "Windows":
        backends = (cv2.CAP_DSHOW, cv2.CAP_ANY)
    else:
        # Jetson USB cameras are V4L2 devices.  Keep CAP_ANY as a fallback for
        # OpenCV builds that do not include the V4L2 backend.
        backends = (cv2.CAP_V4L2, cv2.CAP_ANY)

    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            continue

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # Set the compressed format before dimensions. Otherwise some V4L2
        # drivers select raw YUYV, which can open successfully but stall on a
        # Jetson USB bus.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        return cap

    return cv2.VideoCapture()


def open_preferred_camera(preferred, width=640, height=360):
    """Try the requested camera, then the other common USB camera index."""
    candidates = [preferred] + [index for index in (0, 1) if index != preferred]
    for index in candidates:
        cap = open_camera(index, width, height)
        if cap.isOpened():
            return cap, index
        cap.release()
    return cv2.VideoCapture(), None
