import json
from pathlib import Path
from typing import Any


class Brain:
    """Simple local storage for food inventory and a spending budget."""

    def __init__(self, file_path: str | Path = "brain.json"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.file_path.exists():
            self.file_path.write_text("{\n  \"foods\": {},\n  \"budget\": 0\n}\n", encoding="utf-8")

        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"foods": {}, "budget": 0}

        if not isinstance(loaded, dict):
            return {"foods": {}, "budget": 0}

        foods = loaded.get("foods", {})
        if not isinstance(foods, dict):
            foods = {}

        return {
            "foods": {str(k): int(v) for k, v in foods.items()},
            "budget": float(loaded.get("budget", 0)),
        }

    def save(self) -> None:
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_store(self) -> dict[str, int]:
        return dict(self.data.get("foods", {}))

    def get_budget(self) -> float:
        return float(self.data.get("budget", 0))

    def get_all(self) -> dict[str, Any]:
        return {
            "foods": self.get_store(),
            "budget": self.get_budget(),
        }

    def add_item(self, item_name: str, quantity: int = 1) -> dict[str, int]:
        name = self._normalize_name(item_name)
        if not name:
            raise ValueError("Item name cannot be empty.")

        current = int(self.data["foods"].get(name, 0))
        updated = max(current + int(quantity), 0)
        self.data["foods"][name] = updated
        self.save()
        return self.get_store()

    def update_item_count(self, item_name: str, change: int) -> dict[str, int]:
        name = self._normalize_name(item_name)
        if not name:
            raise ValueError("Item name cannot be empty.")

        current = int(self.data["foods"].get(name, 0))
        updated = max(current + int(change), 0)
        self.data["foods"][name] = updated
        self.save()
        return self.get_store()

    def set_budget(self, amount: float) -> float:
        self.data["budget"] = float(amount)
        self.save()
        return self.get_budget()

    def update_budget(self, change: float) -> float:
        self.data["budget"] = self.get_budget() + float(change)
        self.save()
        return self.get_budget()

    @staticmethod
    def _normalize_name(item_name: str) -> str:
        return str(item_name).strip().lower()


if __name__ == "__main__":
    brain = Brain("brain.json")
    brain.add_item("apples", 2)
    brain.add_item("bananas", 2)
    brain.add_item("water bottle", 2)
    brain.update_item_count("apples", 1)
    brain.update_item_count("bananas", -1)
    brain.set_budget(50)
    brain.update_budget(10)
    print(brain.get_all())
