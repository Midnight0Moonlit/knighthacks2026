import tempfile
import threading
import time
import unittest
from pathlib import Path

from brain import Brain
from nutrition_scheduler import NutritionScheduler


class NutritionSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.brain = Brain(Path(self.temp_dir.name) / "brain.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def wait_for(self, condition, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for scheduler condition")

    def test_grace_period_batches_items_added_before_call(self):
        calls = []
        called = threading.Event()

        def lookup(items):
            calls.append(items)
            called.set()
            return {item: {"carbs": 1, "protein": 2, "fat": 3} for item in items}

        self.brain.add_item("oranges")
        scheduler = NutritionScheduler(
            self.brain,
            lookup,
            cart_grace_seconds=0.08,
            minimum_interval_seconds=0,
        )
        scheduler.enter_cart()
        time.sleep(0.03)
        self.assertFalse(called.is_set(), "The lookup started before the cart grace period ended")
        self.brain.add_item("beans")
        scheduler.inventory_changed()

        self.assertTrue(called.wait(1))
        self.assertEqual(calls, [["oranges", "beans"]])
        self.wait_for(lambda: self.brain.get_pending_items() == [])

    def test_additions_during_call_wait_for_next_rate_limited_batch(self):
        calls = []
        call_times = []
        first_call_started = threading.Event()
        finish_first_call = threading.Event()
        second_call_finished = threading.Event()
        active_calls = 0
        max_active_calls = 0
        state_lock = threading.Lock()

        def lookup(items):
            nonlocal active_calls, max_active_calls
            with state_lock:
                active_calls += 1
                max_active_calls = max(max_active_calls, active_calls)
                call_times.append(time.monotonic())
                call_number = len(calls)
                calls.append(items)
            try:
                if call_number == 0:
                    first_call_started.set()
                    self.assertTrue(finish_first_call.wait(1))
                else:
                    second_call_finished.set()
                return {item: {"carbs": 1, "protein": 2, "fat": 3} for item in items}
            finally:
                with state_lock:
                    active_calls -= 1

        self.brain.add_item("oranges")
        scheduler = NutritionScheduler(
            self.brain,
            lookup,
            cart_grace_seconds=0,
            minimum_interval_seconds=0.12,
        )
        scheduler.enter_cart()
        self.assertTrue(first_call_started.wait(1))

        self.brain.add_item("beans")
        self.brain.add_item("donuts")
        scheduler.inventory_changed()
        finish_first_call.set()

        self.assertTrue(second_call_finished.wait(1))
        self.wait_for(lambda: self.brain.get_pending_items() == [])
        self.assertEqual(calls, [["oranges"], ["beans", "donuts"]])
        self.assertGreaterEqual(call_times[1] - call_times[0], 0.10)
        self.assertEqual(max_active_calls, 1)
        self.assertEqual(self.brain.get_pending_items(), [])

    def test_failed_call_keeps_items_pending_and_exposes_error(self):
        def lookup(_items):
            raise RuntimeError("temporary Gemini failure")

        self.brain.add_item("donuts")
        scheduler = NutritionScheduler(
            self.brain,
            lookup,
            cart_grace_seconds=0,
            minimum_interval_seconds=0,
        )
        scheduler.enter_cart()

        self.wait_for(lambda: scheduler.get_error() is not None)
        self.assertEqual(self.brain.get_pending_items(), ["donuts"])
        self.assertIn("temporary Gemini failure", scheduler.get_error())
        self.assertGreater(self.brain.get_last_ai_run(), 0)

        retry_called = threading.Event()

        def retry_lookup(items):
            retry_called.set()
            return {item: {"carbs": 1, "protein": 2, "fat": 3} for item in items}

        restarted_scheduler = NutritionScheduler(
            self.brain,
            retry_lookup,
            cart_grace_seconds=0,
            minimum_interval_seconds=0.12,
        )
        restarted_scheduler.enter_cart()
        time.sleep(0.03)
        self.assertFalse(retry_called.is_set(), "A restart bypassed the persisted call interval")
        self.assertTrue(retry_called.wait(1))
        self.wait_for(lambda: self.brain.get_pending_items() == [])

    def test_parallel_inventory_updates_are_persisted_without_lost_counts(self):
        self.brain.set_item("apples", 0)

        def add_many():
            for _ in range(50):
                self.brain.add_item("apples")

        workers = [threading.Thread(target=add_many) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        self.assertEqual(self.brain.get_store()["apples"], 200)
        reloaded = Brain(Path(self.temp_dir.name) / "brain.json")
        self.assertEqual(reloaded.get_store()["apples"], 200)


if __name__ == "__main__":
    unittest.main()
