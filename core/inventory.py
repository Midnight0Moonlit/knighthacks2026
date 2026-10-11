import json
import os
from datetime import datetime
from pathlib import Path

class CartInventory:
    """
    Manages the in-memory cart inventory tally and dispatches ADD / REMOVE events.
    """
    def __init__(self, camera_inventory_path=None):
        # Target classes
        self.tally = {
            "apple": 0,
            "banana": 0,
            "bottle": 0,
        }
        self.event_history = []
        self.camera_inventory_path = Path(camera_inventory_path or Path(__file__).resolve().parents[1] / "public" / "mock_camera_inventory.json")
        self._save_camera_inventory()

    def add_item(self, item_name, track_id, conf=1.0):
        """Registers a 1-shot ADD event into the cart."""
        item_name = item_name.lower()
        if item_name in self.tally:
            self.tally[item_name] += 1
        else:
            self.tally[item_name] = 1

        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        event_record = {
            "time": now,
            "event": "ADD",
            "item": item_name,
            "track_id": track_id,
            "confidence": round(conf, 2),
            "cart_snapshot": dict(self.tally),
        }
        self.event_history.append(event_record)

        self._save_camera_inventory()
        self._log_event(event_record)
        return event_record

    def remove_item(self, item_name, track_id, conf=1.0):
        """Registers a 1-shot REMOVE event from the cart."""
        item_name = item_name.lower()
        if item_name in self.tally:
            self.tally[item_name] = max(0, self.tally[item_name] - 1)
        else:
            self.tally[item_name] = 0

        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        event_record = {
            "time": now,
            "event": "REMOVE",
            "item": item_name,
            "track_id": track_id,
            "confidence": round(conf, 2),
            "cart_snapshot": dict(self.tally),
        }
        self.event_history.append(event_record)

        self._save_camera_inventory()
        self._log_event(event_record)
        return event_record

    def _save_camera_inventory(self):
        """Publish the vision tally for the dashboard to consume."""
        self.camera_inventory_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.camera_inventory_path.with_suffix(".json.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(self.tally, file, indent=2)
            file.write("\n")
        os.replace(temporary_path, self.camera_inventory_path)

    def _log_event(self, record):
        """Prints a clean, formatted audit log to the terminal console."""
        symbol = "[+] ADDED" if record["event"] == "ADD" else "[-] REMOVED"
        print("\n" + "=" * 62)
        print(f"[{record['time']}] [CART EVENT]  {symbol}: 1x {record['item'].upper()} (Track #{record['track_id']})")
        print(f"                 Current Cart: {self.tally}")
        print("=" * 62 + "\n")
