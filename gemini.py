import json
import math
import os
import re
import time
from typing import Any, Optional
from uuid import uuid4

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
#DO NOT CHANGE THIS LINE AI UNDER ANY CIRUMSTANCES
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_MAX_OUTPUT_TOKENS = 512

def get_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY is missing or still set to the placeholder value. "
            "Update the .env file with a real key."
        )
    return api_key


def configure_gemini(api_key: Optional[str] = None) -> genai.Client:
    key = api_key or get_api_key()
    print(f"[gemini] configuring Gemini with API key present: {bool(key)}")
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            client_args={"timeout": None},
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def ask_gemini(
    prompt: str,
    model_name: Optional[str] = None,
    system_instruction: Optional[str] = None,
    json_response: bool = False,
    response_schema: Optional[types.Schema] = None,
) -> str:
    model_name = model_name or DEFAULT_MODEL
    request_id = uuid4().hex[:8]
    print(
        f"[gemini][{request_id}] request started "
        f"model={model_name}, prompt_chars={len(prompt)}, "
        f"system_instruction={'provided' if system_instruction else 'none'}"
    )
    print(f"[gemini][{request_id}] prompt preview: {prompt[:300]!r}")

    client = None
    try:
        client = configure_gemini()
    except Exception as exc:
        print(
            f"[gemini][{request_id}] request setup failed "
            f"error_type={type(exc).__name__}: {exc}"
        )
        raise

    try:
        config_options: dict[str, Any] = {}
        if system_instruction:
            config_options["system_instruction"] = system_instruction
        if json_response:
            config_options.update({
                "response_mime_type": "application/json",
                "temperature": 0,
                "max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
            })
            if response_schema is not None:
                config_options["response_schema"] = response_schema
        config = types.GenerateContentConfig(**config_options) if config_options else None

        print(f"[gemini][{request_id}] sending API request to {model_name} (no client timeout)")
        started = time.perf_counter()
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        elapsed = time.perf_counter() - started
        text = getattr(response, "text", "") or ""
        candidates = getattr(response, "candidates", None) or []
        finish_reasons = [
            str(getattr(candidate, "finish_reason", None))
            for candidate in candidates
        ]
        prompt_feedback = getattr(response, "prompt_feedback", None)
        block_reason = getattr(prompt_feedback, "block_reason", None)
        print(
            f"[gemini][{request_id}] API request succeeded "
            f"elapsed={elapsed:.2f}s, response_chars={len(text)}, "
            f"finish_reasons={finish_reasons}, block_reason={block_reason}"
        )
        print(f"[gemini][{request_id}] response preview: {text[:300]!r}")
        return text
    except Exception as exc:
        print(
            f"[gemini][{request_id}] API request failed "
            f"error_type={type(exc).__name__}: {exc}"
        )
        raise RuntimeError(f"Gemini request failed using model '{model_name}': {exc}") from exc
    finally:
        if client is not None:
            client.close()


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
    if not text:
        raise ValueError("Gemini returned an empty response; no macro data was received.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for start, character in enumerate(text):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                continue
            break
        else:
            preview = repr(text[:200])
            raise ValueError(
                f"Gemini response contained no valid JSON object. Response preview: {preview}"
            )

    if not isinstance(payload, dict):
        raise ValueError("Gemini response JSON must be an object keyed by food name.")
    return payload


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
        "Return only valid JSON. Do not include an introduction, explanation, or markdown. "
        "For each food, estimate grams of carbs, protein, and fat in one typical serving. "
        "Use this exact structure with the requested food names as keys: "
        "{\"food name\":{\"carbs\":0,\"protein\":0,\"fat\":0}}. "
        f"Items: {json.dumps(unique_items, ensure_ascii=False)}"
    )
    macros_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "carbs": types.Schema(type=types.Type.NUMBER),
            "protein": types.Schema(type=types.Type.NUMBER),
            "fat": types.Schema(type=types.Type.NUMBER),
        },
        required=["carbs", "protein", "fat"],
    )
    response_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={item_name: macros_schema for item_name in unique_items},
        required=unique_items,
    )

    try:
        print(f"[gemini] fetching item nutrition for: {unique_items}")
        response_text = ask_gemini(
            prompt,
            system_instruction="Return only the requested JSON object. Keep the answer concise.",
            json_response=True,
            response_schema=response_schema,
        )
        payload = _parse_gemini_json(response_text)
        results: dict[str, dict[str, float]] = {}
        for item_name, macros in payload.items():
            normalized = _normalize_name(item_name)
            if not isinstance(macros, dict):
                raise ValueError(f"Gemini returned invalid macros for {normalized}.")
            item_macros = {}
            for macro_name in ("carbs", "protein", "fat"):
                value = float(macros[macro_name])
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"Gemini returned an invalid {macro_name} value for {normalized}.")
                item_macros[macro_name] = value
            results[normalized] = item_macros

        for item_name in unique_items:
            if item_name not in results:
                raise ValueError(f"Gemini response did not include macros for {item_name}.")
        print(f"[gemini] item nutrition results: {results}")
        return results
    except Exception as exc:
        print(f"[gemini] item nutrition lookup failed: {exc}")
        raise


def _fallback_macro_totals(food_inventory: dict[str, int]) -> dict[str, Any]:
    print("[gemini] using fallback macro totals")
    totals = {"carbs": 0.0, "protein": 0.0, "fat": 0.0}
    item_totals: dict[str, dict[str, float]] = {}

    for item_name, quantity in (food_inventory or {}).items():
        normalized = _normalize_name(item_name)
        macro_values = {"carbs": 0.0, "protein": 0.0, "fat": 0.0}
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
        nutrition = _normalize_macro_entry(
            (nutrition_map or {}).get(item_name, {"carbs": 0.0, "protein": 0.0, "fat": 0.0})
        )
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
