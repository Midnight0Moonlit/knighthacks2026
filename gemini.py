import json
import os
import re
import time
from typing import Any, Optional

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

FALLBACK_MACRO_VALUES = {
    "apple": {"carbs": 25.0, "protein": 0.5, "fat": 0.3},
    "apples": {"carbs": 25.0, "protein": 0.5, "fat": 0.3},
    "banana": {"carbs": 27.0, "protein": 1.3, "fat": 0.3},
    "bananas": {"carbs": 27.0, "protein": 1.3, "fat": 0.3},
    "water bottle": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
    "water bottles": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
    "water": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
}


def get_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY is missing or still set to the placeholder value. "
            "Update the .env file with a real key."
        )
    return api_key


def configure_gemini(api_key: Optional[str] = None) -> str:
    key = api_key or get_api_key()
    print(f"[gemini] configuring Gemini with API key present: {bool(key)}")
    genai.configure(api_key=key)
    return key


def ask_gemini(
    prompt: str,
    model_name: Optional[str] = None,
    system_instruction: Optional[str] = None,
) -> str:
    model_name = model_name or DEFAULT_MODEL
    print(f"[gemini] ask_gemini called with model={model_name}, prompt_len={len(prompt)}")
    configure_gemini()

    try:
        model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
        print(f"[gemini] sending request to {model_name}...")
        started = time.time()
        response = model.generate_content(prompt)
        print(f"[gemini] response received in {time.time() - started:.2f}s")
        text = getattr(response, "text", str(response))
        print(f"[gemini] response preview: {text[:200]!r}")
        return text
    except Exception as exc:
        print(f"[gemini] request failed: {exc}")
        raise RuntimeError(f"Gemini request failed using model '{model_name}': {exc}") from exc


def _normalize_name(item_name: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(item_name).strip().lower())
    return cleaned.replace("_", " ")


def _normalize_macro_entry(macros: Any) -> dict[str, float]:
    if not isinstance(macros, dict):
        return {"carbs": 0.0, "protein": 0.0, "fat": 0.0}
    return {
        "carbs": float(macros.get("carbs", 0.0) or 0.0),
        "protein": float(macros.get("protein", 0.0) or 0.0),
        "fat": float(macros.get("fat", 0.0) or 0.0),
    }


def _parse_gemini_json(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in Gemini response")

    return json.loads(match.group(0))


def get_item_macros_for_names(item_names: list[str]) -> dict[str, dict[str, float]]:
    unique_items = []
    seen = set()
    for item_name in item_names or []:
        normalized = _normalize_name(item_name)
        if normalized and normalized not in seen:
            unique_items.append(normalized)
            seen.add(normalized)

    if not unique_items:
        return {}

    prompt = (
        "Return valid JSON only. Use this shape: {\"food name\": {\"carbs\": number, \"protein\": number, \"fat\": number}}. "
        "Give values in grams per single item. "
        f"Items: {json.dumps(unique_items, ensure_ascii=False)}"
    )

    try:
        print(f"[gemini] fetching item nutrition for: {unique_items}")
        response_text = ask_gemini(prompt)
        payload = _parse_gemini_json(response_text)
        results: dict[str, dict[str, float]] = {}
        for item_name, macros in payload.items():
            normalized = _normalize_name(item_name)
            results[normalized] = _normalize_macro_entry(macros)

        for item_name in unique_items:
            if item_name not in results:
                results[item_name] = FALLBACK_MACRO_VALUES.get(
                    item_name,
                    {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
                )
        print(f"[gemini] item nutrition results: {results}")
        return results
    except Exception as exc:
        print(f"[gemini] item nutrition lookup failed: {exc}")
        fallback: dict[str, dict[str, float]] = {}
        for item_name in unique_items:
            fallback[item_name] = FALLBACK_MACRO_VALUES.get(
                item_name,
                {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
            )
        return fallback


def _fallback_macro_totals(food_inventory: dict[str, int]) -> dict[str, Any]:
    print("[gemini] using fallback macro totals")
    totals = {"carbs": 0.0, "protein": 0.0, "fat": 0.0}
    item_totals: dict[str, dict[str, float]] = {}

    for item_name, quantity in (food_inventory or {}).items():
        normalized = _normalize_name(item_name)
        macro_values = FALLBACK_MACRO_VALUES.get(normalized, {"carbs": 0.0, "protein": 0.0, "fat": 0.0})
        qty = max(int(quantity), 0)
        item_totals[normalized] = {
            "carbs": round(macro_values["carbs"] * qty, 2),
            "protein": round(macro_values["protein"] * qty, 2),
            "fat": round(macro_values["fat"] * qty, 2),
        }
        for key in totals:
            totals[key] += item_totals[normalized][key]

    result = {
        "totals": {k: round(v, 2) for k, v in totals.items()},
        "items": item_totals,
    }
    print(f"[gemini] fallback totals: {result}")
    return result


def get_macro_totals(food_inventory: dict[str, int], nutrition_map: Optional[dict[str, dict[str, float]]] = None) -> dict[str, Any]:
    normalized_inventory = {
        _normalize_name(name): max(int(quantity), 0)
        for name, quantity in (food_inventory or {}).items()
    }

    print(f"[gemini] normalized inventory for macro calc: {normalized_inventory}")
    if not normalized_inventory:
        print("[gemini] no items in inventory; returning zero totals")
        return {"totals": {"carbs": 0.0, "protein": 0.0, "fat": 0.0}, "items": {}}

    totals = {"carbs": 0.0, "protein": 0.0, "fat": 0.0}
    item_totals: dict[str, dict[str, float]] = {}

    for item_name, quantity in normalized_inventory.items():
        nutrition = _normalize_macro_entry((nutrition_map or {}).get(item_name, FALLBACK_MACRO_VALUES.get(item_name, {"carbs": 0.0, "protein": 0.0, "fat": 0.0})))
        item_totals[item_name] = {
            "carbs": round(float(nutrition["carbs"]) * quantity, 2),
            "protein": round(float(nutrition["protein"]) * quantity, 2),
            "fat": round(float(nutrition["fat"]) * quantity, 2),
        }
        totals["carbs"] += item_totals[item_name]["carbs"]
        totals["protein"] += item_totals[item_name]["protein"]
        totals["fat"] += item_totals[item_name]["fat"]

    result = {"totals": {k: round(v, 2) for k, v in totals.items()}, "items": item_totals}
    print(f"[gemini] local totals computed: {result}")
    return result


def quick_check() -> str:
    return ask_gemini("Reply with exactly: Gemini working")


if __name__ == "__main__":
    try:
        print(get_macro_totals({"apples": 2, "bananas": 2, "water bottle": 2}))
    except Exception as exc:
        print(f"Quick check failed: {exc}")
