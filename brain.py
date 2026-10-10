import json
import re
import time
from pathlib import Path
from typing import Any


class Brain:
    """Local storage for foods, budget, and cached macro data for each item."""

    DEFAULT_NUTRITION = {
        "apples": {"carbs": 25.0, "protein": 0.5, "fat": 0.3},
        "bananas": {"carbs": 27.0, "protein": 1.3, "fat": 0.3},
        "water bottle": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
        "water": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
    }

    def __init__(self, file_path: str | Path = "brain.json"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.file_path.exists():
            self.file_path.write_text(
                json.dumps(
                    {
                        "foods": {},
                        "budget": 0,
                        "nutrition": self.DEFAULT_NUTRITION,
                        "last_ai_run": 0,
                        "pending_items": [],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

        self.data = self._load()
        self._seed_known_nutrition()
        self.save()

    def _load(self) -> dict[str, Any]:
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {
                "foods": {},
                "budget": 0,
                "nutrition": {},
                "last_ai_run": 0,
                "pending_items": [],
            }

        if not isinstance(loaded, dict):
            return {
                "foods": {},
                "budget": 0,
                "nutrition": {},
                "last_ai_run": 0,
                "pending_items": [],
            }

        foods = loaded.get("foods", {})
        if not isinstance(foods, dict):
            foods = {}

        nutrition = loaded.get("nutrition", {})
        if not isinstance(nutrition, dict):
            nutrition = {}

        normalized_nutrition: dict[str, dict[str, float]] = {}
        for item_name, macros in nutrition.items():
            if not isinstance(macros, dict):
                continue
            normalized_nutrition[self._normalize_name(item_name)] = {
                "carbs": float(macros.get("carbs", 0.0) or 0.0),
                "protein": float(macros.get("protein", 0.0) or 0.0),
                "fat": float(macros.get("fat", 0.0) or 0.0),
            }

        pending_items = loaded.get("pending_items", [])
        if not isinstance(pending_items, list):
            pending_items = []

        return {
            "foods": {self._normalize_name(k): max(int(v), 0) for k, v in foods.items()},
            "budget": float(loaded.get("budget", 0)),
            "nutrition": normalized_nutrition,
            "last_ai_run": float(loaded.get("last_ai_run", 0)),
            "pending_items": [self._normalize_name(item) for item in pending_items if str(item).strip()],
        }

    def _seed_known_nutrition(self) -> None:
        self.data.setdefault("nutrition", {})
        for item_name, macros in self.DEFAULT_NUTRITION.items():
            normalized = self._normalize_name(item_name)
            self.data["nutrition"].setdefault(
                normalized,
                {
                    "carbs": float(macros.get("carbs", 0.0) or 0.0),
                    "protein": float(macros.get("protein", 0.0) or 0.0),
                    "fat": float(macros.get("fat", 0.0) or 0.0),
                },
            )

    def save(self) -> None:
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def set_items(self, foods: dict[str, int]) -> dict[str, int]:
        self.data["foods"] = {
            self._normalize_name(name): max(int(quantity), 0)
            for name, quantity in (foods or {}).items()
        }
        self.save()
        return self.get_store()

    def set_item(self, item_name: str, quantity: int) -> dict[str, int]:
        name = self._normalize_name(item_name)
        if not name:
            raise ValueError("Item name cannot be empty.")

        self.data["foods"][name] = max(int(quantity), 0)
        self._queue_missing_nutrition(name)
        self.save()
        return self.get_store()

    def add_item(self, item_name: str, quantity: int = 1) -> dict[str, int]:
        name = self._normalize_name(item_name)
        if not name:
            raise ValueError("Item name cannot be empty.")

        current = int(self.data["foods"].get(name, 0))
        self.data["foods"][name] = max(current + int(quantity), 0)
        self._queue_missing_nutrition(name)
        self.save()
        return self.get_store()

    def update_item_count(self, item_name: str, change: int) -> dict[str, int]:
        name = self._normalize_name(item_name)
        if not name:
            raise ValueError("Item name cannot be empty.")

        current = int(self.data["foods"].get(name, 0))
        self.data["foods"][name] = max(current + int(change), 0)
        self._queue_missing_nutrition(name)
        self.save()
        return self.get_store()

    def remove_item(self, item_name: str) -> dict[str, int]:
        name = self._normalize_name(item_name)
        self.data["foods"].pop(name, None)
        self.data["nutrition"].pop(name, None)
        pending = self.data.get("pending_items", [])
        self.data["pending_items"] = [item for item in pending if item != name]
        self.save()
        return self.get_store()

    def _queue_missing_nutrition(self, item_name: str) -> None:
        name = self._normalize_name(item_name)
        if not name:
            return

        nutrition = self.data.setdefault("nutrition", {})
        if name not in nutrition:
            nutrition[name] = {"carbs": 0.0, "protein": 0.0, "fat": 0.0}

        pending = self.data.setdefault("pending_items", [])
        if name not in pending:
            pending.append(name)

    def get_pending_items(self) -> list[str]:
        return list(self.data.get("pending_items", []))

    def consume_pending_items(self) -> list[str]:
        pending = self.get_pending_items()
        self.data["pending_items"] = []
        self.save()
        return pending

    def set_last_ai_run(self, timestamp: float | None = None) -> float:
        self.data["last_ai_run"] = float(timestamp if timestamp is not None else time.time())
        self.save()
        return self.data["last_ai_run"]

    def get_last_ai_run(self) -> float:
        return float(self.data.get("last_ai_run", 0))

    def get_nutrition_store(self) -> dict[str, dict[str, float]]:
        return {
            item_name: {
                "carbs": float(macros.get("carbs", 0.0) or 0.0),
                "protein": float(macros.get("protein", 0.0) or 0.0),
                "fat": float(macros.get("fat", 0.0) or 0.0),
            }
            for item_name, macros in self.data.get("nutrition", {}).items()
        }

    def set_item_nutrition(self, item_name: str, macros: dict[str, float]) -> dict[str, float]:
        name = self._normalize_name(item_name)
        self.data.setdefault("nutrition", {})
        self.data["nutrition"][name] = {
            "carbs": float(macros.get("carbs", 0.0) or 0.0),
            "protein": float(macros.get("protein", 0.0) or 0.0),
            "fat": float(macros.get("fat", 0.0) or 0.0),
        }
        pending = self.data.get("pending_items", [])
        self.data["pending_items"] = [item for item in pending if item != name]
        self.save()
        return self.data["nutrition"][name]

    def apply_ai_nutrition(self, updates: dict[str, dict[str, float]]) -> None:
        for item_name, macros in (updates or {}).items():
            if not item_name:
                continue
            self.set_item_nutrition(item_name, macros)

    def get_macro_totals(self) -> dict[str, Any]:
        totals = {"carbs": 0.0, "protein": 0.0, "fat": 0.0}
        item_totals: dict[str, dict[str, float]] = {}

        for item_name, quantity in self.data.get("foods", {}).items():
            nutrition = self.data.get("nutrition", {}).get(item_name, {"carbs": 0.0, "protein": 0.0, "fat": 0.0})
            carbs = float(nutrition.get("carbs", 0.0) or 0.0)
            protein = float(nutrition.get("protein", 0.0) or 0.0)
            fat = float(nutrition.get("fat", 0.0) or 0.0)

            item_totals[item_name] = {
                "carbs": round(carbs * float(quantity), 2),
                "protein": round(protein * float(quantity), 2),
                "fat": round(fat * float(quantity), 2),
            }
            totals["carbs"] += item_totals[item_name]["carbs"]
            totals["protein"] += item_totals[item_name]["protein"]
            totals["fat"] += item_totals[item_name]["fat"]

        return {
            "totals": {key: round(value, 2) for key, value in totals.items()},
            "items": item_totals,
        }

    def get_store(self) -> dict[str, int]:
        return dict(self.data.get("foods", {}))

    def get_budget(self) -> float:
        return float(self.data.get("budget", 0))

    def set_budget(self, amount: float) -> float:
        self.data["budget"] = float(amount)
        self.save()
        return self.get_budget()

    def update_budget(self, change: float) -> float:
        self.data["budget"] = self.get_budget() + float(change)
        self.save()
        return self.get_budget()

    def get_all(self) -> dict[str, Any]:
        return {
            "foods": self.get_store(),
            "budget": self.get_budget(),
            "nutrition": self.get_nutrition_store(),
            "pending_items": self.get_pending_items(),
            "last_ai_run": self.get_last_ai_run(),
            "macro_totals": self.get_macro_totals(),
        }

    @staticmethod
    def _normalize_name(item_name: str) -> str:
        return re.sub(r"\s+", " ", str(item_name).strip().lower())


if __name__ == "__main__":
    brain = Brain("brain.json")
    brain.set_items({"apples": 2, "bananas": 2, "water bottle": 2})
    brain.update_item_count("apples", 1)
    brain.update_item_count("bananas", -1)
    brain.set_budget(50)
    brain.update_budget(10)
    print(brain.get_all())
