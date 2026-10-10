import os
from typing import Optional

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


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
    genai.configure(api_key=key)
    return key


def ask_gemini(
    prompt: str,
    model_name: Optional[str] = None,
    system_instruction: Optional[str] = None,
) -> str:
    model_name = model_name or DEFAULT_MODEL
    configure_gemini()

    try:
        model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
        response = model.generate_content(prompt)
        return getattr(response, "text", str(response))
    except Exception as exc:
        raise RuntimeError(f"Gemini request failed using model '{model_name}': {exc}") from exc


def quick_check() -> str:
    return ask_gemini("Reply with exactly: Gemini working")


if __name__ == "__main__":
    try:
        print(quick_check())
    except Exception as exc:
        print(f"Quick check failed: {exc}")
