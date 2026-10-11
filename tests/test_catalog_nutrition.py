import tempfile
import unittest
from pathlib import Path

from brain import Brain


class CatalogNutritionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.brain = Brain(Path(self.temp_dir.name) / "brain.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_catalog_macros_are_seeded_and_not_replaced_by_ai_results(self):
        expected = {
            "apples": {"carbs": 25.0, "protein": 0.5, "fat": 0.3},
            "bananas": {"carbs": 27.0, "protein": 1.3, "fat": 0.3},
            "buffalo sauce": {"carbs": 1.0, "protein": 0.0, "fat": 2.0},
            "barbecue sauce": {"carbs": 18.0, "protein": 0.0, "fat": 0.0},
            "water bottle": {"carbs": 0.0, "protein": 0.0, "fat": 0.0},
        }

        self.assertEqual(
            {item: self.brain.get_nutrition_store()[item] for item in expected},
            expected,
        )
        self.assertEqual(self.brain.get_pending_items(), [])

        self.brain.apply_ai_nutrition({
            "apples": {"carbs": 99, "protein": 99, "fat": 99},
            "bananas": {"carbs": 99, "protein": 99, "fat": 99},
        })
        self.assertEqual(self.brain.get_nutrition_store()["apples"], expected["apples"])
        self.assertEqual(self.brain.get_nutrition_store()["bananas"], expected["bananas"])

    def test_catalog_macros_scale_with_quantity(self):
        self.brain.set_item("apples", 2)
        self.brain.set_item("buffalo sauce", 3)

        self.assertEqual(
            self.brain.get_macro_totals()["items"],
            {
                "apples": {"carbs": 50.0, "protein": 1.0, "fat": 0.6},
                "buffalo sauce": {"carbs": 3.0, "protein": 0.0, "fat": 6.0},
            },
        )


if __name__ == "__main__":
    unittest.main()
