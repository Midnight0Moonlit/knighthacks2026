import threading
import time
from typing import Callable, Optional

from brain import Brain


class NutritionScheduler:
    """Batches queued food lookups and enforces a global request interval."""

    def __init__(
        self,
        brain: Brain,
        lookup: Callable[[list[str]], dict[str, dict[str, float]]],
        cart_grace_seconds: float = 15,
        minimum_interval_seconds: float = 60,
        clock: Callable[[], float] = time.time,
    ):
        self.brain = brain
        self.lookup = lookup
        self.cart_grace_seconds = cart_grace_seconds
        self.minimum_interval_seconds = minimum_interval_seconds
        self.clock = clock

        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._cart_entered_at: Optional[float] = None
        self._last_call_at = brain.get_last_ai_run()
        self._error: Optional[str] = None
        self._worker: Optional[threading.Thread] = None
        self._request_in_flight = False

    def enter_cart(self) -> None:
        with self._lock:
            self._cart_entered_at = self.clock()
            self._error = None
            self._start_worker_locked()
            self._wake.set()
        print(
            "[app] cart entered; nutrition lookups will wait "
            f"{self.cart_grace_seconds:g} seconds before batching"
        )

    def inventory_changed(self) -> None:
        with self._lock:
            if not self.brain.get_pending_items():
                return
            if self._request_in_flight:
                print(
                    "[app] new food queued during an active Gemini request; "
                    "it will be included in the next rate-limited batch"
                )
            self._error = None
            self._start_worker_locked()
            self._wake.set()

    def get_error(self) -> Optional[str]:
        with self._lock:
            return self._error

    def get_retry_after(self) -> int:
        with self._lock:
            if self._cart_entered_at is None or not self.brain.get_pending_items():
                return 0
            due_at = max(
                self._cart_entered_at + self.cart_grace_seconds,
                self._last_call_at + self.minimum_interval_seconds,
            )
            return max(int(due_at - self.clock() + 0.999), 0)

    def _start_worker_locked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self) -> None:
        try:
            while True:
                if not self.brain.get_pending_items():
                    return

                with self._lock:
                    cart_entered_at = self._cart_entered_at
                    if self._error:
                        return

                if cart_entered_at is None:
                    return

                now = self.clock()
                due_at = max(
                    cart_entered_at + self.cart_grace_seconds,
                    self._last_call_at + self.minimum_interval_seconds,
                )
                delay = due_at - now
                if delay > 0:
                    self._wake.wait(delay)
                    self._wake.clear()
                    continue

                pending_items = self.brain.get_pending_items()
                if not pending_items:
                    continue

                started_at = self.clock()
                try:
                    with self._lock:
                        # Persist the start, not just successful completions, so failures
                        # and server restarts cannot bypass the minimum call interval.
                        self._last_call_at = started_at
                        self.brain.set_last_ai_run(started_at)
                        self._request_in_flight = True
                except Exception as exc:
                    with self._lock:
                        self._error = str(exc)
                    print(f"[app] could not reserve Gemini request slot: {exc}")
                    return

                print(f"[app] asking Gemini for batched item macros: {pending_items}")
                try:
                    nutrition_updates = self.lookup(pending_items)
                    missing = [item for item in pending_items if item not in nutrition_updates]
                    if missing:
                        raise ValueError(
                            f"Gemini did not return macro data for pending items: {missing}"
                        )
                    self.brain.apply_ai_nutrition(nutrition_updates)
                except Exception as exc:
                    with self._lock:
                        self._request_in_flight = False
                        self._error = str(exc)
                    print(f"[app] Gemini nutrition lookup failed; items remain pending: {exc}")
                    return

                with self._lock:
                    self._request_in_flight = False
                    self._error = None
                print(f"[app] AI nutrition update saved to brain: {nutrition_updates}")
        finally:
            with self._lock:
                self._worker = None
                if (
                    self.brain.get_pending_items()
                    and self._cart_entered_at is not None
                    and not self._error
                ):
                    self._start_worker_locked()
