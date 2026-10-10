import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Optional, Union


class Brain:
    """Local storage for foods, budget, and cached macro data for each item."""

    # FDA major food allergens: https://www.fda.gov/food/food-labeling-nutrition/food-allergies
    DIETARY_RESTRICTIONS = (
        {"id": "milk", "label": "Milk"},
        {"id": "eggs", "label": "Eggs"},
        {"id": "fish", "label": "Fish"},
        {"id": "crustacean_shellfish", "label": "Crustacean shellfish"},
        {"id": "tree_nuts", "label": "Tree nuts"},
        {"id": "peanuts", "label": "Peanuts"},
        {"id": "gluten", "label": "Gluten"},
        {"id": "soybeans", "label": "Soybeans"},
        {"id": "sesame", "label": "Sesame"},
    )

    LEGACY_SEEDED_NUTRITION = {
        "apples": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
        "bananas": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
        "water bottle": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
    }

    def __init__(self, file_path: Union[str, Path] = "brain.json"):
        self._lock = threading.RLock()
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.file_path.exists():
            self.file_path.write_text(
                json.dumps(
                    {
                        "foods": {},
                        "budget": 0,
                        "dietary_restrictions": [],
                        "other_dietary_restrictions": [],
                        "nutrition": {},
                        "last_ai_run": 0,
                        "pending_items": [],
                        "nutrition_migration_version": 0,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

        self.data = self._load()
        self._migrate_legacy_nutrition()
        self.data["pending_items"] = []
        for item_name, quantity in self.data["foods"].items():
            if quantity > 0:
                self._queue_missing_nutrition(item_name)
        self.save()

    def _load(self) -> dict[str, Any]:
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {
                "foods": {},
                "budget": 0,
                "dietary_restrictions": [],
                "other_dietary_restrictions": [],
                "nutrition": {},
                "last_ai_run": 0,
                "pending_items": [],
                "nutrition_migration_version": 0,
            }

        if not isinstance(loaded, dict):
            return {
                "foods": {},
                "budget": 0,
                "dietary_restrictions": [],
                "other_dietary_restrictions": [],
                "nutrition": {},
                "last_ai_run": 0,
                "pending_items": [],
                "nutrition_migration_version": 0,
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
            "dietary_restrictions": self._normalize_dietary_restrictions(
                loaded.get("dietary_restrictions", [])
            ),
            "other_dietary_restrictions": self._normalize_other_dietary_restrictions(
                loaded.get("other_dietary_restrictions", [])
            ),
            "last_ai_run": float(loaded.get("last_ai_run", 0)),
            "pending_items": [self._normalize_name(item) for item in pending_items if str(item).strip()],
            "nutrition_migration_version": int(loaded.get("nutrition_migration_version", 0)),
        }

    def _migrate_legacy_nutrition(self) -> None:
        if self.data.get("nutrition_migration_version", 0) >= 2:
            return

        nutrition = self.data.setdefault("nutrition", {})
        for item_name, macros in self.LEGACY_SEEDED_NUTRITION.items():
            normalized = self._normalize_name(item_name)
            if normalized not in {"water", "water bottle", "water bottles"} and nutrition.get(normalized) == macros:
                del nutrition[normalized]

        for item_name in self.data.get("pending_items", []):
            macros = nutrition.get(item_name)
            if macros and all(float(macros.get(key, 0.0) or 0.0) == 0.0 for key in ("carbs", "protein", "fat")):
                del nutrition[item_name]

        for item_name, macros in list(nutrition.items()):
            is_water = item_name in {"water", "water bottle", "water bottles"}
            is_empty = all(float(macros.get(key, 0.0) or 0.0) == 0.0 for key in ("carbs", "protein", "fat"))
            if is_empty and not is_water:
                del nutrition[item_name]

        self.data["nutrition_migration_version"] = 2

    def save(self) -> None:
        with self._lock:
            with self.file_path.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    def set_items(self, foods: dict[str, int]) -> dict[str, int]:
        with self._lock:
            self.data["foods"] = {
                self._normalize_name(name): max(int(quantity), 0)
                for name, quantity in (foods or {}).items()
            }
            self.data["pending_items"] = [
                item
                for item in self.data.get("pending_items", [])
                if self.data["foods"].get(item, 0) > 0 and item not in self.data.get("nutrition", {})
            ]
            for item_name, quantity in self.data["foods"].items():
                if quantity > 0:
                    self._queue_missing_nutrition(item_name)
                else:
                    self._remove_pending_item(item_name)
            self.save()
            return self.get_store()

    def set_item(self, item_name: str, quantity: int) -> dict[str, int]:
        with self._lock:
            name = self._normalize_name(item_name)
            if not name:
                raise ValueError("Item name cannot be empty.")

            self.data["foods"][name] = max(int(quantity), 0)
            self._queue_missing_nutrition(name)
            self.save()
            return self.get_store()

    def add_item(self, item_name: str, quantity: int = 1) -> dict[str, int]:
        with self._lock:
            name = self._normalize_name(item_name)
            if not name:
                raise ValueError("Item name cannot be empty.")

            current = int(self.data["foods"].get(name, 0))
            self.data["foods"][name] = max(current + int(quantity), 0)
            self._queue_missing_nutrition(name)
            self.save()
            return self.get_store()

    def update_item_count(self, item_name: str, change: int) -> dict[str, int]:
        with self._lock:
            name = self._normalize_name(item_name)
            if not name:
                raise ValueError("Item name cannot be empty.")

            current = int(self.data["foods"].get(name, 0))
            self.data["foods"][name] = max(current + int(change), 0)
            self._queue_missing_nutrition(name)
            self.save()
            return self.get_store()

    def remove_item(self, item_name: str) -> dict[str, int]:
        with self._lock:
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

        quantity = self.data.get("foods", {}).get(name, 0)
        if quantity < 1 or name in self.data.get("nutrition", {}):
            self._remove_pending_item(name)
            return
        pending = self.data.setdefault("pending_items", [])
        if name not in pending:
            pending.append(name)

    def _remove_pending_item(self, item_name: str) -> None:
        name = self._normalize_name(item_name)
        pending = self.data.setdefault("pending_items", [])
        self.data["pending_items"] = [item for item in pending if item != name]

    def get_pending_items(self) -> list[str]:
        with self._lock:
            return list(self.data.get("pending_items", []))

    def consume_pending_items(self) -> list[str]:
        with self._lock:
            pending = self.get_pending_items()
            self.data["pending_items"] = []
            self.save()
            return pending

    def set_last_ai_run(self, timestamp: Optional[float] = None) -> float:
        with self._lock:
            self.data["last_ai_run"] = float(timestamp if timestamp is not None else time.time())
            self.save()
            return self.data["last_ai_run"]

    def get_last_ai_run(self) -> float:
        with self._lock:
            return float(self.data.get("last_ai_run", 0))

    def get_nutrition_store(self) -> dict[str, dict[str, float]]:
        with self._lock:
            return {
                item_name: {
                    "carbs": float(macros.get("carbs", 0.0) or 0.0),
                    "protein": float(macros.get("protein", 0.0) or 0.0),
                    "fat": float(macros.get("fat", 0.0) or 0.0),
                }
                for item_name, macros in self.data.get("nutrition", {}).items()
            }

    def set_item_nutrition(self, item_name: str, macros: dict[str, float]) -> dict[str, float]:
        with self._lock:
            name = self._normalize_name(item_name)
            self.data.setdefault("nutrition", {})
            self.data["nutrition"][name] = {
                "carbs": float(macros.get("carbs", 0.0) or 0.0),
                "protein": float(macros.get("protein", 0.0) or 0.0),
                "fat": float(macros.get("fat", 0.0) or 0.0),
            }
            self._remove_pending_item(name)
            self.save()
            return self.data["nutrition"][name]

    def apply_ai_nutrition(self, updates: dict[str, dict[str, float]]) -> None:
        with self._lock:
            for item_name, macros in (updates or {}).items():
                if not item_name:
                    continue
                normalized = self._normalize_name(item_name)
                if self.data.get("foods", {}).get(normalized, 0) < 1:
                    continue
                self.set_item_nutrition(item_name, macros)

    def get_macro_totals(self) -> dict[str, Any]:
        with self._lock:
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
        with self._lock:
            return dict(self.data.get("foods", {}))

    @classmethod
    def get_available_dietary_restrictions(cls) -> list[dict[str, str]]:
        return [dict(restriction) for restriction in cls.DIETARY_RESTRICTIONS]

    @classmethod
    def _normalize_dietary_restrictions(cls, restrictions: Any) -> list[str]:
        if not isinstance(restrictions, list):
            return []
        allowed_ids = {restriction["id"] for restriction in cls.DIETARY_RESTRICTIONS}
        normalized = ("gluten" if restriction == "wheat" else restriction for restriction in restrictions)
        return list(dict.fromkeys(
            restriction for restriction in normalized
            if isinstance(restriction, str) and restriction in allowed_ids
        ))

    @staticmethod
    def _normalize_other_dietary_restrictions(restrictions: Any) -> list[str]:
        if not isinstance(restrictions, list):
            return []
        normalized = []
        seen = set()
        for restriction in restrictions:
            if not isinstance(restriction, str):
                continue
            label = re.sub(r"\s+", " ", restriction.strip())
            key = label.casefold()
            if label and key not in seen and len(label) <= 80:
                seen.add(key)
                normalized.append(label)
        return normalized

    def get_dietary_restrictions(self) -> list[str]:
        with self._lock:
            return list(self.data.get("dietary_restrictions", []))

    def get_other_dietary_restrictions(self) -> list[str]:
        with self._lock:
            return list(self.data.get("other_dietary_restrictions", []))

    def set_dietary_restrictions(self, restrictions: list[str]) -> list[str]:
        self.set_dietary_preferences(
            restrictions,
            self.get_other_dietary_restrictions(),
        )
        return self.get_dietary_restrictions()

    def set_dietary_preferences(
        self,
        restrictions: list[str],
        other_restrictions: list[str],
    ) -> dict[str, list[str]]:
        with self._lock:
            if not isinstance(restrictions, list) or any(
                not isinstance(restriction, str) for restriction in restrictions
            ):
                raise ValueError("Dietary restrictions must be a list of restriction IDs.")

            allowed_ids = {restriction["id"] for restriction in self.DIETARY_RESTRICTIONS}
            unknown_ids = set(restrictions) - allowed_ids
            if unknown_ids:
                raise ValueError(
                    f"Unsupported dietary restriction IDs: {', '.join(sorted(unknown_ids))}"
                )

            if not isinstance(other_restrictions, list) or any(
                not isinstance(restriction, str) for restriction in other_restrictions
            ):
                raise ValueError("Other dietary restrictions must be a list of names.")

            if any(len(re.sub(r"\s+", " ", restriction.strip())) > 80 for restriction in other_restrictions):
                raise ValueError("Other dietary restriction names must be 80 characters or fewer.")

            selected_ids = set(restrictions)
            self.data["dietary_restrictions"] = [
                restriction["id"] for restriction in self.DIETARY_RESTRICTIONS
                if restriction["id"] in selected_ids
            ]
            self.data["other_dietary_restrictions"] = self._normalize_other_dietary_restrictions(
                other_restrictions
            )
            self.save()
            return {
                "dietary_restrictions": self.get_dietary_restrictions(),
                "other_dietary_restrictions": self.get_other_dietary_restrictions(),
            }

    def get_budget(self) -> float:
        with self._lock:
            return float(self.data.get("budget", 0))

    def set_budget(self, amount: float) -> float:
        with self._lock:
            self.data["budget"] = float(amount)
            self.save()
            return self.get_budget()

    def update_budget(self, change: float) -> float:
        with self._lock:
            self.data["budget"] = self.get_budget() + float(change)
            self.save()
            return self.get_budget()

    def get_all(self) -> dict[str, Any]:
        with self._lock:
            return {
                "foods": self.get_store(),
                "budget": self.get_budget(),
                "dietary_restrictions": self.get_dietary_restrictions(),
                "other_dietary_restrictions": self.get_other_dietary_restrictions(),
                "available_dietary_restrictions": self.get_available_dietary_restrictions(),
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
