import tempfile
import unittest
from pathlib import Path

from brain import Brain


class BrainDietaryRestrictionsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.brain_path = Path(self.temp_dir.name) / "brain.json"
        self.brain = Brain(self.brain_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exposes_fda_major_allergens(self):
        self.assertEqual(
            [option["id"] for option in self.brain.get_available_dietary_restrictions()],
            [
                "milk",
                "eggs",
                "fish",
                "crustacean_shellfish",
                "tree_nuts",
                "peanuts",
                "gluten",
                "soybeans",
                "sesame",
            ],
        )

    def test_saves_unique_selections_in_canonical_order(self):
        selected = self.brain.set_dietary_restrictions(["sesame", "milk", "milk"])

        self.assertEqual(selected, ["milk", "sesame"])
        self.assertEqual(self.brain.get_all()["dietary_restrictions"], ["milk", "sesame"])
        self.assertEqual(
            Brain(self.brain_path).get_dietary_restrictions(),
            ["milk", "sesame"],
        )

    def test_rejects_unknown_selection_without_changing_saved_value(self):
        self.brain.set_dietary_restrictions(["peanuts"])

        with self.assertRaisesRegex(ValueError, "Unsupported dietary restriction IDs"):
            self.brain.set_dietary_restrictions(["milk", "unknown"])

        self.assertEqual(self.brain.get_dietary_restrictions(), ["peanuts"])

    def test_requires_a_list_of_string_ids(self):
        with self.assertRaisesRegex(ValueError, "must be a list"):
            self.brain.set_dietary_restrictions("milk")

    def test_saves_and_normalizes_other_allergies(self):
        preferences = self.brain.set_dietary_preferences(
            ["peanuts"],
            ["  Coconut  ", "coconut", "gluten"],
        )

        self.assertEqual(preferences["dietary_restrictions"], ["peanuts"])
        self.assertEqual(preferences["other_dietary_restrictions"], ["Coconut", "gluten"])
        self.assertEqual(
            Brain(self.brain_path).get_all()["other_dietary_restrictions"],
            ["Coconut", "gluten"],
        )

    def test_rejects_invalid_other_allergy_without_changing_preferences(self):
        self.brain.set_dietary_preferences(["milk"], ["Coconut"])

        with self.assertRaisesRegex(ValueError, "80 characters or fewer"):
            self.brain.set_dietary_preferences(["eggs"], ["a" * 81])

        self.assertEqual(self.brain.get_dietary_restrictions(), ["milk"])
        self.assertEqual(self.brain.get_other_dietary_restrictions(), ["Coconut"])

    def test_migrates_saved_wheat_selection_to_gluten(self):
        self.brain.data["dietary_restrictions"] = ["wheat"]
        self.brain.save()

        migrated_brain = Brain(self.brain_path)

        self.assertEqual(migrated_brain.get_dietary_restrictions(), ["gluten"])
