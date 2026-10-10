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

class ObjectTrack:
    """
    Maintains the trajectory history, signed rim distances, and state lifecycle of a single tracked object.
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

        # Initial state based on where object first appeared
        if initial_dist > 20:
            # Appeared deep inside cart (e.g. was already in basket when starting or occluded item reappeared)
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
    Manages tracklets, state machine transitions, and dispatches 1-shot ADD/REMOVE signals.
    """
    def __init__(
        self,
        inventory,
        entry_dist_threshold=25.0,   # pixels deep inside polygon to confirm ADD
        exit_dist_threshold=-20.0,   # pixels outside polygon to confirm REMOVE
        min_frames_to_commit=2,     # consecutive frames inside required
    ):
        self.inventory = inventory
        self.entry_dist_threshold = entry_dist_threshold
        self.exit_dist_threshold = exit_dist_threshold
        self.min_frames_to_commit = min_frames_to_commit

        self.tracks = {}  # track_id -> ObjectTrack
        self.recent_events = collections.deque(maxlen=4)

    def process_frame_tracks(self, detections, polygon_zone, frame_width, frame_height):
        """
        detections: list of dicts: [{'track_id': id, 'name': str, 'conf': float, 'box': [x1, y1, x2, y2], 'centroid': (cx, cy)}]
        polygon_zone: CartPolygonZone instance
        """
        active_track_ids = set()

        for det in detections:
            track_id = det["track_id"]
            name = det["name"]
            conf = det["conf"]
            cx, cy = det["centroid"]
            active_track_ids.add(track_id)

            # Compute signed pixel distance to polygon boundary:
            # > 0 inside, < 0 outside
            status, dist = polygon_zone.get_zone_status(cx, cy, frame_width, frame_height)

            if track_id not in self.tracks:
                self.tracks[track_id] = ObjectTrack(track_id, name, (cx, cy), dist)
            else:
                self.tracks[track_id].update((cx, cy), dist, conf)

            track = self.tracks[track_id]

            # --- State Machine Transitions ---
            # 1. OUTSIDE -> ENTERING
            if track.state == TrackState.OUTSIDE:
                if dist > -15.0:  # Reached entry boundary
                    track.state = TrackState.ENTERING

            # 2. ENTERING -> IN_CART (1-Shot ADD Trigger)
            if track.state == TrackState.ENTERING:
                # Check if moving deeper into the cart basket
                recent_dists = list(track.distances)[-self.min_frames_to_commit:]
                is_deep = dist >= self.entry_dist_threshold
                is_consistently_inside = all(d > 0 for d in recent_dists)

                if is_deep or (is_consistently_inside and len(recent_dists) >= self.min_frames_to_commit):
                    track.state = TrackState.IN_CART
                    track.committed = True
                    # 🔥 DISPATCH 1-SHOT ADD EVENT
                    event = self.inventory.add_item(track.class_name, track.track_id, track.latest_conf)
                    self.recent_events.append(f"+ ADDED {track.class_name.upper()}")

                elif dist < self.exit_dist_threshold:
                    # Aborted entry: pulled back before fully entering
                    track.state = TrackState.OUTSIDE

            # 3. IN_CART -> EXITING / REMOVED (1-Shot REMOVE Trigger)
            elif track.state == TrackState.IN_CART:
                if dist < 0:
                    track.state = TrackState.EXITING

            elif track.state == TrackState.EXITING:
                if dist <= self.exit_dist_threshold:
                    track.state = TrackState.REMOVED
                    # 🔥 DISPATCH 1-SHOT REMOVE EVENT
                    event = self.inventory.remove_item(track.class_name, track.track_id, track.latest_conf)
                    self.recent_events.append(f"- REMOVED {track.class_name.upper()}")

                elif dist >= self.entry_dist_threshold:
                    # Put back down inside cart
                    track.state = TrackState.IN_CART

        # Clean up old tracks that have not been seen for > 10 seconds
        now = time.time()
        stale_ids = [
            tid for tid, trk in self.tracks.items()
            if (now - trk.last_seen > 10.0 and trk.state in [TrackState.OUTSIDE, TrackState.REMOVED])
        ]
        for tid in stale_ids:
            del self.tracks[tid]

    def draw_tracks_and_hud(self, frame, detections, polygon_zone):
        """Draws trajectory trails, motion vectors, active track states, and live cart inventory HUD."""
        h, w = frame.shape[:2]

        # 1. Draw Trajectory Trails for moving objects
        for det in detections:
            track_id = det["track_id"]
            if track_id in self.tracks:
                track = self.tracks[track_id]
                pts = list(track.centroids)
                for i in range(1, len(pts)):
                    # Green trail for entering/inside, Orange/Red for exiting
                    trail_color = (0, 255, 120) if track.state in [TrackState.ENTERING, TrackState.IN_CART] else (0, 100, 255)
                    thickness = int(np.sqrt(16 / float(len(pts) - i + 1)) * 1.5)
                    cv2.line(frame, pts[i - 1], pts[i], trail_color, max(1, thickness))

                # Draw track state badge next to object
                cx, cy = track.centroids[-1]
                state_colors = {
                    TrackState.OUTSIDE: (0, 0, 255),
                    TrackState.ENTERING: (0, 255, 255),
                    TrackState.IN_CART: (0, 255, 0),
                    TrackState.EXITING: (0, 140, 255),
                    TrackState.REMOVED: (128, 128, 128),
                }
                color = state_colors.get(track.state, (255, 255, 255))
                badge_text = f"#{track_id} {track.class_name} [{track.state}]"
                cv2.putText(
                    frame,
                    badge_text,
                    (cx - 40, max(20, cy - 15)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    color,
                    2,
                    cv2.LINE_AA,
                )

        # 2. Top-Right: Live Cart Inventory Tally Box
        tally = self.inventory.tally
        box_w = 260
        box_h = 135
        bx1 = w - box_w - 15
        by1 = 15

        # Background card
        cv2.rectangle(frame, (bx1, by1), (bx1 + box_w, by1 + box_h), (20, 20, 20), -1)
        cv2.rectangle(frame, (bx1, by1), (bx1 + box_w, by1 + box_h), (0, 255, 200), 2)
        cv2.putText(frame, "CART INVENTORY", (bx1 + 15, by1 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2, cv2.LINE_AA)

        # Items
        cv2.putText(frame, f"Apples:       {tally.get('apple', 0)}", (bx1 + 15, by1 + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"Bananas:      {tally.get('banana', 0)}", (bx1 + 15, by1 + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"Water Bottles:{tally.get('bottle', 0)}", (bx1 + 15, by1 + 105), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        # 3. Top-Left: Recent Event Ticker
        if self.recent_events:
            last_ev = self.recent_events[-1]
            banner_color = (0, 180, 0) if "+ ADDED" in last_ev else (0, 80, 255)
            cv2.rectangle(frame, (15, 15), (320, 55), banner_color, -1)
            cv2.putText(frame, last_ev, (25, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        return frame
