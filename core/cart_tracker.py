import time
import collections
import cv2

class DirectCountCartTracker:
    """
    Dead-Simple Hackathon Inventory Engine.
    
    1. Counts visible items inside the calibrated cart polygon per frame.
    2. Debounces with a 4-frame confirmation window to eliminate camera flicker.
    3. Triggers ADD when stable inside count increases.
    4. Triggers REMOVE when stable inside count decreases.
    """
    def __init__(self, inventory, confirm_frames=3):
        self.inventory = inventory
        self.confirm_frames = confirm_frames

        # Buffer of raw counts for the last N frames
        # {class_name: collections.deque([count_t0, count_t1, ...], maxlen=confirm_frames)}
        self.frame_history = {
            "apple": collections.deque(maxlen=confirm_frames),
            "banana": collections.deque(maxlen=confirm_frames),
            "bottle": collections.deque(maxlen=confirm_frames),
        }

        # Confirmed stable state
        self.confirmed_counts = {
            "apple": 0,
            "banana": 0,
            "bottle": 0,
        }

        self.last_event_banner = None
        self.last_event_time = 0.0

    def process_frame(self, raw_detections, polygon_zone, frame_width, frame_height):
        """
        raw_detections: list of dicts [{'name': str, 'conf': float, 'box': [x1,y1,x2,y2], 'centroid': (cx, cy)}]
        """
        # Current frame counts inside the cart
        current_inside = {"apple": 0, "banana": 0, "bottle": 0}

        for det in raw_detections:
            name = det["name"]
            cx, cy = det["centroid"]

            # Query if centroid is inside polygon
            status, dist = polygon_zone.get_zone_status(cx, cy, frame_width, frame_height)
            det["zone_status"] = status
            det["zone_dist"] = dist

            if status == "INSIDE" and name in current_inside:
                current_inside[name] += 1

        # Push to debounce history and check for stable delta changes
        for item_name, count in current_inside.items():
            history = self.frame_history[item_name]
            history.append(count)

            # Only update confirmed count if we have enough consistent frames
            if len(history) == self.confirm_frames:
                # If all recent frames agree on the count
                if len(set(history)) == 1:
                    stable_count = history[0]
                    prev_count = self.confirmed_counts[item_name]

                    # -----------------------------------------------
                    # 🟢 ADD EVENT: Stable count increased
                    # -----------------------------------------------
                    if stable_count > prev_count:
                        diff = stable_count - prev_count
                        for _ in range(diff):
                            self.inventory.add_item(item_name, 1, 1.0)
                        self.confirmed_counts[item_name] = stable_count
                        self.last_event_banner = f"+ ADDED {diff}x {item_name.upper()}"
                        self.last_event_time = time.time()

                    # -----------------------------------------------
                    # 🔴 REMOVE EVENT: Stable count decreased
                    # -----------------------------------------------
                    elif stable_count < prev_count:
                        diff = prev_count - stable_count
                        for _ in range(diff):
                            self.inventory.remove_item(item_name, 1, 1.0)
                        self.confirmed_counts[item_name] = stable_count
                        self.last_event_banner = f"- REMOVED {diff}x {item_name.upper()}"
                        self.last_event_time = time.time()

        return raw_detections

    def draw_hud(self, frame, detections, polygon_zone):
        """Renders bounding boxes, inside/outside badges, live inventory tally card, and event banners."""
        h, w = frame.shape[:2]

        for det in detections:
            name = det["name"]
            conf = det["conf"]
            x1, y1, x2, y2 = det["box"]
            cx, cy = det["centroid"]
            status = det.get("zone_status", "OUTSIDE")

            # Green for INSIDE, Red for OUTSIDE
            tag_color = (0, 255, 0) if status == "INSIDE" else (0, 0, 255)

            # Draw Box & Centroid
            cv2.rectangle(frame, (x1, y1), (x2, y2), tag_color, 2)
            cv2.circle(frame, (cx, cy), 6, tag_color, -1)
            cv2.circle(frame, (cx, cy), 8, (255, 255, 255), 2)

            # Draw Badge
            badge_text = f"{name.upper()} [{status}]"
            text_size = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            bw = text_size[0] + 16
            bh = text_size[1] + 12
            bx1 = max(0, x1)
            by1 = max(0, y1 - bh - 4)

            cv2.rectangle(frame, (bx1, by1), (bx1 + bw, by1 + bh), tag_color, -1)
            text_color = (0, 0, 0) if status == "INSIDE" else (255, 255, 255)
            cv2.putText(
                frame,
                badge_text,
                (bx1 + 8, by1 + bh - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                text_color,
                2,
                cv2.LINE_AA,
            )

        # Top-Right: Cart Inventory Tally Card
        tally = self.inventory.tally
        box_w = 260
        box_h = 135
        bx1 = w - box_w - 15
        by1 = 15

        cv2.rectangle(frame, (bx1, by1), (bx1 + box_w, by1 + box_h), (20, 20, 20), -1)
        cv2.rectangle(frame, (bx1, by1), (bx1 + box_w, by1 + box_h), (0, 255, 200), 2)
        cv2.putText(frame, "CART INVENTORY", (bx1 + 15, by1 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2, cv2.LINE_AA)

        cv2.putText(frame, f"Apples:       {tally.get('apple', 0)}", (bx1 + 15, by1 + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"Bananas:      {tally.get('banana', 0)}", (bx1 + 15, by1 + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"Water Bottles:{tally.get('bottle', 0)}", (bx1 + 15, by1 + 105), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        # Top-Left: Event Banner (2.5s auto-fade)
        if self.last_event_banner and (time.time() - self.last_event_time < 2.5):
            banner_color = (0, 180, 0) if "+ ADDED" in self.last_event_banner else (0, 80, 255)
            cv2.rectangle(frame, (15, 15), (340, 55), banner_color, -1)
            cv2.putText(frame, self.last_event_banner, (25, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        return frame

# Aliases for backward compatibility
DirectionalGateTracker = DirectCountCartTracker
CartTracker = DirectCountCartTracker
