import collections
import time
import numpy as np
import cv2

class TrackState:
    OUTSIDE = "OUTSIDE"
    ENTERING = "ENTERING"
    IN_CART = "IN_CART"
    EXITING = "EXITING"
    REMOVED = "REMOVED"

class SimpleCentroidTracker:
    """
    Lightweight, high-speed Euclidean distance centroid tracker.
    Assigns persistent IDs without the latency of ByteTrack/DeepSORT.
    """
    def __init__(self, max_disappeared=15, max_distance=120):
        self.next_object_id = 1
        self.objects = {}         # object_id -> centroid (cx, cy)
        self.disappeared = {}     # object_id -> count of consecutive frames lost
        self.classes = {}         # object_id -> class_name
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid, class_name):
        obj_id = self.next_object_id
        self.objects[obj_id] = centroid
        self.disappeared[obj_id] = 0
        self.classes[obj_id] = class_name
        self.next_object_id += 1
        return obj_id

    def deregister(self, obj_id):
        if obj_id in self.objects:
            del self.objects[obj_id]
        if obj_id in self.disappeared:
            del self.disappeared[obj_id]
        if obj_id in self.classes:
            del self.classes[obj_id]

    def update(self, detections):
        """
        detections: list of dicts [{'name': str, 'conf': float, 'box': [x1,y1,x2,y2], 'centroid': (cx, cy)}]
        Returns matched list with 'track_id' populated.
        """
        if len(detections) == 0:
            for obj_id in list(self.disappeared.keys()):
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)
            return []

        input_centroids = [d["centroid"] for d in detections]
        input_classes = [d["name"] for d in detections]

        if len(self.objects) == 0:
            for i, d in enumerate(detections):
                obj_id = self.register(input_centroids[i], input_classes[i])
                d["track_id"] = obj_id
            return detections

        # Match existing objects to input centroids using Euclidean distance
        object_ids = list(self.objects.keys())
        object_centroids = list(self.objects.values())

        # Compute distance matrix
        D = np.zeros((len(object_ids), len(input_centroids)), dtype=np.float32)
        for i, obj_pt in enumerate(object_centroids):
            for j, in_pt in enumerate(input_centroids):
                # Prefer matching same class
                class_penalty = 0 if self.classes.get(object_ids[i]) == input_classes[j] else 100.0
                dist = np.hypot(obj_pt[0] - in_pt[0], obj_pt[1] - in_pt[1]) + class_penalty
                D[i, j] = dist

        rows = D.min(axis=1).argsort()
        cols = D.argmin(axis=1)[rows]

        used_rows = set()
        used_cols = set()

        for (row, col) in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if D[row, col] > self.max_distance + 100.0:  # exceeded max allowable jump
                continue

            obj_id = object_ids[row]
            self.objects[obj_id] = input_centroids[col]
            self.disappeared[obj_id] = 0
            self.classes[obj_id] = input_classes[col]
            detections[col]["track_id"] = obj_id

            used_rows.add(row)
            used_cols.add(col)

        # Handle unmatched existing objects
        unused_rows = set(range(0, D.shape[0])).difference(used_rows)
        for row in unused_rows:
            obj_id = object_ids[row]
            self.disappeared[obj_id] += 1
            if self.disappeared[obj_id] > self.max_disappeared:
                self.deregister(obj_id)

        # Handle newly appeared objects
        unused_cols = set(range(0, D.shape[1])).difference(used_cols)
        for col in unused_cols:
            obj_id = self.register(input_centroids[col], input_classes[col])
            detections[col]["track_id"] = obj_id

        return detections


class ObjectTrack:
    """
    Maintains trajectory, signed rim distances, and state transitions for a track ID.
    """
    def __init__(self, track_id, class_name, initial_centroid, initial_dist):
        self.track_id = track_id
        self.class_name = class_name
        self.centroids = collections.deque(maxlen=20)
        self.distances = collections.deque(maxlen=20)
        self.confidences = collections.deque(maxlen=10)

        self.centroids.append(initial_centroid)
        self.distances.append(initial_dist)
        self.last_seen = time.time()
        self.frames_seen = 1

        # Determine starting state:
        # If object first appeared clearly inside cart (dist > 15px), it was already in cart
        if initial_dist > 15.0:
            self.state = TrackState.IN_CART
            self.committed = True
        else:
            self.state = TrackState.OUTSIDE
            self.committed = False

    def update(self, centroid, dist, conf):
        self.centroids.append(centroid)
        self.distances.append(dist)
        self.confidences.append(conf)
        self.last_seen = time.time()
        self.frames_seen += 1

    @property
    def latest_conf(self):
        return self.confidences[-1] if self.confidences else 1.0


class CartTracker:
    """
    High-speed, robust state machine tracker for shopping cart ADD/REMOVE events.
    """
    def __init__(
        self,
        inventory,
        entry_dist_threshold=20.0,   # pixels inside polygon to confirm ADD
        exit_dist_threshold=-15.0,   # pixels outside polygon to confirm REMOVE
    ):
        self.inventory = inventory
        self.entry_dist_threshold = entry_dist_threshold
        self.exit_dist_threshold = exit_dist_threshold

        self.centroid_tracker = SimpleCentroidTracker(max_disappeared=10, max_distance=150)
        self.tracks = {}  # track_id -> ObjectTrack
        self.last_event_banner = None
        self.last_event_time = 0.0

    def process_frame(self, raw_detections, polygon_zone, frame_width, frame_height):
        """
        raw_detections: list of dicts [{'name': str, 'conf': float, 'box': [x1,y1,x2,y2], 'centroid': (cx, cy)}]
        """
        # 1. Update lightweight centroid tracker (instantly assigns track_ids)
        tracked_detections = self.centroid_tracker.update(raw_detections)

        active_track_ids = set()

        for det in tracked_detections:
            track_id = det.get("track_id")
            if track_id is None:
                continue

            name = det["name"]
            conf = det["conf"]
            cx, cy = det["centroid"]
            active_track_ids.add(track_id)

            # Compute signed pixel distance to polygon boundary
            status, dist = polygon_zone.get_zone_status(cx, cy, frame_width, frame_height)
            det["zone_status"] = status
            det["zone_dist"] = dist

            if track_id not in self.tracks:
                self.tracks[track_id] = ObjectTrack(track_id, name, (cx, cy), dist)
            else:
                self.tracks[track_id].update((cx, cy), dist, conf)

            track = self.tracks[track_id]

            # --- State Machine Transitions ---
            # 1. OUTSIDE -> ENTERING
            if track.state == TrackState.OUTSIDE:
                if dist > -10.0:  # crossed near the rim
                    track.state = TrackState.ENTERING

            # 2. ENTERING -> IN_CART (🔥 Trigger ADD)
            if track.state == TrackState.ENTERING:
                # Check if moving deeper into the cart basket
                if dist >= self.entry_dist_threshold:
                    track.state = TrackState.IN_CART
                    track.committed = True
                    # 1-Shot ADD Event
                    self.inventory.add_item(track.class_name, track.track_id, track.latest_conf)
                    self.last_event_banner = f"+ ADDED 1x {track.class_name.upper()}"
                    self.last_event_time = time.time()
                elif dist < self.exit_dist_threshold:
                    # Aborted entry
                    track.state = TrackState.OUTSIDE

            # 3. IN_CART -> EXITING
            elif track.state == TrackState.IN_CART:
                if dist < 0:
                    track.state = TrackState.EXITING

            # 4. EXITING -> REMOVED (🔥 Trigger REMOVE)
            elif track.state == TrackState.EXITING:
                if dist <= self.exit_dist_threshold:
                    track.state = TrackState.REMOVED
                    # 1-Shot REMOVE Event
                    self.inventory.remove_item(track.class_name, track.track_id, track.latest_conf)
                    self.last_event_banner = f"- REMOVED 1x {track.class_name.upper()}"
                    self.last_event_time = time.time()
                elif dist >= self.entry_dist_threshold:
                    # Dropped back in
                    track.state = TrackState.IN_CART

        # Clean stale tracks
        now = time.time()
        for tid in list(self.tracks.keys()):
            if tid not in active_track_ids and (now - self.tracks[tid].last_seen > 5.0):
                if self.tracks[tid].state in [TrackState.OUTSIDE, TrackState.REMOVED]:
                    del self.tracks[tid]

        return tracked_detections

    def draw_hud(self, frame, tracked_detections, polygon_zone):
        """Draws bounding boxes, inside/outside badges, trails, and fading event banners."""
        h, w = frame.shape[:2]

        for det in tracked_detections:
            track_id = det.get("track_id", 0)
            name = det["name"]
            conf = det["conf"]
            x1, y1, x2, y2 = det["box"]
            cx, cy = det["centroid"]
            status = det.get("zone_status", "OUTSIDE")

            # Status Colors
            if status == "INSIDE":
                tag_color = (0, 255, 0)      # Bright Green
            elif status == "OUTSIDE":
                tag_color = (0, 0, 255)      # Red
            else:
                tag_color = (0, 255, 255)    # Yellow border

            # Draw Box & Centroid
            cv2.rectangle(frame, (x1, y1), (x2, y2), tag_color, 2)
            cv2.circle(frame, (cx, cy), 5, tag_color, -1)
            cv2.circle(frame, (cx, cy), 7, (255, 255, 255), 2)

            # Draw prominent badge above box
            track_state = self.tracks[track_id].state if track_id in self.tracks else status
            badge_text = f"#{track_id} {name.upper()} [{track_state}]"
            
            # Badge background pill
            text_size = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            bw = text_size[0] + 16
            bh = text_size[1] + 12
            bx1 = max(0, x1)
            by1 = max(0, y1 - bh - 4)

            cv2.rectangle(frame, (bx1, by1), (bx1 + bw, by1 + bh), tag_color, -1)
            text_color = (0, 0, 0) if status == "INSIDE" or track_state == TrackState.ENTERING else (255, 255, 255)
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

            # Draw Motion Trail
            if track_id in self.tracks:
                pts = list(self.tracks[track_id].centroids)
                for i in range(1, len(pts)):
                    cv2.line(frame, pts[i - 1], pts[i], tag_color, 2)

        # Top-Right: Cart Inventory HUD Card
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

        # Top-Left: Event Banner with 2.5s Auto-Fade Timer
        if self.last_event_banner and (time.time() - self.last_event_time < 2.5):
            banner_color = (0, 180, 0) if "+ ADDED" in self.last_event_banner else (0, 80, 255)
            cv2.rectangle(frame, (15, 15), (340, 55), banner_color, -1)
            cv2.putText(frame, self.last_event_banner, (25, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        return frame
