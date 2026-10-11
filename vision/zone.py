import json
import os
import cv2
import numpy as np

class CartPolygonZone:
    """
    Defines and manages the 4-corner perspective quadrilateral polygon
    representing the physical shopping cart entrance rim.
    """
    def __init__(self, config_path="config/zone_config.json"):
        self.config_path = config_path
        # Normalized coordinates [x, y] in ratio (0.0 to 1.0)
        # Order: [Top-Left, Top-Right, Bottom-Right, Bottom-Left]
        self.default_corners = [
            [0.10, 0.20],  # P1: Top-Left (Far rim)
            [0.90, 0.20],  # P2: Top-Right (Far rim)
            [0.95, 0.90],  # P3: Bottom-Right (Near handle rim)
            [0.05, 0.90],  # P4: Bottom-Left (Near handle rim)
        ]
        self.corners = list(self.default_corners)
        self.selected_corner_idx = -1
        self.load_config()

    def get_pixel_corners(self, frame_width, frame_height):
        """Returns np.ndarray of shape (4, 2) in integer pixel coordinates."""
        pts = []
        for x_r, y_r in self.corners:
            px = int(x_r * frame_width)
            py = int(y_r * frame_height)
            pts.append([px, py])
        return np.array(pts, dtype=np.int32)

    def get_zone_status(self, cx, cy, frame_width, frame_height):
        """
        Tests whether the centroid (cx, cy) is inside or outside the cart polygon.
        Returns:
            - 'INSIDE': Point is within the polygon rim
            - 'OUTSIDE': Point is outside the polygon rim
            - 'ON_BORDER': Point is right on the boundary line
        """
        pts = self.get_pixel_corners(frame_width, frame_height)
        # cv2.pointPolygonTest: >0 inside, <0 outside, 0 on edge
        dist = cv2.pointPolygonTest(pts, (float(cx), float(cy)), measureDist=True)
        if dist > 3.0:
            return "INSIDE", dist
        elif dist < -3.0:
            return "OUTSIDE", dist
        else:
            return "ON_BORDER", dist

    def draw(self, frame, show_handles=True, show_zone=True):
        """Renders the semi-transparent polygon, border lines, and corner draggable handles."""
        h, w = frame.shape[:2]
        pts = self.get_pixel_corners(w, h)

        if show_zone:
            # 1. Draw semi-transparent filled polygon
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], (255, 180, 0))
            alpha = 0.25
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

            # 2. Draw solid boundary outline
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 255), thickness=3)

            # Label the rims
            p1, p2, p3, p4 = pts
            cv2.putText(
                frame,
                "FAR RIM (FRONT)",
                (int((p1[0] + p2[0]) / 2) - 60, max(25, int((p1[1] + p2[1]) / 2) - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                "NEAR RIM (HANDLEBAR)",
                (int((p4[0] + p3[0]) / 2) - 80, min(h - 15, int((p4[1] + p3[1]) / 2) + 22)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # 3. Draw corner handles for calibration
        if show_zone and show_handles:
            corner_labels = ["P1 (Top-L)", "P2 (Top-R)", "P3 (Btm-R)", "P4 (Btm-L)"]
            for i, (px, py) in enumerate(pts):
                is_active = (i == self.selected_corner_idx)
                handle_color = (0, 0, 255) if is_active else (0, 255, 0)
                radius = 12 if is_active else 8

                cv2.circle(frame, (px, py), radius, handle_color, -1)
                cv2.circle(frame, (px, py), radius + 2, (255, 255, 255), 2)
                cv2.putText(
                    frame,
                    corner_labels[i],
                    (px + 12, py + 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

        return frame

    def handle_mouse_event(self, event, x, y, flags, param, frame_width, frame_height):
        """Interactive mouse callback to drag corners."""
        pts = self.get_pixel_corners(frame_width, frame_height)

        if event == cv2.EVENT_LBUTTONDOWN:
            # Check if clicked near any of the 4 corners (radius 25px)
            for i, (px, py) in enumerate(pts):
                distance = np.hypot(x - px, y - py)
                if distance <= 25:
                    self.selected_corner_idx = i
                    print(f"[*] Selected corner P{i+1}")
                    break

        elif event == cv2.EVENT_MOUSEMOVE and self.selected_corner_idx != -1:
            # Update position of selected corner
            norm_x = max(0.0, min(1.0, x / frame_width))
            norm_y = max(0.0, min(1.0, y / frame_height))
            self.corners[self.selected_corner_idx] = [round(norm_x, 4), round(norm_y, 4)]

        elif event == cv2.EVENT_LBUTTONUP:
            if self.selected_corner_idx != -1:
                print(f"[*] Released corner P{self.selected_corner_idx+1}")
                self.selected_corner_idx = -1

    def save_config(self):
        """Saves current polygon corners to JSON."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = {
            "type": "quadrilateral_polygon",
            "corners": self.corners
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[*] Cart polygon calibration saved to: {self.config_path}")

    def load_config(self):
        """Loads saved polygon corners from JSON."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    if "corners" in data and len(data["corners"]) == 4:
                        self.corners = data["corners"]
                        print(f"[*] Loaded polygon calibration from {self.config_path}")
            except Exception as e:
                print(f"[!] Warning: Failed loading config: {e}")

    def reset_defaults(self):
        """Resets corners to default proportions."""
        self.corners = list(self.default_corners)
        print("[*] Polygon corners reset to defaults.")
