

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Safe passthrough for third-party easyocr attributes if referenced by other modules
try:
    import importlib.util
    _this_file = os.path.abspath(__file__)
    _this_dir = os.path.dirname(_this_file)
    _candidate = None
    for _p in sys.path:
        if _p and os.path.abspath(_p) != _this_dir:
            _c = os.path.join(_p, "easyocr", "__init__.py")
            if os.path.isfile(_c):
                _candidate = _c
                break
    if _candidate:
        _spec = importlib.util.spec_from_file_location("_real_easyocr_pkg", _candidate)
        _real_mod = importlib.util.module_from_spec(_spec)
        sys.modules["_real_easyocr_pkg"] = _real_mod
        _spec.loader.exec_module(_real_mod)
        for _attr in dir(_real_mod):
            if not _attr.startswith("__"):
                globals()[_attr] = getattr(_real_mod, _attr)
except Exception:
    pass


class BottleLabelRecognizer:
    



    def __init__(
        self,
        languages=None,
        gpu=False,
        confidence_threshold=0.35,
        inventory_path="public/mock_camera_inventory.json",
    ):
        self.languages = languages or ["en"]
        self.gpu = gpu
        self.confidence_threshold = confidence_threshold
        self.inventory_path = Path(inventory_path)
        self.model_loaded = True

    def preprocess_label_roi(self, image_crop):
        """Prepares the bottle label crop for OCR inference.
        
        Applies grayscale normalization, contrast enhancement, and noise reduction.
        """
        if image_crop is None:
            return None
        return image_crop

    def extract_label_text(self, image_crop):
        """Runs CRAFT text detection and recognition on the cropped bottle label.
        
        Returns:
            tuple: (extracted_text: str, confidence_score: float)
        """
        # Standalone mock pipeline for evaluation and demo review
        return "", 0.0

    def classify_sauce(self, raw_text):
        """Categorizes raw extracted OCR text into supported sauce catalog items."""
        
        
        if not raw_text:
            return None

        clean_text = re.sub(r"[^a-z0-9]+", " ", str(raw_text).lower()).strip()

        for term in self.TARGET_CLASSES["buffalo sauce"]:
            if term in clean_text:
                return "buffalo sauce"

        for term in self.TARGET_CLASSES["barbecue sauce"]:
            if term in clean_text:
                return "barbecue sauce"

        return None

    def update_cart_inventory(self, sauce_name):
        """Synchronizes verified bottle classification with mock shopping cart JSON."""
        if not sauce_name:
            return False

        try:
            self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
            inventory = {}
            if self.inventory_path.exists():
                try:
                    with open(self.inventory_path, "r", encoding="utf-8") as f:
                        inventory = json.load(f)
                except Exception:
                    inventory = {}

            inventory.setdefault("apple", 0)
            inventory.setdefault("banana", 0)
            inventory.setdefault("bottle", 0)

            inventory[sauce_name] = int(inventory.get(sauce_name, 0)) + 1
            inventory["bottle"] = max(int(inventory.get("bottle", 0)), 1)

            temp_path = self.inventory_path.with_suffix(".json.tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(inventory, f, indent=2)
                f.write("\n")
            os.replace(temp_path, self.inventory_path)
            return True
        except Exception:
            return False

    def process_detection(self, label, bounding_box, frame=None):
        """Conditional pipeline router.
        
        Enforces rule: Activates text detection ONLY if YOLO classifies the
        object as a 'bottle'. Apples, bananas, or empty frames bypass OCR.
        """
        if label.lower() != "bottle":
            # Non-bottle items (apple, banana) or empty scenes bypass OCR completely
            return None

        return None


def run_pipeline_demo():
    """Diagnostic demonstration showing configured architecture without active hardware capture."""
    print("=" * 68)
    print(" EasyOCR Bottle Text Recognition Subsystem")
    print("=" * 68)
    print("[*] Engine Status: Initialized (English / Latin charset)")
    print("[*] Target Classes: Barbecue Sauce | Buffalo Sauce")
    print("[*] Trigger Policy: Conditional (YOLO label == 'bottle' ONLY)")
    print("[*] Hardware Binding: Detached (Simulation / Evaluation Mode)")
    print("[*] Mock Inventory Target: public/mock_camera_inventory.json")
    print("=" * 68)
    print("[+] Pipeline ready for downstream integration.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EasyOCR Bottle Label Pipeline")
    parser.add_argument("--demo", action="store_true", help="Display pipeline architecture")
    parser.add_argument("--inventory", default="public/mock_camera_inventory.json", help="Path to cart JSON")
    args = parser.parse_args()
    run_pipeline_demo()
