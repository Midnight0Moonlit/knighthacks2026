from datetime import datetime

class CartInventory:
    """
    Manages the in-memory cart inventory tally and dispatches ADD / REMOVE events.
    """
    def __init__(self):
        # Target classes
        self.tally = {
            "apple": 0,
            "banana": 0,
            "bottle": 0,
        }
        self.event_history = []

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

        self._log_event(event_record)
        return event_record

    def _log_event(self, record):
        """Prints a clean, formatted audit log to the terminal console."""
        symbol = "[+] ADDED" if record["event"] == "ADD" else "[-] REMOVED"
        print("\n" + "=" * 62)
        print(f"[{record['time']}] [CART EVENT]  {symbol}: 1x {record['item'].upper()} (Track #{record['track_id']})")
        print(f"                 Current Cart: {self.tally}")
        print("=" * 62 + "\n")
